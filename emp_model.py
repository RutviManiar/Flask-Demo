from models import db

class Emp(db.Model):
    __tablename__ = "emp"
    eno = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ename = db.Column(db.String(20), nullable=False)
    sal = db.Column(db.Float, nullable=True, default=0)
    deptid = db.Column(db.Integer, db.ForeignKey("dept.id"))
    is_deleted = db.Column(db.Boolean, default=False)  # For soft delete
    email = db.Column(db.String(50), nullable=True, unique=True)  # New email field (must be unique)
    phone = db.Column(db.String(15), nullable=True)  # New phone field
    password = db.Column(db.String(255), nullable=True)  # New password field (should be hashed in production)
    role = db.Column(
        db.Enum('user', 'admin', name='role_enum'),
        nullable=False,
        server_default='user',
        default='user',
    )  # Role: 'admin' or 'user' (enforced at DB level)
    # Use MEDIUMBLOB in MySQL so larger images can be stored (default BLOB is limited to 64KB).
    # If you plan to store very large files, you can use LONGBLOB instead.
    image = db.Column(db.LargeBinary(length=(2**24 - 1)), nullable=True)  # ~16MB
    def __repr__(self):
        return f"<Employee {self.eno} {self.ename} {self.sal} Dept:{self.deptid}>"