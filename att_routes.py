from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response, abort
from models import db, Att, Emp

att_bp = Blueprint('att', __name__)

@att_bp.route('/attendance/add', methods=['GET', 'POST'])
def add_attendance():
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 1))  # Last 5 years + current year
    
    error = None

    if request.method == 'POST':
        emp_id = request.form['emp_id']
        month = request.form['month']
        year = int(request.form['year'])
        present_days = int(request.form['present_days'])

        att = Att(emp_id=emp_id, month=month, year=year, present_days=present_days)
        db.session.add(att)
        db.session.commit()

        flash('Attendance record added successfully!', 'success')
        return redirect(url_for('att.list_attendance'))

    emps = Emp.query.filter_by(is_deleted=False).all()
    return render_template('att/att_form.html', emps=emps, years=years, action="Add", error=error)

@att_bp.route('/att/edit/<int:id>', methods=['GET', 'POST'])
def edit_att(id):
    att = Att.query.get_or_404(id)
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 1))

    if request.method == 'POST':
        att.emp_id = request.form['emp_id']
        att.month = request.form['month']
        att.year = int(request.form['year'])
        att.present_days = int(request.form['present_days'])
        db.session.commit()
        flash('Attendance record updated successfully!', 'success')
        return redirect(url_for('att.list_attendance'))

    emps = Emp.query.filter_by(is_deleted=False).all()
    return render_template('att/att_form.html', emps=emps, years=years, action="Edit", error=None, att=att)

@att_bp.route('/atts')
def list_attendance():
    records = Att.query.all()
    return render_template('att/atts.html', records=records)

@att_bp.route('/att/delete/<int:id>')
def delete_att(id):
    att = Att.query.get_or_404(id)
    db.session.delete(att)
    db.session.commit()
    flash('Attendance record deleted successfully!', 'success')
    return redirect(url_for('att.list_attendance'))