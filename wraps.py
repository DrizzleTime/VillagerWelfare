
from functools import wraps

from flask import flash, redirect, session, url_for


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != '管理员':
            flash('权限不足', 'danger')
            return redirect(url_for('residents.residents'))
        return f(*args, **kwargs)

    return decorated_function
