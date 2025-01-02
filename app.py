from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User
from residents import residents_bp
from welfare import welfare_bp
from education import education_bp
from export import export_bp
from import_data import import_bp  # 添加导入

app = Flask(__name__)
app.secret_key = 'asd'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            flash('登录成功', 'success')
            return redirect(url_for('residents.residents'))
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('您已退出系统', 'info')
    return redirect(url_for('login'))


app.register_blueprint(residents_bp, url_prefix='/residents')
app.register_blueprint(welfare_bp, url_prefix='/welfare')
app.register_blueprint(education_bp, url_prefix='/education')
app.register_blueprint(export_bp, url_prefix='/export')
app.register_blueprint(import_bp, url_prefix='/import')  # 添加这行

if __name__ == '__main__':
    app.run(debug=True)
