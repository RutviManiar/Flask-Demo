from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models from separate files
from dept_model import Dept
from emp_model import Emp
from att_model import Att
from payroll_model import Payroll
from announcement_model import Announcement, AnnouncementComment
from leave_model import Leave
from holiday_model import Holiday

