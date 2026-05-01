# 📢 Announcement Discussion System - User Guide

## Overview
The Flask app now has a complete announcement discussion system with:
- **Admin posts** → **Employees read and discuss**
- **Threaded comments** (replies to comments)
- **Soft deletes** (comments can be removed)
- **Chat-like interface** (easy to follow conversations)

---

## 🎯 Quick Start

### For Admins
1. Go to **"📢 Announcements"** in the navbar
2. Click **"Create New Announcement"** (only visible to admins)
3. Fill in title and content
4. Click **"Publish Announcement"**

### For All Employees
1. Go to **"📢 Announcements"** in the navbar
2. Click on any announcement to read it
3. Scroll down to **"Comments"** section
4. Add your thoughts in the comment box
5. Click **"Reply"** on any comment to start a discussion thread

---

## 🗂️ File Structure

```
templates/announcement/
├── announcements.html      # List all announcements (paginated)
├── view.html              # View announcement + discussions
├── add.html               # Create new announcement (admin)
├── edit.html              # Edit announcement (admin/creator)
└── edit_comment.html      # Edit comment

announcement_model.py      # Database models
announcement_routes.py     # All routes (CRUD + comments)
```

---

## 🛠️ Features Breakdown

### Announcements (CRUD)
| Feature | Accessible By |
|---------|--------------|
| Create | Admin only |
| Read | All logged-in users |
| Edit | Admin + Creator |
| Delete | Admin + Creator |

### Comments & Replies
| Feature | Accessible By |
|---------|--------------|
| Add comment | All logged-in users |
| Reply to comment | All logged-in users |
| Edit own | Commenter + Admin |
| Delete own | Commenter + Admin |

---

## 📊 Database Schema

### Announcement Table
```
id (PK)
title (VARCHAR)
content (TEXT)
created_by (FK to Emp.eno)
created_at (DATETIME)
updated_at (DATETIME)
is_deleted (BOOLEAN)
```

### AnnouncementComment Table
```
id (PK)
announcement_id (FK)
emp_id (FK)
message (TEXT)
parent_id (FK - for threading)  ← Reply to reply!
created_at (DATETIME)
updated_at (DATETIME)
is_deleted (BOOLEAN)
```

---

## 🔄 Comment Threading Example

```
Admin: Office closed tomorrow
 └─ Employee1: Why?
     └─ Admin: Building maintenance
         └─ Employee1: Thanks for info!
 └─ Employee2: Will we work remotely?
     └─ Admin: No, it's a complete closure
```

---

## 🎨 UI Preview

### List View
- Announcement cards with title, excerpt, comment count
- Pagination (10 per page)
- Edit/Delete buttons for admins

### Detail View
- Full announcement text
- Comments displayed like a chat
- Indented replies (nested threads)
- Edit/Delete buttons for comment authors
- Badges showing:
  - "Edited" if comment was modified
  - Comment count at top

---

## 🔐 Security & Permissions

✅ **Implemented**
- Soft deletes (data never truly lost)
- Admin moderation (can delete any comment)
- Permission checks on every route
- User can only see/edit their own comments
- Only admins can create announcements

---

## 🚀 Future Enhancement Ideas (Not Implemented)

Level 3 features you could add:
1. **Likes/Reactions** - Emoji reactions to comments
2. **Notifications** - Email when someone replies to your comment
3. **Pinned Comments** - Admin highlights important replies
4. **Toxic Word Filter** - Auto-flag inappropriate language
5. **Question Detection** - Auto-mark comments with "?" as questions

---

## 🧪 Testing

### Manual Testing Steps
1. **As Admin:**
   - Create 2-3 announcements
   - Edit one announcement
   - Add comments as admin and regular users
   - Try to delete a comment

2. **As Employee:**
   - Read announcements
   - Add comment
   - Reply to a comment
   - Edit your own comment
   - Try to edit someone else's (should fail)

3. **Edge Cases:**
   - Try to access edit page directly (should 404)
   - Create empty comment (should flash error)
   - Try to delete from another user's comment (should deny)

---

## 📝 Database Migration

Migration file: `a51f4f488e9e_add_announcements_and_comments.py`

Already applied! ✅

If you need to rollback:
```bash
flask db downgrade -1  # Removes announcement tables
```

To reapply:
```bash
flask db upgrade       # Re-creates tables
```

---

## 🎯 What Wasn't Changed

- ✅ DeepFace face login (untouched)
- ✅ All existing routes work as before
- ✅ No employee/department data affected
- ✅ Payroll system unchanged

Everything is backward compatible!

---

## 💡 Tips

- Admins should create announcements regularly for company updates
- Use reply feature to address employee questions publicly
- Delete inappropriate comments to keep discussions professional
- The comment count badge makes it easy to see active discussions

---

**Questions?** Check the implementation files:
- Routes logic: `announcement_routes.py`
- Database schema: `announcement_model.py`
- UI code: `templates/announcement/*.html`
