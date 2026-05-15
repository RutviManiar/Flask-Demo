from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response, abort
from datetime import datetime, date

from models import db, Emp, Dept
from utils import send_email


def get_minimum_birth_date():
    today = date.today()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        # Handle leap day birthdays
        return today.replace(year=today.year - 18, day=28)


def parse_birth_date(birth_date_str):
    if not birth_date_str:
        return None
    try:
        return datetime.strptime(birth_date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


emp_bp = Blueprint('emp', __name__)


def _guess_image_mime(data: bytes) -> str:
    # Minimal fingerprinting for common image formats.
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


@emp_bp.route('/emps')
def list_emps():
    emps = Emp.query.filter_by(is_deleted=False).all()
    return render_template('emp/emps.html', emps=emps)


@emp_bp.route('/emp/add', methods=['GET', 'POST'])
def add_emp():
    depts = Dept.query.all()
    error = None

    if request.method == 'POST':
        ename = request.form['ename']
        sal = request.form['sal']
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        deptid = request.form['deptid']
        is_deleted = request.form.get('is_deleted') == 'false'
        
        # Parse birth date
        birth_date = parse_birth_date(request.form.get('birth_date', '').strip())
        if request.form.get('birth_date', '').strip() and not birth_date:
            error = 'Invalid birth date format.'

        min_birth_date = get_minimum_birth_date()
        if birth_date and birth_date > min_birth_date:
            error = 'Employee must be at least 18 years old.'

        image_file = request.files.get('image')
        image_data = None
        if image_file and image_file.filename:
            image_data = image_file.read()

        if email:
            existing = Emp.query.filter_by(email=email, is_deleted=False).first()
            if existing:
                error = "Email is already in use. Please choose another."

        if not error:
            new_emp = Emp(
                ename=ename,
                sal=sal,
                email=email,
                phone=phone,
                password=password,
                role=role,
                deptid=deptid,
                is_deleted=is_deleted,
                image=image_data,
                birth_date=birth_date,
            )
            db.session.add(new_emp)
            db.session.commit()

            # Send welcome email after successful creation
            if email:
                try:
                    send_email(
                        to_email=email,
                        subject="Welcome to the team",
                        body=(
                            f"Hi {ename},\n\n"
                            "Your employee account has been created. "
                            "You can log in using this email address.\n\n"
                            "Best,\n"
                            "FlaskDemo Team"
                        ),
                    )
                    flash('Welcome email sent successfully.', 'success')
                except Exception as exc:
                    flash(f'Employee created, but failed to send email: {exc}', 'warning')

            return redirect(url_for('emp.list_emps'))

    return render_template(
        'emp/emp_form.html',
        depts=depts,
        action="Add",
        error=error,
        max_birth_date=get_minimum_birth_date().isoformat(),
    )


@emp_bp.route('/emp/edit/<int:eno>', methods=['GET', 'POST'])
def edit_emp(eno):
    emp = Emp.query.filter_by(eno=eno, is_deleted=False).first_or_404()
    depts = Dept.query.all()
    error = None

    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            existing = (
                Emp.query
                .filter(Emp.email == email, Emp.is_deleted == False, Emp.eno != eno)
                .first()
            )
            if existing:
                error = "Email is already in use. Please choose another."

        birth_date = parse_birth_date(request.form.get('birth_date', '').strip())
        if request.form.get('birth_date', '').strip() and not birth_date:
            error = 'Invalid birth date format.'

        min_birth_date = get_minimum_birth_date()
        if birth_date and birth_date > min_birth_date:
            error = 'Employee must be at least 18 years old.'

        if not error:
            emp.ename = request.form['ename']
            emp.email = email
            emp.phone = request.form.get('phone')
            emp.birth_date = birth_date

            image_file = request.files.get('image')
            if image_file and image_file.filename:
                emp.image = image_file.read()

            password = request.form.get('password')
            if password:
                emp.password = password

            # Regular users cannot change salary/role/department
            if session.get('user_role') != 'user':
                emp.sal = request.form['sal']
                emp.role = request.form.get('role', 'user')
                emp.deptid = request.form['deptid']

            emp.is_deleted = request.form.get('is_deleted') == 'false'
            db.session.commit()
            flash('Updated successfully', 'success')
            if session.get('user_role') == 'user':
                return redirect(url_for('emp.edit_emp', eno=eno))
            return redirect(url_for('emp.list_emps'))

    return render_template(
        'emp/emp_form.html',
        emp=emp,
        depts=depts,
        action="Edit",
        error=error,
        max_birth_date=get_minimum_birth_date().isoformat(),
    )


@emp_bp.route('/emp/delete/<int:eno>')
def delete_emp(eno):
    emp = Emp.query.filter_by(eno=eno, is_deleted=False).first_or_404()
    emp.is_deleted = True
    db.session.commit()
    return redirect(url_for('emp.list_emps'))


@emp_bp.route('/emp/<int:eno>/image')
def emp_image(eno):
    emp = Emp.query.filter_by(eno=eno, is_deleted=False).first_or_404()
    if not emp.image:
        abort(404)

    mime_type = _guess_image_mime(emp.image)
    return Response(emp.image, mimetype=mime_type)