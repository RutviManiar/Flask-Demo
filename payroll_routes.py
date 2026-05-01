import io
import os
import re
from urllib.parse import quote

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from fpdf import FPDF
from models import db, Emp, Att, Payroll
import calendar
from datetime import datetime

payroll_bp = Blueprint('payroll', __name__)


def _get_pdf_directory() -> str:
    pdf_dir = os.path.join(current_app.root_path, 'pdfs')
    os.makedirs(pdf_dir, exist_ok=True)
    return pdf_dir


def _build_payroll_pdf(payroll: Payroll) -> bytes:
    employee = Emp.query.get(payroll.emp)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Payroll Invoice', ln=True, align='C')
    pdf.ln(8)

    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Employee: {employee.ename}', ln=True)
    pdf.cell(0, 8, f'Employee ID: {employee.eno}', ln=True)
    pdf.cell(0, 8, f'Month / Year: {payroll.month} {payroll.year}', ln=True)
    pdf.cell(0, 8, f'Department: {employee.department.dname if employee.department else "Unassigned"}', ln=True)
    pdf.ln(4)

    pdf.cell(0, 8, f'Base Salary: {payroll.base_salary:.2f}', ln=True)
    pdf.cell(0, 8, f'Total Days: {payroll.total_days}', ln=True)
    pdf.cell(0, 8, f'Present Days: {payroll.present_days}', ln=True)
    pdf.cell(0, 8, f'Net Salary: {payroll.net_salary:.2f}', ln=True)
    pdf.ln(8)

    pdf.multi_cell(0, 8, 'This invoice is generated automatically by the payroll system. Please verify the details with HR if anything looks incorrect.')
    pdf.ln(6)
    pdf.cell(0, 8, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', ln=True)

    return pdf.output(dest='S').encode('latin-1')


def _save_payroll_pdf(payroll: Payroll) -> str:
    pdf_dir = _get_pdf_directory()
    filename = f'payroll_{payroll.id}.pdf'
    path = os.path.join(pdf_dir, filename)
    with open(path, 'wb') as f:
        f.write(_build_payroll_pdf(payroll))
    return path


def _get_payroll_pdf_url(payroll_id: int) -> str:
    return url_for('payroll.download_payroll_invoice', id=payroll_id, _external=True)


def _normalize_whatsapp_phone(phone: str) -> str | None:
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    return digits if digits else None


@payroll_bp.route('/payroll/generate', methods=['GET', 'POST'])
def generate_payroll():
    emps = Emp.query.filter_by(is_deleted=False).all()
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 1))  # Last 5 years + current year
    
    error = None


    if request.method == 'POST':
        emp = int(request.form['emp'])
        month = request.form['month']
        year = int(request.form['year'])

        existing = Payroll.query.filter_by(
            emp=emp,
            month=month,
            year=year
        ).first()

        if existing:
            flash("Payroll already generated for this employee!", "warning")
            return redirect(url_for('payroll.generate_payroll'))

        # Get attendance
        att = Att.query.filter_by(emp_id=emp, month=month, year=year).first()

        if not att:
            flash("Attendance not found!", "danger")
            return redirect(url_for('payroll.generate_payroll'))

        emp = Emp.query.get(emp)

        base_salary = emp.sal
        present_days = att.present_days

        # Get total days in month
        month_number = list(calendar.month_name).index(month)
        total_days = calendar.monthrange(year, month_number)[1]

        net_salary = (base_salary / total_days) * present_days
        
        payroll = Payroll(
            emp=emp.eno,
            month=month,
            year=year,
            base_salary=base_salary,
            present_days=present_days,
            total_days=total_days,
            net_salary=net_salary
        )

        db.session.add(payroll)
        db.session.commit()
        _save_payroll_pdf(payroll)

        flash("Payroll generated and invoice created!", "success")
        return redirect(url_for('payroll.list_payroll'))

    return render_template('payroll/payroll_form.html', emps=emps, years=years, action="Generate", error=error)

@payroll_bp.route('/payroll')
def list_payroll():
    records = Payroll.query.all()
    return render_template('payroll/list.html', records=records)

@payroll_bp.route('/payroll/<int:id>/invoice.pdf')
def download_payroll_invoice(id):
    payroll = Payroll.query.get_or_404(id)
    filename = f'payroll_{id}.pdf'
    pdf_dir = _get_pdf_directory()
    path = os.path.join(pdf_dir, filename)
    if not os.path.exists(path):
        _save_payroll_pdf(payroll)

    return send_file(path, mimetype='application/pdf', as_attachment=True, download_name=filename)

@payroll_bp.route('/payroll/<int:id>/share')
def share_payroll_whatsapp(id):
    payroll = Payroll.query.get_or_404(id)
    phone = _normalize_whatsapp_phone(payroll.employee.phone)
    if not phone:
        flash('Employee phone number missing; cannot open WhatsApp chat.', 'danger')
        return redirect(url_for('payroll.list_payroll'))

    text = (
        f"Hello {payroll.employee.ename}, your payroll invoice for {payroll.month} {payroll.year} "
        "has been generated. Please check your WhatsApp messages for the attached invoice."
    )
    whatsapp_url = f'https://api.whatsapp.com/send?phone={phone}&text={quote(text)}'
    return redirect(whatsapp_url)

@payroll_bp.route('/payroll/delete/<int:id>')
def delete_payroll(id):
    payroll = Payroll.query.get_or_404(id)
    db.session.delete(payroll)
    db.session.commit()
    flash('Payroll record deleted successfully!', 'success')
    return redirect(url_for('payroll.list_payroll'))

@payroll_bp.route('/payroll/edit/<int:id>', methods=['GET', 'POST'])
def edit_payroll(id):
    payroll = Payroll.query.get_or_404(id)
    emps = Emp.query.filter_by(is_deleted=False).all()
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 1))

    if request.method == 'POST':
        emp_id = int(request.form['emp'])
        month = request.form['month']
        year = int(request.form['year'])

        # 🔹 Duplicate check (exclude current record)
        existing = Payroll.query.filter(
            Payroll.emp == emp_id,
            Payroll.month == month,
            Payroll.year == year,
            Payroll.id != id   # IMPORTANT 🔥
        ).first()

        if existing:
            flash("Payroll already exists for this employee!", "warning")
            return redirect(url_for('payroll.list_payroll'))

        # 🔹 Attendance check
        att = Att.query.filter_by(
            emp_id=emp_id,
            month=month,
            year=year
        ).first()

        if not att:
            flash("Attendance not found!", "danger")
            return redirect(url_for('payroll.list_payroll'))

        emp = Emp.query.get(emp_id)

        # 🔹 Update payroll fields
        payroll.emp = emp_id
        payroll.month = month
        payroll.year = year
        payroll.base_salary = emp.sal
        payroll.present_days = att.present_days

        import calendar
        month_number = list(calendar.month_name).index(month)
        payroll.total_days = calendar.monthrange(year, month_number)[1]

        payroll.net_salary = (payroll.base_salary / payroll.total_days) * payroll.present_days

        db.session.commit()

        flash('Payroll record updated successfully!', 'success')
        return redirect(url_for('payroll.list_payroll'))
    
    return render_template('payroll/payroll_form.html', emps=emps, years=years, action="Edit", error=None, payroll=payroll)