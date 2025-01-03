import os
from app import app, db
from models import User
import argparse
from datetime import datetime


def create_user(username, password, role, area):
    """创建新用户"""
    try:
        user = User(
            username=username,
            password=password,
            role=role,
            area=area,
            registered_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        print(f"用户 {username} 创建成功。")
    except Exception as e:
        db.session.rollback()
        print(f"创建用户失败：{str(e)}")


def update_user(user_id, username=None, password=None, role=None, area=None):
    """更新用户信息"""
    user = User.query.get(user_id)
    if user:
        try:
            if username:
                user.username = username
            if password:
                user.password = password
            if role:
                user.role = role
            if area:
                user.area = area
            db.session.commit()
            print(f"用户 {user_id} 更新成功。")
        except Exception as e:
            db.session.rollback()
            print(f"更新用户失败：{str(e)}")
    else:
        print(f"未找到ID为 {user_id} 的用户。")


def delete_user(user_id):
    """删除用户"""
    user = User.query.get(user_id)
    if user:
        try:
            db.session.delete(user)
            db.session.commit()
            print(f"用户 {user_id} 删除成功。")
        except Exception as e:
            db.session.rollback()
            print(f"删除用户失败：{str(e)}")
    else:
        print(f"未找到ID为 {user_id} 的用户。")


def get_user(user_id):
    """查询用户信息"""
    user = User.query.get(user_id)
    if user:
        print(f"用户ID: {user.id}")
        print(f"用户名: {user.username}")
        print(f"角色: {user.role}")
        print(f"工区: {user.area}")
        print(f"注册时间: {user.registered_at}")
        print(f"最后登录: {user.last_login}")
    else:
        print(f"未找到ID为 {user_id} 的用户。")


def list_all_users():
    """显示所有用户列表"""
    users = User.query.all()
    if users:
        print("\n当前所有用户:")
        print("ID\t用户名\t角色\t工区")
        print("-" * 40)
        for user in users:
            print(f"{user.id}\t{user.username}\t{user.role}\t{user.area}")
    else:
        print("当前没有任何用户。")


def show_menu():
    """显示主菜单"""
    print("\n=== 用户管理系统 ===")
    print("1. 创建用户")
    print("2. 更新用户")
    print("3. 删除用户")
    print("4. 查询用户")
    print("0. 退出系统")
    print("================")


if __name__ == "__main__":
    with app.app_context():
        while True:
            show_menu()
            choice = input("请输入操作选项 (0-4): ")

            if choice == "0":
                print("再见！")
                break

            elif choice == "1":
                print("\n=== 创建新用户 ===")
                username = input("请输入用户名: ")
                password = input("请输入密码: ")
                print("\n请选择用户角色:")
                print("1. 管理员")
                print("2. 普通用户")
                role_choice = input("请输入角色选项 (1-2): ")
                role = "管理员" if role_choice == "1" else "普通用户"
                area = input("请输入工区: ")

                if all([username, password, role, area]):
                    create_user(username, password, role, area)
                else:
                    print("错误：所有字段都必须填写！")

            elif choice == "2":
                print("\n=== 更新用户信息 ===")
                user_id = input("请输入要更新的用户ID: ")
                if not user_id.isdigit():
                    print("错误：用户ID必须是数字！")
                    continue

                print("请输入要更新的信息(不更新的项目请直接按回车):")
                username = input("新用户名: ").strip() or None
                password = input("新密码: ").strip() or None
                print("\n角色选项:")
                print("1. 管理员")
                print("2. 普通用户")
                role_choice = input("新角色 (1-2，直接回车跳过): ").strip()
                role = None
                if role_choice == "1":
                    role = "管理员"
                elif role_choice == "2":
                    role = "普通用户"
                area = input("新工区: ").strip() or None

                update_user(int(user_id), username, password, role, area)

            elif choice == "3":
                print("\n=== 删除用户 ===")
                user_id = input("请输入要删除的用户ID: ")
                if user_id.isdigit():
                    confirm = input(f"确认要删除ID为 {user_id} 的用户吗？(y/n): ")
                    if confirm.lower() == 'y':
                        delete_user(int(user_id))
                else:
                    print("错误：用户ID必须是数字！")

            elif choice == "4":
                print("\n=== 查询用户 ===")
                # 先显示所有用户列表
                list_all_users()
                print("\n请选择操作：")
                print("1. 查询指定用户详细信息")
                print("2. 返回主菜单")
                sub_choice = input("请输入选项 (1-2): ")

                if sub_choice == "1":
                    user_id = input("请输入要查询的用户ID: ")
                    if user_id.isdigit():
                        get_user(int(user_id))
                    else:
                        print("错误：用户ID必须是数字！")
                elif sub_choice == "2":
                    continue
                else:
                    print("无效的选项！")

            else:
                print("无效的选项，请重新选择！")

            input("\n按回车键继续...")
