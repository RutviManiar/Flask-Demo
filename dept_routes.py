from flask import Blueprint, render_template, request, redirect, url_for

from models import db, Dept

dept_bp = Blueprint('dept', __name__)


@dept_bp.route('/depts')
def list_depts():
    depts = Dept.query.filter_by(is_deleted=False).all()
    return render_template('dept/depts.html', depts=depts)


@dept_bp.route('/dept/add', methods=['GET', 'POST'])
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
        return redirect(next_url or url_for('dept.list_depts'))

    return render_template('dept/dept_form.html', action="Add", next_url=next_url)


@dept_bp.route('/dept/edit/<int:id>', methods=['GET', 'POST'])
def edit_dept(id):
    dept = Dept.query.get_or_404(id)
    if request.method == 'POST':
        dept.dname = request.form['dname']
        dept.loc = request.form['loc']
        dept.created_date = request.form['created_date']
        dept.is_deleted = request.form.get('is_deleted') == 'false'
        db.session.commit()
        return redirect(url_for('dept.list_depts'))
    return render_template('dept/dept_form.html', dept=dept, action="Edit")


@dept_bp.route('/dept/delete/<int:id>')
def delete_dept(id):
    dept = Dept.query.filter_by(id=id, is_deleted=False).first_or_404()
    dept.is_deleted = True
    db.session.commit()
    return redirect(url_for('dept.list_depts'))


@dept_bp.route('/report')
def report():
    depts = Dept.query.filter_by(is_deleted=False).all()
    return render_template('dept/report.html', depts=depts)