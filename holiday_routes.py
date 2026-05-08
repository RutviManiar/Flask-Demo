from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import db, Holiday, Emp
from datetime import datetime, date
from sqlalchemy import func

holiday_bp = Blueprint('holiday', __name__)

@holiday_bp.route('/holidays')
def list_holidays():
    """List all holidays - viewable by all users"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    # Get current year holidays
    current_year = datetime.now().year
    holidays = Holiday.query.filter(
        func.year(Holiday.date) == current_year,
        Holiday.is_active == True
    ).order_by(Holiday.date).all()

    # Get upcoming holidays (next 30 days)
    today = date.today()
    upcoming_holidays = Holiday.query.filter(
        Holiday.date >= today,
        Holiday.is_active == True
    ).order_by(Holiday.date).limit(10).all()

    return render_template('holiday/holidays.html',
                         holidays=holidays,
                         upcoming_holidays=upcoming_holidays,
                         is_admin=(current_user.role == 'admin'),
                         current_year=current_year)

@holiday_bp.route('/holiday/add', methods=['GET', 'POST'])
def add_holiday():
    """Add a new holiday (admin only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        name = request.form['name']
        date_str = request.form['date']
        description = request.form.get('description', '')

        try:
            holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('holiday.add_holiday'))

        # Check if holiday already exists on this date
        existing_holiday = Holiday.query.filter_by(date=holiday_date, is_active=True).first()
        if existing_holiday:
            flash('A holiday already exists on this date', 'danger')
            return redirect(url_for('holiday.add_holiday'))

        # Check if date is in the past
        if holiday_date < date.today():
            flash('Cannot add holidays in the past', 'danger')
            return redirect(url_for('holiday.add_holiday'))

        # Create holiday
        holiday = Holiday(
            name=name,
            date=holiday_date,
            description=description,
            created_by=user_id
        )

        db.session.add(holiday)
        db.session.commit()

        flash('Holiday added successfully', 'success')
        return redirect(url_for('holiday.list_holidays'))

    return render_template('holiday/add_holiday.html', today=date.today().isoformat())

@holiday_bp.route('/holiday/<int:holiday_id>/edit', methods=['GET', 'POST'])
def edit_holiday(holiday_id):
    """Edit a holiday (admin only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role != 'admin':
        abort(403)

    holiday = Holiday.query.filter_by(id=holiday_id, is_active=True).first()
    if not holiday:
        flash('Holiday not found', 'danger')
        return redirect(url_for('holiday.list_holidays'))

    if request.method == 'POST':
        name = request.form['name']
        date_str = request.form['date']
        description = request.form.get('description', '')

        try:
            holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('holiday.edit_holiday', holiday_id=holiday_id))

        # Check if another holiday exists on this date (excluding current)
        existing_holiday = Holiday.query.filter(
            Holiday.date == holiday_date,
            Holiday.id != holiday_id,
            Holiday.is_active == True
        ).first()
        if existing_holiday:
            flash('A holiday already exists on this date', 'danger')
            return redirect(url_for('holiday.edit_holiday', holiday_id=holiday_id))

        # Check if date is in the past
        if holiday_date < date.today():
            flash('Cannot set holidays in the past', 'danger')
            return redirect(url_for('holiday.edit_holiday', holiday_id=holiday_id))

        # Update holiday
        holiday.name = name
        holiday.date = holiday_date
        holiday.description = description

        db.session.commit()

        flash('Holiday updated successfully', 'success')
        return redirect(url_for('holiday.list_holidays'))

    return render_template('holiday/edit_holiday.html', holiday=holiday, today=date.today().isoformat())

@holiday_bp.route('/holiday/<int:holiday_id>/delete', methods=['POST'])
def delete_holiday(holiday_id):
    """Delete a holiday (admin only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role != 'admin':
        abort(403)

    holiday = Holiday.query.filter_by(id=holiday_id, is_active=True).first()
    if not holiday:
        flash('Holiday not found', 'danger')
        return redirect(url_for('holiday.list_holidays'))

    # Soft delete by setting is_active to False
    holiday.is_active = False
    db.session.commit()

    flash('Holiday deleted successfully', 'success')
    return redirect(url_for('holiday.list_holidays'))

def is_holiday_or_weekend(date_to_check):
    """Check if a date is a holiday or weekend"""
    # Check if it's a weekend (Saturday=5, Sunday=6)
    if date_to_check.weekday() >= 5:
        return True, "Weekend"

    # Check if it's a holiday
    holiday = Holiday.query.filter_by(date=date_to_check, is_active=True).first()
    if holiday:
        return True, holiday.name

    return False, None

def calculate_working_days(start_date, end_date):
    """Calculate working days between two dates, excluding weekends and holidays"""
    if start_date > end_date:
        return 0

    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        is_non_working, reason = is_holiday_or_weekend(current_date)
        if not is_non_working:
            working_days += 1
        current_date += date.resolution  # Add one day

    return working_days