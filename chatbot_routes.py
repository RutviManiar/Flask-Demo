import os
import re
from typing import Any

from flask import Blueprint, render_template, request, redirect, url_for, session
from sqlalchemy import func, or_, text

from models import db, Emp, Dept, Payroll

try:
    import anthropic
except ImportError:
    anthropic = None

AnthropicError = Exception
if anthropic is not None:
    anthropic_error_module = getattr(anthropic, 'exceptions', None)
    if anthropic_error_module is not None:
        AnthropicError = getattr(anthropic_error_module, 'AnthropicError', Exception)
    else:
        AnthropicError = getattr(anthropic, 'AnthropicError', Exception)

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')

ALLOWED_TABLES = {'emp', 'dept', 'payroll'}
ALLOWED_COLUMNS = {
    'emp': {'eno', 'ename', 'sal', 'deptid', 'is_deleted', 'email', 'phone', 'role'},
    'dept': {'id', 'dname', 'loc', 'created_date', 'is_deleted'},
    'payroll': {'id', 'emp', 'month', 'year', 'base_salary', 'present_days', 'total_days', 'net_salary'},
}
ALLOWED_COLUMNS_FLAT = set().union(*ALLOWED_COLUMNS.values())
SQL_RESERVED_WORDS = {
    'select', 'from', 'where', 'and', 'or', 'join', 'left', 'right', 'inner', 'outer',
    'on', 'as', 'order', 'by', 'group', 'having', 'limit', 'offset', 'desc', 'asc',
    'count', 'avg', 'min', 'max', 'sum', 'lower', 'upper', 'cast', 'extract', 'year',
    'date', 'true', 'false', 'null', 'is', 'not', 'in', 'like', 'ilike', 'between',
    'case', 'when', 'then', 'else', 'end', 'distinct', 'exists', 'all', 'any'
}
BANNED_TOKENS = {';', '--', '/*', '*/', 'insert', 'update', 'delete', 'drop', 'alter', 'create', 'grant', 'revoke', 'truncate', 'replace'}


def _normalize(text: str) -> str:
    return (text or '').strip().lower()


def _openai_enabled() -> bool:
    if anthropic is None:
        return False

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return False

    return hasattr(anthropic, 'Anthropic')


def _standardize_text_token(token: str) -> str:
    return token.lower().strip().strip('(),')


def _clean_string_literal(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9 _-]", '', value).strip()


def _to_sql_from_openai(query_text: str) -> str:
    if not _openai_enabled():
        raise RuntimeError('Claude is not configured. Install anthropic and set ANTHROPIC_API_KEY to use the LLM converter.')

    prompt = (
        'You are an assistant that converts user plain-English requests into SQL SELECT statements. '
        'Only use the tables emp, dept, and payroll. Only use these allowed columns exactly as provided: '
        'emp(eno, ename, sal, deptid, is_deleted, email, phone, role), '
        'dept(id, dname, loc, created_date, is_deleted), '
        'payroll(id, emp, month, year, base_salary, present_days, total_days, net_salary). '
        'Always include emp.is_deleted = FALSE for employee queries. Do not generate INSERT/UPDATE/DELETE/DDL. '
        'Do not include any comments or semicolons. Return only the SQL query.'
    )

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    response = client.messages.create(
        model='claude-3-haiku-20240307',
        max_tokens=256,
        system=prompt,
        messages=[
            {'role': 'user', 'content': query_text},
        ],
        temperature=0,
    )
    sql = response.content[0].text.strip()

    return sql


def _to_sql_from_fallback(query_text: str) -> str:
    text = _normalize(query_text)
    if 'employee' not in text and 'employees' not in text:
        raise ValueError('Currently only employee list queries are supported by the plain-English query builder.')

    select_clause = (
        'SELECT emp.eno, emp.ename, emp.sal, dept.dname AS department, emp.email, emp.phone, emp.role '
        'FROM emp LEFT JOIN dept ON emp.deptid = dept.id'
    )
    conditions = ['emp.is_deleted = FALSE']

    dept_match = re.search(r'\bin\s+([a-zA-Z ]+?)(?:\s+with|\s+and|\s*$)', text)
    if dept_match:
        dept_name = _clean_string_literal(dept_match.group(1))
        if dept_name and dept_name not in {'employees', 'employee', 'department', 'departments'}:
            conditions.append(f"LOWER(dept.dname) = '{dept_name.lower()}'")
            conditions.append('dept.is_deleted = FALSE')

    salary_above = re.search(r'salary\s+(?:above|over|greater than|more than)\s*([\d.,km]+)', text)
    salary_below = re.search(r'salary\s+(?:below|under|less than)\s*([\d.,km]+)', text)
    if salary_above:
        value = salary_above.group(1).replace(',', '').lower()
        if value.endswith('k'):
            value = float(value[:-1]) * 1000
        elif value.endswith('m'):
            value = float(value[:-1]) * 1000000
        else:
            value = float(value)
        conditions.append(f'emp.sal > {int(value)}')
    elif salary_below:
        value = salary_below.group(1).replace(',', '').lower()
        if value.endswith('k'):
            value = float(value[:-1]) * 1000
        elif value.endswith('m'):
            value = float(value[:-1]) * 1000000
        else:
            value = float(value)
        conditions.append(f'emp.sal < {int(value)}')

    if any(word in text for word in ['hired after', 'hired before', 'hire date', 'hired on', 'hired in']):
        raise ValueError('The current schema does not expose employee hire date, so date-based filters are not supported.')

    return select_clause + ' WHERE ' + ' AND '.join(conditions)


def _validate_sql(query_text: str) -> tuple[bool, str | None]:
    normalized = query_text.strip().lower()
    if not normalized.startswith('select '):
        return False, 'Only SELECT queries are allowed.'

    for banned in BANNED_TOKENS:
        if banned.isalpha():
            if re.search(rf"\b{re.escape(banned)}\b", normalized):
                return False, f'SQL contains unsupported operation: {banned}'
        elif banned in normalized:
            return False, f'SQL contains unsupported operation: {banned}'

    cleaned = re.sub(r'''('[^']*'|"[^"]*")''', ' ', normalized)
    token_pattern = re.compile(r"[a-zA-Z_][a-zA-Z0-9_\.]*")
    for token in token_pattern.findall(cleaned):
        token = token.lower()
        if token in SQL_RESERVED_WORDS or token.isdigit() or token in ALLOWED_TABLES or token in {'emp', 'dept', 'payroll'}:
            continue
        if '.' in token:
            table, column = token.split('.', 1)
            if table not in ALLOWED_TABLES:
                return False, f'Invalid table name: {table}'
            if column not in ALLOWED_COLUMNS.get(table, set()):
                return False, f'Invalid column name: {table}.{column}'
            continue
        if token in ALLOWED_COLUMNS_FLAT:
            continue
        return False, f'Invalid SQL identifier: {token}'

    return True, None


def _execute_sql(query_text: str) -> list[dict[str, Any]]:
    result = db.session.execute(text(query_text))
    rows = [dict(row._mapping) for row in result]
    return rows


def _search_employee(query_text: str) -> str | None:
    tokens = re.findall(r"[\w@.%-]+", query_text)
    tokens = [t for t in tokens if len(t) > 1]
    for token in tokens:
        employee = (
            Emp.query
            .filter(Emp.is_deleted == False)
            .filter(
                or_(
                    Emp.ename.ilike(f"%{token}%"),
                    Emp.email.ilike(f"%{token}%")
                )
            )
            .first()
        )
        if employee:
            dept_name = employee.department.dname if employee.department else 'Unassigned'
            return (
                f"Employee {employee.ename} (ID {employee.eno}) works in {dept_name}. "
                f"Email: {employee.email or 'N/A'}. Phone: {employee.phone or 'N/A'}. "
                f"Current salary is {employee.sal:.2f}."
            )
    return None


def _search_department(query_text: str) -> str | None:
    tokens = re.findall(r"[\w%-]+", query_text)
    tokens = [t for t in tokens if len(t) > 1]
    for token in tokens:
        department = (
            Dept.query
            .filter(Dept.is_deleted == False)
            .filter(Dept.dname.ilike(f"%{token}%"))
            .first()
        )
        if department:
            employee_count = Emp.query.filter_by(deptid=department.id, is_deleted=False).count()
            return (
                f"Department {department.dname} (located in {department.loc or 'N/A'}) has {employee_count} active employee(s)."
            )
    return None


def _get_latest_payroll_summary() -> str | None:
    payroll = Payroll.query.order_by(Payroll.year.desc(), Payroll.month.desc()).first()
    if not payroll:
        return None

    employee_name = payroll.employee.ename if payroll.employee else 'Unknown employee'
    return (
        f"Most recent payroll record is for {employee_name} in {payroll.month} {payroll.year}. "
        f"Net salary is {payroll.net_salary:.2f} with {payroll.present_days}/{payroll.total_days} present days."
    )


def get_chatbot_response(message: str) -> str:
    text = _normalize(message)
    if not text:
        return "Please type a question and submit it."

    if any(phrase in text for phrase in ["how many employees", "total employees", "employee count", "number of employees"]):
        total = Emp.query.filter_by(is_deleted=False).count()
        return f"There are {total} active employees in the database."

    if any(phrase in text for phrase in ["how many departments", "total departments", "department count", "number of departments"]):
        total = Dept.query.filter_by(is_deleted=False).count()
        return f"There are {total} active departments."

    if "average salary" in text or "avg salary" in text or "average pay" in text:
        average_salary = db.session.query(func.avg(Emp.sal)).filter(Emp.is_deleted == False).scalar() or 0
        return f"The average salary is {average_salary:.2f}."

    if any(phrase in text for phrase in ["highest salary", "max salary", "highest paid"]):
        max_salary = db.session.query(func.max(Emp.sal)).filter(Emp.is_deleted == False).scalar() or 0
        return f"The highest reported salary is {max_salary:.2f}."

    if any(phrase in text for phrase in ["lowest salary", "min salary", "lowest paid"]):
        min_salary = db.session.query(func.min(Emp.sal)).filter(Emp.is_deleted == False).scalar() or 0
        return f"The lowest reported salary is {min_salary:.2f}."

    if "payroll" in text:
        payroll_summary = _get_latest_payroll_summary()
        if payroll_summary:
            return payroll_summary
        return "There are no payroll records yet."

    if "employee" in text or "staff" in text or "person" in text:
        employee_info = _search_employee(text)
        if employee_info:
            return employee_info
        return (
            "I can help with employee lookups and HR questions. "
            "Try asking: 'Show employee details for Alice' or 'Find employee by email'."
        )

    if "department" in text:
        department_info = _search_department(text)
        if department_info:
            return department_info
        return (
            "I can help with department summaries. "
            "Try asking: 'How many employees are in Sales?' or 'Department info for IT'."
        )

    return (
        "I can answer HR and payroll questions about employees, departments, and salaries. "
        "For example: 'How many employees do we have?', 'What is the average salary?', or 'Show me employee details for john@example.com'."
    )


@chatbot_bp.route('/', methods=['GET', 'POST'])
def home():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    chat_history = session.get('chat_history', [])

    if request.method == 'POST':
        if request.form.get('action') == 'clear':
            session.pop('chat_history', None)
            return redirect(url_for('chatbot.home'))

        user_message = request.form.get('message', '').strip()
        if user_message:
            bot_reply = get_chatbot_response(user_message)
            chat_history.append({'sender': 'You', 'message': user_message})
            chat_history.append({'sender': 'HR Assistant', 'message': bot_reply})
            session['chat_history'] = chat_history[-30:]

    return render_template('chatbot/chat.html', chat_history=chat_history)


@chatbot_bp.route('/nl_query', methods=['GET', 'POST'])
def nl_query():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    query_text = ''
    sql_text = None
    query_results = None
    error_message = None
    source = 'Claude' if _openai_enabled() else 'fallback'

    if request.method == 'POST':
        query_text = request.form.get('nl_query', '').strip()
        if query_text:
            if _openai_enabled():
                try:
                    sql_text = _to_sql_from_openai(query_text)
                except Exception as claude_exc:
                    fallback_reason = str(claude_exc)
                    source = 'fallback'
                    try:
                        sql_text = _to_sql_from_fallback(query_text)
                        error_message = (
                            f'Claude failed ({fallback_reason}). Using local fallback converter instead.'
                        )
                    except Exception as fallback_exc:
                        error_message = (
                            f'Claude failed ({fallback_reason}) and local fallback also failed: {fallback_exc}'
                        )
                        sql_text = None
                except Exception as exc:
                    error_message = str(exc)
            else:
                try:
                    sql_text = _to_sql_from_fallback(query_text)
                except Exception as exc:
                    error_message = str(exc)

            if sql_text and not error_message:
                valid, validation_error = _validate_sql(sql_text)
                if not valid:
                    error_message = validation_error
                    sql_text = None
                else:
                    query_results = _execute_sql(sql_text)
            elif sql_text and error_message:
                valid, validation_error = _validate_sql(sql_text)
                if not valid:
                    error_message = f'{error_message} | {validation_error}'
                    sql_text = None
                else:
                    query_results = _execute_sql(sql_text)

    return render_template(
        'chatbot/nl_query.html',
        query_text=query_text,
        sql_text=sql_text,
        query_results=query_results,
        error_message=error_message,
        source=source,
    )
