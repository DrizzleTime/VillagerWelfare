import os
from app import app, db
from models import User


def init_database():
    db_path = 'data.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"已删除旧数据库文件: {db_path}")

    with app.app_context():
        # 创建所有表
        db.create_all()
        print("已创建新的数据库表")

        # 检查是否已存在管理员账户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # 创建默认管理员账户
            admin = User(
                username='admin',
                password='admin',
                role='管理员',
                area='全区'
            )
            db.session.add(admin)
            db.session.commit()
            print("已创建默认管理员账户")
        else:
            print("管理员账户已存在，跳过创建")


if __name__ == '__main__':
    init_database()
