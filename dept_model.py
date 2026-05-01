from models import db

class Dept(db.Model):
    __tablename__ = "dept"
    __table_args__ = (
        db.CheckConstraint("created_date <= CURRENT_DATE", name="ck_created_date_not_future"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dname = db.Column(db.String(20), nullable=False)
    loc = db.Column(db.String(20), nullable=True)
    created_date = db.Column(db.Date, default=db.func.current_date())
    is_deleted = db.Column(db.Boolean, default=False)  # For soft delete
    
    # Correct backref name — should describe the relationship to Emp
    employees = db.relationship("Emp", backref="department", lazy=True)

    def __repr__(self):
        return f"<Department {self.id} {self.dname} {self.loc}>"