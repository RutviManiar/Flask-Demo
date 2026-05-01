from models import db
from datetime import datetime


class Announcement(db.Model):
    __tablename__ = "announcement"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('emp.eno'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Relationships
    creator = db.relationship('Emp', backref='announcements')
    comments = db.relationship(
        'AnnouncementComment', 
        backref='announcement', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<Announcement {self.id} - {self.title}>"
    
    def get_comment_count(self):
        """Get count of non-deleted comments"""
        return self.comments.filter_by(is_deleted=False).count()


class AnnouncementComment(db.Model):
    __tablename__ = "announcement_comment"
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    announcement_id = db.Column(
        db.Integer, db.ForeignKey('announcement.id'), nullable=False
    )
    emp_id = db.Column(
        db.Integer, db.ForeignKey('emp.eno'), nullable=False
    )
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # For threaded replies
    parent_id = db.Column(
        db.Integer, db.ForeignKey('announcement_comment.id'), nullable=True
    )
    
    # Relationships
    employee = db.relationship('Emp', backref='announcement_comments')
    replies = db.relationship(
        'AnnouncementComment',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic',
        foreign_keys=[parent_id],
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<Comment {self.id} on Announcement {self.announcement_id}>"
    
    def get_replies(self):
        """Get non-deleted replies to this comment"""
        return self.replies.filter_by(is_deleted=False).all()
