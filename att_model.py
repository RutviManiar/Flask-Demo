from models import db
from datetime import date

class Att(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.Integer, db.ForeignKey('emp.eno'), nullable=False)
    month = db.Column(db.String(10))   # e.g., "March"
    year = db.Column(db.Integer)
    present_days = db.Column(db.Integer)

    employee = db.relationship('Emp', backref='att')
__table_args__ = (
    db.UniqueConstraint('emp_id', 'month', 'year', name='unique_attendance'),
)