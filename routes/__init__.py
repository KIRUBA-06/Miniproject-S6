from functools import wraps
from flask import abort
from flask_login import current_user


def student_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role != "student":
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role != "admin":
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


def faculty_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role != "faculty":
            abort(403)
        return view_func(*args, **kwargs)
    return wrapped


# Backward compatible alias.
mentor_required = admin_required
