from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.Enum('管理员', '普通用户'), default='普通用户', nullable=False)
    area = db.Column(db.String(50), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)


class HouseholdHead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_number = db.Column(db.String(50), unique=True, nullable=False)
    head_id = db.Column(db.Integer, db.ForeignKey(
        'villager.id'), nullable=False)
    head = db.relationship(
        'Villager', back_populates='as_head', foreign_keys=[head_id])  # 修改
    members = db.relationship('Villager', back_populates='household_head',
                              foreign_keys='Villager.household_head_id')  # 修改
    address_group = db.Column(db.String(50), nullable=False)  # 保持不变


class Villager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # 基本信息
    name = db.Column(db.String(50), nullable=False, index=True)
    id_card = db.Column(db.String(18), unique=True, nullable=False, index=True)
    gender = db.Column(db.Enum('男', '女'), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    age = db.Column(db.Integer)
    ethnicity = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    original_id_card = db.Column(db.String(18), nullable=True)  # 添加原始身份证号字段

    # 地址信息
    province = db.Column(db.String(50), default='江苏省')
    city = db.Column(db.String(50), default='江阴市')
    county = db.Column(db.String(50), default='周庄镇')
    community = db.Column(db.String(50), default='三房巷村')
    detailed_address = db.Column(db.Text)

    # 户籍信息
    bank_account = db.Column(db.String(20), nullable=False)
    area = db.Column(db.String(50), nullable=False)  # 工区
    nomination_date = db.Column(db.Date)  # 提名日期
    nomination_age = db.Column(db.Integer)  # 提名时周岁
    relationship = db.Column(db.String(50))  # 确保有 relationship 字段

    household_head_id = db.Column(
        db.Integer, db.ForeignKey('household_head.id'))  # 保持不变
    household_head = db.relationship(
        # 保持不变
        'HouseholdHead', back_populates='members', foreign_keys=[household_head_id])
    as_head = db.relationship(
        'HouseholdHead',
        back_populates='head',
        uselist=False,
        primaryjoin='HouseholdHead.head_id == Villager.id',
        foreign_keys='HouseholdHead.head_id'
    )  # 保持不变

    welfare_eligible = db.Column(db.Boolean, default=True)
    university_welfare_eligible = db.Column(db.Boolean, default=False)
    high_school_welfare_eligible = db.Column(db.Boolean, default=False)
    elderly_welfare_eligible = db.Column(db.Boolean, default=True)
    moved_out = db.Column(db.Boolean, default=False)
    move_out_date = db.Column(db.Date)
    move_out_location = db.Column(db.Text)
    moved_in = db.Column(db.Boolean, default=False)
    move_in_date = db.Column(db.Date)  # 新增迁入日期
    move_in_location = db.Column(db.Text)
    deceased = db.Column(db.Boolean, default=False)
    death_date = db.Column(db.Date)
    residency_status = db.Column(db.Boolean, default=True)
    remarks = db.Column(db.Text)  # 添加备注字段

    # 创建和更新时间
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(
        db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def calculate_age(self):
        if self.birth_date:
            today = datetime.today().date()
            age = today.year - self.birth_date.year
            if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
                age -= 1
            print("test",age)
            return age
        return None

    def to_dict(self):
        data = {
            'id': self.id,
            'name': self.name,
            'id_card': self.id_card,
            'gender': self.gender,
            'birth_date': self.birth_date.strftime('%Y-%m-%d') if self.birth_date else None,
            'ethnicity': self.ethnicity,
            'phone': self.phone,
            'province': self.province,
            'city': self.city,
            'county': self.county,
            'community': self.community,
            'detailed_address': self.detailed_address,
            'bank_account': self.bank_account,
            'area': self.area,
            'nomination_date': self.nomination_date.strftime('%Y-%m-%d') if self.nomination_date else None,
            'nomination_age': self.nomination_age,
            'welfare_eligible': self.welfare_eligible,
            'university_welfare_eligible': self.university_welfare_eligible,
            'high_school_welfare_eligible': self.high_school_welfare_eligible,
            'elderly_welfare_eligible': self.elderly_welfare_eligible,
            'moved_out': self.moved_out,
            'move_out_date': self.move_out_date.strftime('%Y-%m-%d') if self.move_out_date else None,
            'move_out_location': self.move_out_location,
            'moved_in': self.moved_in,
            'move_in_date': self.move_in_date.strftime('%Y-%m-%d') if self.move_in_date else None,
            'move_in_location': self.move_in_location,
            'deceased': self.deceased,
            'death_date': self.death_date.strftime('%Y-%m-%d') if self.death_date else None,
            'residency_status': self.residency_status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'household_members': [member.to_dict_simple() for member in self.household_head.members] if self.household_head else [],
            'relationship': self.relationship,
            'household_head': {
                'household_number': self.household_head.household_number,
                'head_name': self.household_head.head.name,
                'address_group': self.household_head.address_group
            } if self.household_head else None,
            'remarks': self.remarks,  # 添加到字典输出
            'original_id_card': self.original_id_card
        }
        return data

    def to_dict_simple(self):
        """简化的字典表示，用于同户成员展示"""
        return {
            'id': self.id,
            'name': self.name,
            'id_card': self.id_card,
            'relationship': self.relationship
        }


class Welfare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    villager_id = db.Column(db.Integer, db.ForeignKey(
        'villager.id'), nullable=False)
    welfare_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum('active', 'inactive'),
                       default='active', nullable=False)

    villager = db.relationship(
        # 改为 welfare_items
        'Villager', backref=db.backref('welfare_items', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'villager_id': self.villager_id,
            'welfare_type': self.welfare_type,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'amount': self.amount,
            'status': self.status
        }


class WelfareConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    basic_welfare_amount = db.Column(db.Float, nullable=False)
    basic_welfare_issue_date = db.Column(db.Date, nullable=True)  # 基础福利发放日期

    # 添加统一的养老金金额和发放日期字段
    elderly_welfare_amount = db.Column(db.Float, nullable=False)  # 养老金金额
    elderly_welfare_issue_date = db.Column(db.Date, nullable=True)  # 养老金发放日期

    # 添加4个阶段的养老金金额和发放日期字段
    elderly_welfare_stage1_amount = db.Column(
        db.Float, nullable=False, default=0)
    elderly_welfare_stage1_issue_date = db.Column(db.Date, nullable=True)
    elderly_welfare_stage2_amount = db.Column(
        db.Float, nullable=False, default=0)
    elderly_welfare_stage2_issue_date = db.Column(db.Date, nullable=True)
    elderly_welfare_stage3_amount = db.Column(
        db.Float, nullable=False, default=0)
    elderly_welfare_stage3_issue_date = db.Column(db.Date, nullable=True)
    elderly_welfare_stage4_amount = db.Column(
        db.Float, nullable=False, default=0)
    elderly_welfare_stage4_issue_date = db.Column(db.Date, nullable=True)


class WelfareRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    villager_id = db.Column(db.Integer, db.ForeignKey(
        'villager.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    # basic, elderly, high_school, university
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    issued = db.Column(db.Boolean, default=False)
    issue_date = db.Column(db.Date)
    school_name = db.Column(db.String(100))
    school_start_date = db.Column(db.Date)
    school_end_date = db.Column(db.Date)
    bank_account = db.Column(db.String(20), nullable=False)  # 新增字段

    def to_dict(self):
        return {
            'id': self.id,
            'villager_id': self.villager_id,
            'welfare_type': self.type,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'amount': self.amount,
            'status': self.issued,
            'issue_date': self.issue_date.strftime('%Y-%m-%d') if self.issue_date else None,
            'school_name': self.school_name,
            'school_start_date': self.school_start_date.strftime('%Y-%m-%d') if self.school_start_date else None,
            'school_end_date': self.school_end_date.strftime('%Y-%m-%d') if self.school_end_date else None,
            'bank_account': self.bank_account  # 新增字段
        }

    villager = db.relationship(
        'Villager', backref='welfare_history')  # 改为 welfare_history


class UniversitySubsidy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    villager_id = db.Column(db.Integer, db.ForeignKey(
        'villager.id'), nullable=False)
    school_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    issue_date = db.Column(db.Date)
    start_year = db.Column(db.Date, nullable=False)
    end_year = db.Column(db.Date, nullable=False)
    bank_account = db.Column(db.String(20), nullable=False)  # 已添加字段

    villager = db.relationship('Villager', backref='university_subsidies')

    def calculate_is_half_year(self, year):
        """判断指定年份是否按半年计算补贴"""
        return (self.start_year.year == year and self.start_year.month > 6) or \
               (self.end_year.year == year and self.end_year.month <= 6)

    def calculate_amount_for_year(self, year):
        """计算指定年份应发放的补贴金额"""
        if year < self.start_year.year or year > self.end_year.year:
            return 0
        
        base_amount = self.amount  # 获取基础金额
        
        # 入学年或毕业年只发放半年补贴
        if self.calculate_is_half_year(year):
            self.amount = base_amount / 2  # 更新数据库中的金额为半额
            db.session.add(self)  # 确保更新被记录
            return base_amount / 2
        
        return base_amount


class HighSchoolReimbursement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    villager_id = db.Column(db.Integer, db.ForeignKey(
        'villager.id'), nullable=False)
    school_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    registration_date = db.Column(db.Date, nullable=False)
    issue_date = db.Column(db.Date)
    is_issued = db.Column(db.Boolean, default=False)
    bank_account = db.Column(db.String(20), nullable=False)  # 已添加字段

    villager = db.relationship(
        'Villager', backref='high_school_reimbursements')

    def calculate_reimbursement_amount(self):
        """计算实际报销金额"""
        # 获取入学日期所在的年份和月份
        reg_year = self.registration_date.year
        reg_month = self.registration_date.month
        
        # 如果是下半年入学（7月后），金额减半
        if reg_month > 6:
            self.amount = self.amount / 2  # 更新数据库中的金额为半额
            db.session.add(self)  # 确保更新被记录
        
        return self.amount
