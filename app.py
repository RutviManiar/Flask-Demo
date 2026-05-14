import base64
import io
import os

from flask import Flask, Response, jsonify, render_template, request, redirect, url_for, session, flash
from PIL import Image
from deepface import DeepFace
import numpy as np
from models import db, Emp, Dept, Announcement
from flask_migrate import Migrate
from dotenv import load_dotenv
from dept_routes import dept_bp
from emp_routes import emp_bp
from att_routes import att_bp
from payroll_routes import payroll_bp
from chatbot_routes import chatbot_bp
from announcement_routes import announcement_bp
from leave_routes import leave_bp, get_leave_balance, LEAVE_BALANCE
from holiday_routes import holiday_bp

app = Flask(__name__)
load_dotenv()  # loads .env from project root

app.secret_key = "dev-secret"  # Replace with a secure random key in production

# Database Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://root:@localhost/test')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail Config (update with your SMTP settings or via .env)
# Example .env values are provided in the repository root.

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = _env_bool('MAIL_USE_TLS', True)
app.config['MAIL_USE_SSL'] = _env_bool('MAIL_USE_SSL', False)
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = (
    os.getenv('MAIL_DEFAULT_SENDER_NAME', 'FlaskDemo'),
    os.getenv('MAIL_DEFAULT_SENDER_EMAIL', os.getenv('MAIL_USERNAME', 'noreply@example.com')),
)


db.init_app(app)
migrate = Migrate(app, db)

app.register_blueprint(dept_bp)
app.register_blueprint(emp_bp)
app.register_blueprint(att_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(announcement_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(holiday_bp)


@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    if user_id:
        user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
        return {'current_user': user}
    return {'current_user': None}


@app.route('/')
def index():
    # If not logged in, show login page as default home
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    # ADMIN DASHBOARD
    if current_user and current_user.role == 'admin':
        total_employees = Emp.query.filter_by(is_deleted=False).count()
        total_departments = Dept.query.filter_by(is_deleted=False).count()

        avg_salary = (
            db.session
            .query(db.func.avg(Emp.sal))
            .filter(Emp.is_deleted == False)
            .scalar()
        ) or 0

        employees_per_department = (
            db.session
            .query(
                Dept.dname.label('department'),
                db.func.count(Emp.eno).label('employee_count')
            )
            .outerjoin(Emp, db.and_(Emp.deptid == Dept.id, Emp.is_deleted == False))
            .filter(Dept.is_deleted == False)
            .group_by(Dept.dname)
            .all()
        )

        recent_announcements = (
            Announcement.query
            .filter_by(is_deleted=False)
            .order_by(Announcement.created_at.desc())
            .limit(5)
            .all()
        )

        return render_template(
            'index.html',
            total_employees=total_employees,
            total_departments=total_departments,
            avg_salary=avg_salary,
            employees_per_department=employees_per_department,
            recent_announcements=recent_announcements,
            is_admin=True,
        )
    
    # EMPLOYEE DASHBOARD
    else:
        recent_announcements = (
            Announcement.query
            .filter_by(is_deleted=False)
            .order_by(Announcement.created_at.desc())
            .limit(5)
            .all()
        )

        # Calculate leave balances
        leave_balances = {}
        for leave_type in LEAVE_BALANCE.keys():
            leave_balances[leave_type] = get_leave_balance(user_id, leave_type)

        return render_template(
            'index.html',
            current_user=current_user,
            recent_announcements=recent_announcements,
            leave_balances=leave_balances,
            is_admin=False,
        )


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = Emp.query.filter_by(email=email, is_deleted=False).first()
        if not user or user.password != password:
            error = 'Invalid email or password'
        else:
            session['user_id'] = user.eno
            session['user_email'] = user.email
            session['user_role'] = user.role
            # Redirect regular users directly to their own edit page
#            if user.role == 'user':
#                return redirect(url_for('index'))
            return redirect(url_for('index'))

    return render_template('login.html', error=error)


def _decode_face_data_url(data_url: str) -> np.ndarray | None:
    if not data_url or ',' not in data_url:
        return None
    try:
        header, encoded = data_url.split(',', 1)
        image_data = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        return np.array(image)
    except Exception:
        return None


def _load_image_from_blob(blob: bytes) -> np.ndarray | None:
    if not blob:
        return None
    try:
        image = Image.open(io.BytesIO(blob)).convert('RGB')
        return np.array(image)
    except Exception:
        return None


def _get_face_model():
    # Removed: DeepFace handles model loading internally
    pass


@app.route('/face_login', methods=['POST'])
def face_login():
    payload = request.get_json(silent=True) or {}
    image_data = payload.get('image')
    if not image_data:
        return jsonify({'error': 'No face image provided.'}), 400

    captured_image = _decode_face_data_url(image_data)
    if captured_image is None:
        return jsonify({'error': 'Unable to decode camera image.'}), 400

    best_match = None
    best_distance = float('inf')

    employees = Emp.query.filter(Emp.image != None, Emp.is_deleted == False).all()
    if not employees:
        return jsonify({'error': 'No registered face profiles available.'}), 404

    for employee in employees:
        known_image = _load_image_from_blob(employee.image)
        if known_image is None:
            continue

        try:
            result = DeepFace.verify(
                img1_path=captured_image,
                img2_path=known_image,
                model_name='ArcFace',
                detector_backend='mtcnn',
                enforce_detection=True
            )
        except Exception as e:
            # Log the exception for debugging
            print(f"Verification failed for employee {employee.eno}: {e}")
            continue

        verified = bool(result.get('verified', False))
        distance = float(result.get('distance', 1.0))
        if verified and distance < best_distance:
            best_distance = distance
            best_match = employee

    if best_match is None:
        return jsonify({'error': 'Face not recognized. Please try again or log in with email/password.'}), 401

    session['user_id'] = best_match.eno
    session['user_email'] = best_match.email
    session['user_role'] = best_match.role
    redirect_url = url_for('emp.edit_emp', eno=best_match.eno) if best_match.role == 'user' else url_for('index')
    return jsonify({'status': 'ok', 'redirect': redirect_url})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/emp_image/<int:eno>')
def emp_image(eno):
    emp = Emp.query.get(eno)
    
    if emp and emp.image:  # image is stored as blob
        return Response(emp.image, mimetype='image/jpeg')
    
    return '', 404


""" # ------------------- DEPARTMENT CRUD -------------------

@app.route('/depts')
def list_depts():
    depts = Dept.query.filter_by(is_deleted=False).all()
    return render_template('depts.html', depts=depts)

@app.route('/dept/add', methods=['GET', 'POST'])
def add_dept():
    next_url = request.args.get('next') or request.form.get('next')

    if request.method == 'POST':
        dname = request.form['dname']
        loc = request.form['loc']
        date_str = request.form['created_date']
        is_deleted = request.form.get('is_deleted') == 'false' # Default to False if not provided
        new_dept = Dept(dname=dname, loc=loc, created_date=date_str, is_deleted=is_deleted)
        db.session.add(new_dept)
        db.session.commit()
        return redirect(next_url or url_for('list_depts'))

    return render_template('dept_form.html', action="Add", next_url=next_url)

@app.route('/dept/edit/<int:id>', methods=['GET', 'POST'])
def edit_dept(id):
    dept = Dept.query.get_or_404(id)
    if request.method == 'POST':
        dept.dname = request.form['dname']
        dept.loc = request.form['loc']
        dept.created_date = request.form['created_date']
        dept.is_deleted = request.form.get('is_deleted') == 'false'
        db.session.commit()
        return redirect(url_for('list_depts'))
    return render_template('dept_form.html', dept=dept, action="Edit")

@app.route('/dept/delete/<int:id>')
def delete_dept(id):
    dept = Dept.query.filter_by(id=id, is_deleted=False).first_or_404()
    dept.is_deleted = True
    db.session.commit()
    return redirect(url_for('list_depts'))


# ------------------- EMPLOYEE CRUD -------------------

@app.route('/emps')
def list_emps():
    emps = Emp.query.filter_by(is_deleted=False).all()
    return render_template('emps.html', emps=emps)


def _guess_image_mime(data: bytes) -> str:
    # Minimal fingerprinting for common image formats.
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    return "application/octet-stream"


@app.route('/emp/<int:eno>/image')
def emp_image(eno):
    emp = Emp.query.filter_by(eno=eno, is_deleted=False).first_or_404()
    if not emp.image:
        abort(404)

    mime_type = _guess_image_mime(emp.image)
    return Response(emp.image, mimetype=mime_type)

@app.route('/emp/add', methods=['GET', 'POST'])
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

            return redirect(url_for('list_emps'))

    return render_template('emp_form.html', depts=depts, action="Add", error=error)

@app.route('/emp/edit/<int:eno>', methods=['GET', 'POST'])
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

        if not error:
            emp.ename = request.form['ename']
            emp.email = email
            emp.phone = request.form.get('phone')

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
                return redirect(url_for('edit_emp', eno=eno))
            return redirect(url_for('list_emps'))

    return render_template('emp_form.html', emp=emp, depts=depts, action="Edit", error=error)

@app.route('/emp/delete/<int:eno>')
def delete_emp(eno):
    emp = Emp.query.filter_by(eno=eno, is_deleted=False).first_or_404()
    emp.is_deleted = True
    db.session.commit()
    return redirect(url_for('list_emps'))
 """
@app.route('/report')
def report():
    depts = Dept.query.filter_by(is_deleted=False).all()
    return render_template('report.html', depts=depts)
 
if __name__ == '__main__':
    app.run(debug=True)

