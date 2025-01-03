from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from models import User, Villager, UniversitySubsidy, HighSchoolReimbursement, db
from wraps import login_required

education_bp = Blueprint('education', __name__)

@education_bp.route('/university')
@login_required
def university():
    return render_template('education/university.html')

@education_bp.route('/highschool')
@login_required
def highschool():
    return render_template('education/highschool.html')

@education_bp.route('/university/search')
@login_required
def search_university():
    query = request.args.get('query', '')
    search_type = request.args.get('search_type', 'name')
    
    if not query:
        return jsonify({'error': '请输入搜索内容'}), 400
        
    villager_query = Villager.query.outerjoin(
        UniversitySubsidy, 
        Villager.id == UniversitySubsidy.villager_id
    )

    if search_type == 'name':
        villager_query = villager_query.filter(Villager.name.like(f'%{query}%'))
    else:
        villager_query = villager_query.filter(Villager.id_card.like(f'%{query}%'))

    if session.get('role') != '管理员':
        user_area = User.query.get(session['user_id']).area
        villager_query = villager_query.filter(Villager.area == user_area)
        
    villagers = villager_query.all()

    return jsonify({
        'villagers': [{
            'id': v.id,
            'name': v.name,
            'id_card': v.id_card,
            'university_welfare_eligible': v.university_welfare_eligible,
            'area': v.area,
            'birth_date': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else None,
            'bank_account': v.bank_account,
            # 当前补贴信息
            'current_subsidy': next((
                {
                    'school_name': s.school_name,
                    'amount': s.amount,  # 使用输入的金额
                    'issue_date': s.issue_date.strftime('%Y-%m-%d') if s.issue_date else None,
                    'start_year': s.start_year.strftime('%Y-%m-%d') if s.start_year else None,
                    'end_year': s.end_year.strftime('%Y-%m-%d') if s.end_year else None,
                    'is_half_year': False,  # 不再使用半年的标记
                }
                for s in v.university_subsidies
                if not s.end_year or s.end_year >= datetime.now().date()
            ), None),
            # 补贴历史
            'subsidy_history': [
                {
                    'school_name': s.school_name,
                    'amount': s.amount,  # 使用输入的金额
                    'issue_date': s.issue_date.strftime('%Y-%m-%d') if s.issue_date else None,
                    'start_year': s.start_year.strftime('%Y-%m-%d') if s.start_year else None,
                    'end_year': s.end_year.strftime('%Y-%m-%d') if s.end_year else None,
                }
                for s in v.university_subsidies
            ]
        } for v in villagers]
    })

@education_bp.route('/highschool/search')
@login_required
def search_highschool():
    query = request.args.get('query', '')
    search_type = request.args.get('search_type', 'name')
    
    if not query:
        return jsonify({'error': '请输入搜索内容'}), 400
        
    villager_query = Villager.query.outerjoin(
        HighSchoolReimbursement, 
        Villager.id == HighSchoolReimbursement.villager_id
    )

    if search_type == 'name':
        villager_query = villager_query.filter(Villager.name.like(f'%{query}%'))
    else:
        villager_query = villager_query.filter(Villager.id_card.like(f'%{query}%'))

    if session.get('role') != '管理员':
        user_area = User.query.get(session['user_id']).area
        villager_query = villager_query.filter(Villager.area == user_area)
        
    villagers = villager_query.all()

    return jsonify({
        'villagers': [{
            'id': v.id,
            'name': v.name,
            'id_card': v.id_card,
            'high_school_welfare_eligible': v.high_school_welfare_eligible,
            'area': v.area,
            'birth_date': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else None,
            'bank_account': v.bank_account,
            # 当前报销信息
            'current_reimbursement': next((
                {
                    'school_name': r.school_name,
                    'amount': r.amount,
                    'invoice_number': r.invoice_number,
                    'invoice_date': r.invoice_date.strftime('%Y-%m-%d') if r.invoice_date else None,
                    'registration_date': r.registration_date.strftime('%Y-%m-%d') if r.registration_date else None,
                    'issue_date': r.issue_date.strftime('%Y-%m-%d') if r.issue_date else None,
                    'is_issued': r.is_issued
                }
                for r in v.high_school_reimbursements
                if not r.is_issued
            ), None),
            # 报销历史
            'reimbursement_history': [
                {
                    'school_name': r.school_name,
                    'amount': r.amount,
                    'invoice_number': r.invoice_number,
                    'invoice_date': r.invoice_date.strftime('%Y-%m-%d') if r.invoice_date else None,
                    'registration_date': r.registration_date.strftime('%Y-%m-%d') if r.registration_date else None,
                    'issue_date': r.issue_date.strftime('%Y-%m-%d') if r.issue_date else None,
                    'is_issued': r.is_issued
                }
                for r in v.high_school_reimbursements
            ]
        } for v in villagers]
    })

@education_bp.route('/university/save', methods=['POST'])
@login_required
def save_university():
    data = request.json
    try:
        villager = Villager.query.get(data['villager_id'])
        bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account

        # 移除自动减半逻辑
        # start_year_date = datetime.strptime(data['start_year'], '%Y-%m-%d').date()
        # end_year_date = datetime.strptime(data['end_year'], '%Y-%m-%d').date()
        amount = float(data['amount'])
        
        # if (start_year_date.year == current_year and start_year_date.month > 6) or \
        #    (end_year_date.year == current_year and end_year_date.month <= 6):
        #     amount = amount / 2

        subsidy = UniversitySubsidy(
            villager_id=data['villager_id'],
            school_name=data['school_name'],
            amount=amount,  # 使用输入的金额
            issue_date=datetime.strptime(data['issue_date'], '%Y-%m-%d').date(),
            start_year=datetime.strptime(data['start_year'], '%Y-%m-%d').date(),
            end_year=datetime.strptime(data['end_year'], '%Y-%m-%d').date(),
            bank_account=bank_account
        )
        db.session.add(subsidy)
        db.session.commit()
        return jsonify({
            'success': True, 
            'amount': amount,  # 返回输入的金额
            'message': '补贴已保存'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@education_bp.route('/highschool/save', methods=['POST'])
@login_required
def save_highschool():
    data = request.json
    try:
        villager = Villager.query.get(data['villager_id'])
        bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account
        
        reimbursement = HighSchoolReimbursement(
            villager_id=data['villager_id'],
            school_name=data['school_name'],
            amount=data['amount'],
            invoice_number=data['invoice_number'],
            invoice_date=datetime.strptime(data['invoice_date'], '%Y-%m-%d').date(),
            registration_date=datetime.strptime(data['registration_date'], '%Y-%m-%d').date(),
            issue_date=datetime.strptime(data['issue_date'], '%Y-%m-%d').date() if data.get('issue_date') else None,
            is_issued=data.get('is_issued', False),
            bank_account=bank_account  # 添加银行账户
        )
        db.session.add(reimbursement)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@education_bp.route('/university/add', methods=['POST'])
@login_required
def add_university_subsidy():
    try:
        data = request.get_json()
        villager_id = data.get('villager_id')
        school_name = data.get('school_name')
        amount = float(data.get('amount', 0))
        start_year = datetime.strptime(data.get('start_year'), '%Y-%m-%d')
        end_year = datetime.strptime(data.get('end_year'), '%Y-%m-%d')

        villager = Villager.query.get(villager_id)
        bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account

        subsidy = UniversitySubsidy(
            villager_id=villager_id,
            school_name=school_name,
            amount=amount,  # 存储输入的金额
            start_year=start_year,
            end_year=end_year,
            bank_account=bank_account
        )

        # 移除自动减半逻辑
        # current_year = datetime.now().year
        # if subsidy.calculate_is_half_year(current_year):
        #     subsidy.amount = amount / 2  # 直接存储半额

        db.session.add(subsidy)
        db.session.commit()
        
        return jsonify({'message': '大学生补贴添加成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@education_bp.route('/highschool/add', methods=['POST'])
@login_required
def add_highschool_reimbursement():
    try:
        data = request.get_json()
        villager_id = data.get('villager_id')
        school_name = data.get('school_name')
        amount = float(data.get('amount', 0))
        invoice_number = data.get('invoice_number')
        invoice_date = datetime.strptime(data.get('invoice_date'), '%Y-%m-%d')
        registration_date = datetime.strptime(data.get('registration_date'), '%Y-%m-%d')

        villager = Villager.query.get(villager_id)
        bank_account = villager.bank_account if not villager.household_head else villager.household_head.head.bank_account

        reimbursement = HighSchoolReimbursement(
            villager_id=villager_id,
            school_name=school_name,
            amount=amount,  # 存储原始金额
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            registration_date=registration_date,
            bank_account=bank_account  # 添加银行账户
        )

        # 根据入学时间调整金额
        if registration_date.month > 6:
            reimbursement.amount = amount / 2  # 直接存储半额

        db.session.add(reimbursement)
        db.session.commit()
        
        return jsonify({'message': '高中生补贴添加成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
