from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import db, Leave, Emp
from datetime import datetime, date
from sqlalchemy import func
from holiday_routes import is_holiday_or_weekend

leave_bp = Blueprint('leave', __name__)

# Leave balance configuration (can be made configurable later)
LEAVE_BALANCE = {
    'annual': 25,  # 25 days per year
    'sick': 10,    # 10 days per year
    'personal': 5, # 5 days per year
    'maternity': 90, # 90 days
    'paternity': 15  # 15 days
}

def get_leave_balance(employee_id, leave_type):
    """Calculate remaining leave balance for an employee"""
    current_year = datetime.now().year

    # Get approved leaves for current year
    used_leaves = Leave.query.filter(
        Leave.employee_id == employee_id,
        Leave.leave_type == leave_type,
        Leave.status == 'approved',
        func.year(Leave.start_date) == current_year,
        Leave.is_deleted == False
    ).with_entities(func.sum(Leave.days_requested)).scalar() or 0

    total_balance = LEAVE_BALANCE.get(leave_type, 0)
    return max(0, total_balance - used_leaves)

@leave_bp.route('/leaves')
def list_leaves():
    """List leaves - different views for admin and employee"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role == 'admin':
        # Admin sees all leaves
        leaves = Leave.query.filter_by(is_deleted=False).order_by(Leave.applied_date.desc()).all()
        # Calculate own leave balances
        balances = {}
        for leave_type in LEAVE_BALANCE.keys():
            balances[leave_type] = get_leave_balance(user_id, leave_type)
        return render_template('leave/leaves.html', leaves=leaves, is_admin=True, balances=balances)
    else:
        # Employee sees only their own leaves
        leaves = Leave.query.filter_by(employee_id=user_id, is_deleted=False).order_by(Leave.applied_date.desc()).all()
        # Calculate leave balances
        balances = {}
        for leave_type in LEAVE_BALANCE.keys():
            balances[leave_type] = get_leave_balance(user_id, leave_type)
        return render_template('leave/leaves.html', leaves=leaves, is_admin=False, balances=balances)

@leave_bp.route('/leave/<int:leave_id>')
def view_leave(leave_id):
    """View detailed leave application information"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    leave = Leave.query.filter_by(id=leave_id, is_deleted=False).first()
    if not leave:
        flash('Leave application not found', 'danger')
        return redirect(url_for('leave.list_leaves'))

    if current_user.role != 'admin' and leave.employee_id != user_id:
        abort(403)

    return render_template('leave/view_leave.html', leave=leave, is_admin=(current_user.role == 'admin'))

@leave_bp.route('/leave/apply', methods=['GET', 'POST'])
def apply_leave():
    """Apply for leave"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if request.method == 'POST':
        leave_type = request.form['leave_type']
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        is_half_day = request.form.get('is_half_day') == 'on'
        reason = request.form.get('reason', '')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('leave.apply_leave'))

        if start_date > end_date:
            flash('End date must be on or after start date', 'danger')
            return redirect(url_for('leave.apply_leave'))

        if start_date < date.today():
            flash('Cannot apply for leave in the past', 'danger')
            return redirect(url_for('leave.apply_leave'))

        # Calculate days requested (working days only, excluding weekends and holidays)
        current_date = start_date
        working_days = 0
        non_working_dates = []

        while current_date <= end_date:
            is_non_working, reason = is_holiday_or_weekend(current_date)
            if is_non_working:
                non_working_dates.append(f"{current_date.strftime('%Y-%m-%d')} ({reason})")
            else:
                working_days += 1
            current_date += date.resolution

        # For single day leave, check if it's half day
        if start_date == end_date:
            # Check if the single day is a working day
            is_non_working, reason = is_holiday_or_weekend(start_date)
            if is_non_working:
                flash(f'Cannot apply for leave on {reason}', 'danger')
                return redirect(url_for('leave.apply_leave'))
            days_requested = 0.5 if is_half_day else 1.0
        else:
            # Multi-day leave - use working days
            days_requested = working_days
            if is_half_day:
                flash('Half-day option is only available for single-day leave', 'warning')
                return redirect(url_for('leave.apply_leave'))

        # Show information about non-working days
        if non_working_dates:
            flash(f'Leave period includes {len(non_working_dates)} non-working day(s): {", ".join(non_working_dates)}. Only {working_days} working day(s) will be deducted from your leave balance.', 'info')

        # Check leave balance
        balance = get_leave_balance(user_id, leave_type)
        if days_requested > balance:
            flash(f'Insufficient leave balance. You have {balance} days remaining for {leave_type} leave.', 'danger')
            return redirect(url_for('leave.apply_leave'))

        # Create leave application
        leave = Leave(
            employee_id=user_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            days_requested=days_requested,
            is_half_day=is_half_day,
            reason=reason
        )

        db.session.add(leave)
        db.session.commit()

        flash('Leave application submitted successfully', 'success')
        return redirect(url_for('leave.list_leaves'))

    # Calculate leave balances for display
    balances = {}
    for leave_type in LEAVE_BALANCE.keys():
        balances[leave_type] = get_leave_balance(user_id, leave_type)

    return render_template('leave/apply_leave.html', balances=balances, today=date.today().isoformat(), is_admin=(current_user.role == 'admin'))

@leave_bp.route('/leave/<int:leave_id>/approve', methods=['POST'])
def approve_leave(leave_id):
    """Approve a leave application (admin only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role != 'admin':
        abort(403)

    leave = Leave.query.filter_by(id=leave_id, is_deleted=False).first()
    if not leave:
        flash('Leave application not found', 'danger')
        return redirect(url_for('leave.list_leaves'))

    if leave.status != 'pending':
        flash('Leave application has already been processed', 'warning')
        return redirect(url_for('leave.list_leaves'))
    
    # Prevent admin from approving their own leave
    if leave.employee_id == user_id:
        flash('You cannot approve your own leave application. Please ask another admin to approve it.', 'danger')
        return redirect(url_for('leave.list_leaves'))

    leave.status = 'approved'
    leave.approved_by = user_id
    leave.approved_date = datetime.utcnow()

    db.session.commit()
    flash('Leave application approved', 'success')
    return redirect(url_for('leave.list_leaves'))

@leave_bp.route('/leave/<int:leave_id>/reject', methods=['GET', 'POST'])
def reject_leave(leave_id):
    """Reject a leave application (admin only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    if current_user.role != 'admin':
        abort(403)

    leave = Leave.query.filter_by(id=leave_id, is_deleted=False).first()
    if not leave:
        flash('Leave application not found', 'danger')
        return redirect(url_for('leave.list_leaves'))

    if leave.status != 'pending':
        flash('Leave application has already been processed', 'warning')
        return redirect(url_for('leave.list_leaves'))
    
    # Prevent admin from rejecting their own leave
    if leave.employee_id == user_id:
        flash('You cannot reject your own leave application. Please ask another admin to process it.', 'danger')
        return redirect(url_for('leave.list_leaves'))

    if request.method == 'POST':
        rejection_reason = request.form.get('rejection_reason', '')

        leave.status = 'rejected'
        leave.approved_by = user_id
        leave.approved_date = datetime.utcnow()
        leave.rejection_reason = rejection_reason

        db.session.commit()
        flash('Leave application rejected', 'success')
        return redirect(url_for('leave.list_leaves'))

    return render_template('leave/reject_leave.html', leave=leave)

@leave_bp.route('/leave/<int:leave_id>/cancel', methods=['POST'])
def cancel_leave(leave_id):
    """Cancel a leave application (employee only)"""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    current_user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()

    leave = Leave.query.filter_by(id=leave_id, employee_id=user_id, is_deleted=False).first()
    if not leave:
        flash('Leave application not found', 'danger')
        return redirect(url_for('leave.list_leaves'))

    if leave.status != 'pending':
        flash('Cannot cancel a processed leave application', 'warning')
        return redirect(url_for('leave.list_leaves'))

    leave.is_deleted = True
    db.session.commit()
    flash('Leave application cancelled', 'success')
    return redirect(url_for('leave.list_leaves'))