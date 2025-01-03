from datetime import datetime
from sqlalchemy import alias
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from models import HighSchoolReimbursement, HouseholdHead, UniversitySubsidy, User, Villager, Welfare, WelfareConfig, WelfareRecord, db
from wraps import login_required, admin_required, area_required
import pandas as pd

welfare_bp = Blueprint('welfare', __name__)

@welfare_bp.route('/')
@login_required
def welfare():
    year = datetime.now().year
    welfare_config = WelfareConfig.query.filter_by(year=year).first()
    return render_template('welfare.html', year=year, config=welfare_config)

@welfare_bp.route('/search')
@login_required
def search():
    search_type = request.args.get('search_type')
    query = request.args.get('query', '')
    year = int(request.args.get('year', datetime.now().year))
    villager_id = request.args.get('villager_id')  # 添加获取villager_id

    # 如果有villager_id，直接查询特定村民
    if villager_id:
        villager = Villager.query.get_or_404(villager_id)
        # 构建基础信息
        resident_info = {
            'villager_id': villager.id,
            'name': villager.name,
            'id_card': villager.id_card,
            'bank_account': villager.bank_account,
            'area': villager.area,
            'birth_date': villager.birth_date.strftime('%Y-%m-%d')  # 添加出生日期
        }

        # 获取户籍信息
        if villager.household_head:
            household = villager.household_head
            household_head = household.head
            resident_info.update({
                'household_number': household.household_number,
                'household_head_name': household_head.name,
                'household_head_bank_account': household_head.bank_account,
                'issued_bank_account': household_head.bank_account
            })
        else:
            resident_info.update({
                'household_number': '',
                'household_head_name': '',
                'household_head_bank_account': '',
                'issued_bank_account': villager.bank_account
            })
        
        # 计算福利金额并更新数据
        welfare_data = calculate_welfare_amounts(villager, year)
        if welfare_data is None:
            welfare_data = {
                'basic_welfare': {
                    'eligible': villager.welfare_eligible,
                    'base_amount': 0,
                    'amount': 0,
                },
                'elderly_welfare': {
                    'eligible': False,
                    'amount': 0,
                    'issue_date': ''
                },
                'welfare_records': get_welfare_records(villager.id, year)
            }
        welfare_data.update(resident_info)
        
        return jsonify({
            'multiple': False,
            'welfare': welfare_data
        })

    # 如果没有villager_id，执行普通搜索
    if not query:
        return jsonify({'error': '请输入搜索内容'}), 400

    # 修改查询逻辑
    VillagerAlias = alias(Villager)  # 创建别名表
    villager_query = Villager.query.outerjoin(
        HouseholdHead, 
        Villager.household_head_id == HouseholdHead.id
    ).outerjoin(
        VillagerAlias,
        HouseholdHead.head_id == VillagerAlias.c.id
    )

    if search_type == 'name':
        villager_query = villager_query.filter(Villager.name.like(f'%{query}%'))
    else:
        villager_query = villager_query.filter(Villager.id_card.like(f'%{query}%'))

    # 权限过滤
    if session.get('role') != '管理员':
        user_areas = User.query.get(session['user_id']).area.split(',')
        villager_query = villager_query.filter(Villager.area.in_(user_areas))

    villagers = villager_query.all()
    
    if not villagers:
        return jsonify({'error': '未找到符合条件的村民'}), 404

    if len(villagers) > 1 and search_type == 'name':
        return jsonify({
            'multiple': True,
            'results': [{
                'id': v.id,
                'name': v.name,
                'id_card': v.id_card,
                'area': v.area,
                'household_number': v.household_head.household_number if v.household_head else ''
            } for v in villagers]
        })

    villager = villagers[0]
    
    # 构建基础信息
    resident_info = {
        'villager_id': villager.id,
        'name': villager.name,
        'id_card': villager.id_card,
        'bank_account': villager.bank_account,
        'area': villager.area
    }

    # 获取户籍信息
    if (household := villager.household_head):
        household_head = household.head
        resident_info.update({
            'household_number': household.household_number,
            'household_head_name': household_head.name,
            'household_head_bank_account': household_head.bank_account,
            'issued_bank_account': household_head.bank_account  # 默认使用户主的银行卡
        })
    else:
        resident_info.update({
            'household_number': '',
            'household_head_name': '',
            'household_head_bank_account': '',
            'issued_bank_account': villager.bank_account  # 如果没有户主，使用本人的银行卡
        })
    
    # 计算福利金额并更新数据
    welfare_data = calculate_welfare_amounts(villager, year)
    if welfare_data is None:
        # 如果没有找到福利配置，创建一个默认的福利数据结构
        welfare_data = {
            'basic_welfare': {
                'eligible': villager.welfare_eligible,
                'base_amount': 0,
                'amount': 0,
            },
            'elderly_welfare': {
                'eligible': False,
                'amount': 0,
                'issue_date': ''
            },
            'welfare_records': get_welfare_records(villager.id, year)
        }
    welfare_data.update(resident_info)
    
    return jsonify({
        'multiple': False,
        'welfare': welfare_data
    })

@welfare_bp.route('/save', methods=['POST'])
@login_required
@area_required
def save_welfare():
    data = request.json
    villager_id = data.get('villager_id')
    basic_welfare_eligible = data.get('basic_welfare_eligible', False)
    
    if not villager_id:
        return jsonify({'error': '缺少必要参数'}), 400

    try:
        villager = Villager.query.get_or_404(villager_id)
        villager.welfare_eligible = basic_welfare_eligible
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@welfare_bp.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    if request.method == 'POST':
        data = request.json
        year = data.get('year')
        basic_amount = data.get('basic_welfare_amount')
        basic_issue_date = data.get('basic_welfare_issue_date')
        
        # 获取4个阶段的养老金金额
        stage1_amount = data.get('elderly_welfare_stage1_amount')
        stage2_amount = data.get('elderly_welfare_stage2_amount')
        stage3_amount = data.get('elderly_welfare_stage3_amount')
        stage4_amount = data.get('elderly_welfare_stage4_amount')
        
        # 使用统一的养老金发放日期
        elderly_issue_date = data.get('elderly_welfare_issue_date')
        
        # 获取统一的养老金金额
        elderly_amount = data.get('elderly_welfare_amount')  # 新增
        
        config = WelfareConfig.query.filter_by(year=year).first()
        if not config:
            config = WelfareConfig(year=year)
            db.session.add(config)
        
        config.basic_welfare_amount = basic_amount
        config.basic_welfare_issue_date = datetime.strptime(basic_issue_date, '%Y-%m-%d').date() if basic_issue_date else None
        
        # 更新统一的养老金金额和发放日期
        config.elderly_welfare_amount = elderly_amount  # 修改
        config.elderly_welfare_issue_date = datetime.strptime(elderly_issue_date, '%Y-%m-%d').date() if elderly_issue_date else None
        
        # 更新4个养老金阶段金额字段
        config.elderly_welfare_stage1_amount = stage1_amount
        config.elderly_welfare_stage2_amount = stage2_amount
        config.elderly_welfare_stage3_amount = stage3_amount
        config.elderly_welfare_stage4_amount = stage4_amount
        
        try:
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    else:
        year = request.args.get('year')
        if year:
            config = WelfareConfig.query.filter_by(year=year).first()
            if config:
                return jsonify({
                    'year': config.year,
                    'basic_welfare_amount': config.basic_welfare_amount,
                    'basic_welfare_issue_date': config.basic_welfare_issue_date.strftime('%Y-%m-%d') if config.basic_welfare_issue_date else '',
                    'elderly_welfare_amount': config.elderly_welfare_amount,  # 新增
                    'elderly_welfare_issue_date': config.elderly_welfare_issue_date.strftime('%Y-%m-%d') if config.elderly_welfare_issue_date else '',
                    'elderly_welfare_stage1_amount': config.elderly_welfare_stage1_amount,
                    'elderly_welfare_stage2_amount': config.elderly_welfare_stage2_amount,
                    'elderly_welfare_stage3_amount': config.elderly_welfare_stage3_amount,
                    'elderly_welfare_stage4_amount': config.elderly_welfare_stage4_amount,
                })
            else:
                return jsonify({'error': '未找到该年份的配置'}), 404
        else:
            return jsonify({'error': '未提供年份参数'}), 400

@welfare_bp.route('/config/view')
@login_required
def config_view():
    return render_template('config.html')

@welfare_bp.route('/issue', methods=['GET', 'POST'])
@login_required
@admin_required
def issue():
    if request.method == 'POST':
        try:
            villager_id = request.form['villager_id']
            welfare_type = request.form['welfare_type']
            amount = float(request.form['amount'])
            bank_account = request.form.get('bank_account')  # 使用 get 方法以允许缺省

            villager = Villager.query.get(villager_id)
            if not villager:
                flash('村民不存在', 'danger')
                return redirect(url_for('welfare.issue'))

            # 如果未提供银行账户号，使用户主的银行账户号
            if not bank_account:
                bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account

            # 验证银行账户号格式（示例：仅数字，长度为至少6位）
            if not bank_account.isdigit() or len(bank_account) < 6:
                flash('银行账户号格式不正确', 'danger')
                return redirect(url_for('welfare.issue'))

            welfare_record = WelfareRecord(
                villager_id=villager_id,
                year=datetime.now().year,
                type=welfare_type,
                amount=amount,
                bank_account=bank_account  # 记录银行账户
            )

            db.session.add(welfare_record)
            db.session.commit()
            flash('福利发放成功', 'success')
            return redirect(url_for('welfare.issue'))
        except Exception as e:
            db.session.rollback()
            flash(f'发放失败: {str(e)}', 'danger')
            return redirect(url_for('welfare.issue'))

def calculate_welfare_amounts(villager, year):
    # 获取福利配置
    config = WelfareConfig.query.filter_by(year=year).first()
    if not config:
        return None

    # 计算居住时间
    start_date = datetime(year, 1, 1).date()
    end_date = datetime(year, 12, 31).date()
    
    # 只有在确实发生迁入迁出的情况下才计算居住时间
    residency_less_than_year = False
    basic_welfare_message = '基本福利金额正常'
    
    if villager.moved_in or villager.moved_out:
        if villager.move_in_date:
            residency_start = max(villager.move_in_date, start_date)
        else:
            residency_start = start_date
        
        if villager.move_out_date:
            residency_end = min(villager.move_out_date, end_date)
        else:
            residency_end = end_date
        
        # 只在同一年份内计算
        if residency_start.year == year and residency_end.year == year:
            residency_days = (residency_end - residency_start).days + 1
            residency_time = residency_days / 365.25
            residency_less_than_year = residency_time < 1
            if residency_less_than_year:
                basic_welfare_message = f'本年度居住不足一年，基本福利金额减半'
    
    # 计算基本福利
    basic_amount = config.basic_welfare_amount
    basic_welfare_message = '基本福利金额正常'
    
    # 检查是否需要减半
    need_half = False
    
    # 检查出生时间（如果是当年出生）
    if villager.birth_date and villager.birth_date.year == year:
        if villager.birth_date.month > 6:  # 下半年出生
            need_half = True
            basic_welfare_message = f'本年度{villager.birth_date.month}月出生，发放半年基础福利'
    
    # 检查死亡时间（如果当年死亡）
    elif villager.deceased and villager.death_date and villager.death_date.year == year:
        if villager.death_date.month <= 6:  # 上半年死亡
            need_half = True
            basic_welfare_message = f'本年度{villager.death_date.month}月死亡，发放半年基础福利'
    
    # 检查迁入时间
    elif villager.moved_in and villager.move_in_date and villager.move_in_date.year == year:
        if villager.move_in_date.month > 6:  # 下半年迁入
            need_half = True
            basic_welfare_message = f'本年度{villager.move_in_date.month}月迁入，发放半年基础福利'
    
    # 检查迁出时间
    elif villager.moved_out and villager.move_out_date and villager.move_out_date.year == year:
        if villager.move_out_date.month <= 6:  # 上半年迁出
            need_half = True
            basic_welfare_message = f'本年度{villager.move_out_date.month}月迁出，发放半年基础福利'
    
    if need_half:
        basic_amount /= 2

    # 计算养老金阶段和金额
    elderly_amount = 0
    elderly_issue_date = config.elderly_welfare_issue_date
    
    if elderly_issue_date:
        # 计算发放日期时的年龄
        age_at_issue = elderly_issue_date.year - villager.birth_date.year
        if (elderly_issue_date.month, elderly_issue_date.day) < (villager.birth_date.month, villager.birth_date.day):
            age_at_issue -= 1
            
        # 根据发放日期时的年龄判断养老金阶段和金额
        if age_at_issue >= 70 and age_at_issue < 80:
            elderly_amount = config.elderly_welfare_stage1_amount
            stage = 'stage1'
        elif age_at_issue >= 80 and age_at_issue < 90:
            elderly_amount = config.elderly_welfare_stage2_amount
            stage = 'stage2'
        elif age_at_issue >= 90 and age_at_issue < 100:
            elderly_amount = config.elderly_welfare_stage3_amount
            stage = 'stage3'
        elif age_at_issue >= 100:
            elderly_amount = config.elderly_welfare_stage4_amount
            stage = 'stage4'
        else:
            stage = None
    
    return {
        'villager_id': villager.id,
        'name': villager.name,
        'id_card': villager.id_card,
        'household_number': villager.household_head.household_number if villager.household_head else '',
        'household_head_name': villager.household_head.head.name if villager.household_head else '',
        'bank_account': villager.bank_account,
        'household_head_bank_account': villager.household_head.head.bank_account if villager.household_head else '',
        'basic_welfare': {
            'eligible': villager.welfare_eligible,
            'base_amount': config.basic_welfare_amount,  # 添加原始基础金额
            'amount': basic_amount,  # 实际发放金额（可能减半）
            'issue_date': config.basic_welfare_issue_date.strftime('%Y-%m-%d') if config.basic_welfare_issue_date else '',
            'message': basic_welfare_message  # 添加提示信息
        },
        
        'elderly_welfare': {
            'eligible': age_at_issue >= 70 if elderly_issue_date else False,
            'amount': elderly_amount,
            'issue_date': elderly_issue_date.strftime('%Y-%m-%d') if elderly_issue_date else '',
            'age_at_issue': age_at_issue if elderly_issue_date else None,
            'stage': stage
        },
        
        'welfare_records': {
            'basic': get_basic_welfare_record(villager.id, year),
            'high_school': get_high_school_welfare_record(villager.id, year),
            'elderly': get_elderly_welfare_record(villager.id, year),
            'university': get_university_welfare_record(villager.id, year)
        },
        'basic_welfare_eligible': villager.welfare_eligible,
        'elderly_welfare_eligible': villager.elderly_welfare_eligible,
        'university_welfare_eligible': villager.university_welfare_eligible,
        'high_school_welfare_eligible': villager.high_school_welfare_eligible,
        'university_subsidies': [
            {
                'school_name': s.school_name,
                'amount': s.amount,
                'start_year': s.start_year.strftime('%Y-%m-%d') if s.start_year else None,
                'end_year': s.end_year.strftime('%Y-%m-%d') if s.end_year else None,
                'issue_date': s.issue_date.strftime('%Y-%m-%d') if s.issue_date else None,
            }
            for s in villager.university_subsidies
        ],
        'high_school_subsidies': [
            {
                'school_name': r.school_name,
                'amount': r.amount,
                'invoice_number': r.invoice_number,
                'invoice_date': r.invoice_date.strftime('%Y-%m-%d') if r.invoice_date else None,
                'registration_date': r.registration_date.strftime('%Y-%m-%d') if r.registration_date else None,
                'issue_date': r.issue_date.strftime('%Y-%m-%d') if r.issue_date else None,
                'is_issued': r.is_issued,
                'bank_account': r.bank_account
            }
            for r in villager.high_school_reimbursements
        ],
        'welfare_bank_account': villager.welfare_bank_account or (villager.household_head.head.bank_account if villager.household_head else '') or villager.bank_account or '0'
    }

def save_welfare_records(villager_id, year, data):
    """保存村民的各项福利记录"""
    
    # 获取村民实例
    villager = Villager.query.get_or_404(villager_id)
    
    # 计算居住时间
    start_date = datetime(year, 1, 1).date()
    end_date = datetime(year, 12, 31).date()
    
    if villager.move_in_date:
        residency_start = max(villager.move_in_date, start_date)
    else:
        residency_start = start_date
    
    if villager.move_out_date:
        residency_end = min(villager.move_out_date, end_date)
    else:
        residency_end = end_date
    
    residency_days = (residency_end - residency_start).days + 1
    residency_time = residency_days / 365.25  # 计算居住年数
    
    residency_less_than_year = residency_time < 1

    # 保存基本福利记录
    if data.get('basic_welfare_eligible'):
        basic_welfare = WelfareRecord.query.filter_by(
            villager_id=villager_id,
            year=year,
            type='basic'
        ).first() or WelfareRecord(
            villager_id=villager_id,
            year=year,
            type='basic'
        )
        
        basic_amount = data.get('basic_welfare_amount', 0)
        if residency_less_than_year:
            basic_amount /= 2  # 居住时间不足一年，减半
        
        basic_welfare.amount = basic_amount
        basic_welfare.issued = bool(data.get('basic_welfare_issued'))
        if data.get('basic_welfare_date'):
            basic_welfare.issue_date = datetime.strptime(data['basic_welfare_date'], '%Y-%m-%d').date()
        # 获取并设置银行账户
        basic_welfare.bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account
        
        db.session.add(basic_welfare)
    
    # 保存高中学费减免记录
    if data.get('high_school_waiver'):
        high_school = WelfareRecord.query.filter_by(
            villager_id=villager_id,
            year=year,
            type='high_school'
        ).first() or WelfareRecord(
            villager_id=villager_id,
            year=year,
            type='high_school'
        )
        
        high_school.amount = data.get('high_school_amount', 0)
        if data.get('high_school_start_date'):
            high_school.school_start_date = datetime.strptime(data['high_school_start_date'], '%Y-%m-%d').date()
        if data.get('high_school_end_date'):
            high_school.school_end_date = datetime.strptime(data['high_school_end_date'], '%Y-%m-%d').date()
        # 获取并设置银行账户
        high_school.bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account
            
        db.session.add(high_school)
    
    # 保存尊老金记录
    age = villager.calculate_age()
    if age and age >= 70:
        elderly = WelfareRecord.query.filter_by(
            villager_id=villager_id,
            year=year,
            type='elderly'
        ).first() or WelfareRecord(
            villager_id=villager_id,
            year=year,
            type='elderly'
        )
        
        elderly.amount = data.get('elderly_welfare_amount', 0)
        elderly.issued = bool(data.get('elderly_welfare_issued'))
        if data.get('elderly_welfare_date'):
            elderly.issue_date = datetime.strptime(data['elderly_welfare_date'], '%Y-%m-%d').date()
        # 获取并设置银行账户
        elderly.bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account
            
        db.session.add(elderly)

    db.session.commit()

def get_welfare_records(villager_id, year):
    """获取村民指定年份的福利记录"""
    records = WelfareRecord.query.filter_by(
        villager_id=villager_id,
        year=year
    ).all()
    
    welfare_records = {
        'basic': None,
        'high_school': None,
        'elderly': None,
        'university': None
    }
    
    for record in records:
        welfare_records[record.type] = {
            'amount': record.amount,
            'issued': record.issued,
            'issue_date': record.issue_date.strftime('%Y-%m-%d') if record.issue_date else None,
            'school_name': record.school_name,
            'school_start_date': record.school_start_date.strftime('%Y-%m-%d') if record.school_start_date else None,
            'school_end_date': record.school_end_date.strftime('%Y-%m-%d') if record.school_end_date else None,
            'bank_account': record.bank_account  # 确保包含银行账户字段
        }
    
    return welfare_records

def get_university_welfare_record(villager_id, year):
    """获取大学生补贴记录"""
    subsidy = UniversitySubsidy.query.filter(
        UniversitySubsidy.villager_id == villager_id,
        UniversitySubsidy.start_year <= datetime(year, 12, 31),
        UniversitySubsidy.end_year >= datetime(year, 1, 1)
    ).first()
    
    if subsidy:
        return {
            'school_name': subsidy.school_name,
            'amount': subsidy.amount,
            'issue_date': subsidy.issue_date.strftime('%Y-%m-%d') if subsidy.issue_date else None,
            'school_start_date': subsidy.start_year.strftime('%Y-%m-%d'),
            'school_end_date': subsidy.end_year.strftime('%Y-%m-%d'),
            'bank_account': subsidy.bank_account  # 确保包含银行账户字段
        }
    return None

def get_high_school_welfare_record(villager_id, year):
    """获取高中生补贴记录"""
    reimbursement = HighSchoolReimbursement.query.filter(
        HighSchoolReimbursement.villager_id == villager_id,
        HighSchoolReimbursement.registration_date.between(
            datetime(year, 1, 1), 
            datetime(year, 12, 31)
        )
    ).first()
    
    if reimbursement:
        return {
            'school_name': reimbursement.school_name,
            'amount': reimbursement.amount,
            'invoice_number': reimbursement.invoice_number,
            'invoice_date': reimbursement.invoice_date.strftime('%Y-%m-%d'),
            'school_start_date': reimbursement.registration_date.strftime('%Y-%m-%d'),
            'issue_date': reimbursement.issue_date.strftime('%Y-%m-%d') if reimbursement.issue_date else None,
            'is_issued': reimbursement.is_issued,
            'bank_account': reimbursement.bank_account  # 确保包含银行账户字段
        }
    return None

def get_basic_welfare_record(villager_id, year):
    """获取基本福利记录"""
    record = WelfareRecord.query.filter_by(
        villager_id=villager_id,
        year=year,
        type='basic'
    ).first()
    
    if record:
        return {
            'amount': record.amount,
            'issued': record.issued,
            'issue_date': record.issue_date.strftime('%Y-%m-%d') if record.issue_date else None,
            'bank_account': record.bank_account  # 确保包含银行账户字段
        }
    return None

def get_elderly_welfare_record(villager_id, year):
    """获取养老金福利记录"""
    record = WelfareRecord.query.filter_by(
        villager_id=villager_id,
        year=year,
        type='elderly'
    ).first()
    
    if record:
        return {
            'amount': record.amount,
            'issued': record.issued,
            'issue_date': record.issue_date.strftime('%Y-%m-%d') if record.issue_date else None,
            'bank_account': record.bank_account  # 确保包含银行账户字段
        }
    return None


@welfare_bp.route('/update_bank_account/<int:record_id>', methods=['POST'])
@login_required
@admin_required
def update_bank_account(record_id):
    try:
        new_bank_account = request.form['bank_account']
        welfare_record = WelfareRecord.query.get(record_id)
        if not welfare_record:
            flash('福利记录不存在', 'danger')
            return redirect(url_for('welfare.records'))

        # 验证银行账户号格式
        if not new_bank_account.isdigit() or len(new_bank_account) < 6:
            flash('银行账户号格式不正确', 'danger')
            return redirect(url_for('welfare.records'))

        welfare_record.bank_account = new_bank_account
        db.session.commit()
        flash('银行账户更新成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败: {str(e)}', 'danger')
    return redirect(url_for('welfare.records'))

@welfare_bp.route('/update_bank_account', methods=['POST'])
@login_required
def update_welfare_bank_account():
    data = request.get_json()
    villager_id = data.get('villager_id')
    welfare_bank_account = data.get('welfare_bank_account')

    if not villager_id:
        return jsonify({'error': '缺少必要参数'}), 400

    try:
        villager = Villager.query.get_or_404(villager_id)
        villager.welfare_bank_account = welfare_bank_account
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

