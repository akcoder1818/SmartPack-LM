"""
Authentication and Role-Based Access Control Module
SmartPack-LM: Legal Metrology Compliance Inspection Platform
SIH26034 | Ministry of Consumer Affairs
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request
from utils.database import get_user_by_id

def get_current_user():
    """Returns the authenticated user dict from session, or None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if not user or user.get('status') != 'ACTIVE':
        # If user was deactivated or deleted while session was alive
        return None
    return user

def login_required(f):
    """Decorator to require an active logged-in user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please sign in to access this portal section.", "warning")
            return redirect(url_for('login', next=request.url))
        user = get_current_user()
        if not user:
            session.clear()
            flash("Your session has expired or your account is deactivated. Please sign in again.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to restrict route strictly to ADMIN role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Administrator authentication required.", "warning")
            return redirect(url_for('login', next=request.url))
        user = get_current_user()
        if not user or user.get('role') != 'ADMIN':
            flash("Access denied: Administrative privileges required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function
