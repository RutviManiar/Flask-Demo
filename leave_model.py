from models import db
from datetime import datetime

class Leave(db.Model):
    __tablename__ = "leave"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("emp.eno"), nullable=False)
    leave_type = db.Column(db.Enum('annual', 'sick', 'personal', 'maternity', 'paternity', name='leave_type_enum'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days_requested = db.Column(db.Float, nullable=False)  # Changed to Float to support half days
    is_half_day = db.Column(db.Boolean, default=False)  # New field for half-day leave
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum('pending', 'approved', 'rejected', name='leave_status_enum'), nullable=False, default='pending')
    applied_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey("emp.eno"), nullable=True)
    approved_date = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    employee = db.relationship('Emp', foreign_keys=[employee_id], backref='leaves')
    approver = db.relationship('Emp', foreign_keys=[approved_by], backref='approved_leaves')

    def __repr__(self):
        return f"<Leave {self.id} {self.employee.ename} {self.leave_type} {self.status}>"