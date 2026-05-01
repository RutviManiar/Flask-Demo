from models import db

class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp = db.Column(db.Integer, db.ForeignKey('emp.eno'), nullable=False)
    month = db.Column(db.String(10))
    year = db.Column(db.Integer)

    base_salary = db.Column(db.Float)
    present_days = db.Column(db.Integer)
    total_days = db.Column(db.Integer)
    net_salary = db.Column(db.Float)

    employee = db.relationship('Emp', backref='payroll')
    __table_args__ = (
    db.UniqueConstraint('emp', 'month', 'year', name='unique_payroll'),
)