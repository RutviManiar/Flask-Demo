from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, Announcement, AnnouncementComment, Emp
from datetime import datetime

announcement_bp = Blueprint('announcement', __name__)


@announcement_bp.route('/announcements')
def list_announcements():
    """List all announcements"""
    page = request.args.get('page', 1, type=int)
    announcements = (
        Announcement.query
        .filter_by(is_deleted=False)
        .order_by(Announcement.created_at.desc())
        .paginate(page=page, per_page=10)
    )
    return render_template('announcement/announcements.html', announcements=announcements)


@announcement_bp.route('/announcement/<int:announcement_id>')
def view_announcement(announcement_id):
    """View single announcement with comments"""
    announcement = Announcement.query.filter_by(
        id=announcement_id, 
        is_deleted=False
    ).first_or_404()
    
    # Get top-level comments (parent_id is None)
    comments = (
        AnnouncementComment.query
        .filter_by(announcement_id=announcement_id, is_deleted=False, parent_id=None)
        .order_by(AnnouncementComment.created_at.desc())
        .all()
    )
    
    return render_template(
        'announcement/view.html',
        announcement=announcement,
        comments=comments
    )


@announcement_bp.route('/announcement/add', methods=['GET', 'POST'])
def add_announcement():
    """Create new announcement (admin only)"""
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user or user.role != 'admin':
        flash('You do not have permission to create announcements.', 'danger')
        return redirect(url_for('announcement.list_announcements'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('announcement.add_announcement'))
        
        new_announcement = Announcement(
            title=title,
            content=content,
            created_by=user_id
        )
        db.session.add(new_announcement)
        db.session.commit()
        
        flash('Announcement created successfully!', 'success')
        return redirect(url_for('announcement.view_announcement', announcement_id=new_announcement.id))
    
    return render_template('announcement/add.html')


@announcement_bp.route('/announcement/<int:announcement_id>/edit', methods=['GET', 'POST'])
def edit_announcement(announcement_id):
    """Edit announcement (creator/admin only)"""
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        is_deleted=False
    ).first_or_404()
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user or (announcement.created_by != user_id and user.role != 'admin'):
        flash('You do not have permission to edit this announcement.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    if request.method == 'POST':
        announcement.title = request.form.get('title', '').strip()
        announcement.content = request.form.get('content', '').strip()
        announcement.updated_at = datetime.utcnow()
        
        if not announcement.title or not announcement.content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('announcement.edit_announcement', announcement_id=announcement_id))
        
        db.session.commit()
        flash('Announcement updated successfully!', 'success')
        return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    return render_template('announcement/edit.html', announcement=announcement)


@announcement_bp.route('/announcement/<int:announcement_id>/delete', methods=['POST'])
def delete_announcement(announcement_id):
    """Soft delete announcement (creator/admin only)"""
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        is_deleted=False
    ).first_or_404()
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user or (announcement.created_by != user_id and user.role != 'admin'):
        flash('You do not have permission to delete this announcement.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    announcement.is_deleted = True
    db.session.commit()
    flash('Announcement deleted successfully!', 'success')
    return redirect(url_for('announcement.list_announcements'))


# ============ COMMENTS ============

@announcement_bp.route('/announcement/<int:announcement_id>/comment/add', methods=['POST'])
def add_comment(announcement_id):
    """Add a comment to an announcement"""
    announcement = Announcement.query.filter_by(
        id=announcement_id,
        is_deleted=False
    ).first_or_404()
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to comment.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    message = request.form.get('message', '').strip()
    parent_id = request.form.get('parent_id', type=int, default=None)
    
    if not message:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    # If parent_id is provided, verify it exists and belongs to this announcement
    if parent_id:
        parent_comment = AnnouncementComment.query.filter_by(
            id=parent_id,
            announcement_id=announcement_id,
            is_deleted=False
        ).first()
        if not parent_comment:
            flash('Parent comment not found.', 'danger')
            return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
    
    new_comment = AnnouncementComment(
        announcement_id=announcement_id,
        emp_id=user_id,
        message=message,
        parent_id=parent_id
    )
    db.session.add(new_comment)
    db.session.commit()
    
    flash('Comment added successfully!', 'success')
    return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))


@announcement_bp.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
def edit_comment(comment_id):
    """Edit a comment (commenter/admin only)"""
    comment = AnnouncementComment.query.filter_by(
        id=comment_id,
        is_deleted=False
    ).first_or_404()
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user or (comment.emp_id != user_id and user.role != 'admin'):
        flash('You do not have permission to edit this comment.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=comment.announcement_id))
    
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        
        if not message:
            flash('Comment cannot be empty.', 'danger')
            return redirect(url_for('edit_comment', comment_id=comment_id))
        
        comment.message = message
        comment.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Comment updated successfully!', 'success')
        return redirect(url_for('announcement.view_announcement', announcement_id=comment.announcement_id))
    
    return render_template('announcement/edit_comment.html', comment=comment)


@announcement_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    """Soft delete a comment (commenter/admin only)"""
    comment = AnnouncementComment.query.filter_by(
        id=comment_id,
        is_deleted=False
    ).first_or_404()
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    
    user = Emp.query.filter_by(eno=user_id, is_deleted=False).first()
    if not user or (comment.emp_id != user_id and user.role != 'admin'):
        flash('You do not have permission to delete this comment.', 'danger')
        return redirect(url_for('announcement.view_announcement', announcement_id=comment.announcement_id))
    
    announcement_id = comment.announcement_id
    comment.is_deleted = True
    db.session.commit()
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('announcement.view_announcement', announcement_id=announcement_id))
