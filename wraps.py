from functools import wraps
from flask import flash, redirect, session, url_for, jsonify, request
from models import User, Villager


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


def area_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') == '管理员':
            return f(*args, **kwargs)
            
        user_areas = User.query.get(session['user_id']).area.split(',')
        
        # 如果路由参数中有 villager_id，检查该村民的区域权限
        villager_id = kwargs.get('id') or request.view_args.get('id') or request.args.get('villager_id')
        if villager_id:
            resident = Villager.query.get_or_404(villager_id)
            if resident.area not in user_areas:
                # 使用 Accept 头或 X-Requested-With 头来检测 AJAX 请求
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                   'application/json' in request.accept_mimetypes:
                    return jsonify({'error': '无权访问该村民信息'}), 403
                flash('无权访问该区域村民信息', 'danger')
                return redirect(url_for('residents.residents'))
                
        return f(*args, **kwargs)
    return decorated_function
