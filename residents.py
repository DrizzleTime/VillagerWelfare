import random
from datetime import datetime

import pandas as pd
from flask import Blueprint, render_template, request, jsonify, flash  # 添加导入

from models import Villager, db, HouseholdHead
from wraps import login_required, admin_required, area_required

residents_bp = Blueprint('residents', __name__)


@residents_bp.route('/')
@login_required
def residents():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Villager.query

    residents = query.paginate(page=page, per_page=per_page, error_out=False)

    # 获取所有户主用于下拉框
    household_heads = HouseholdHead.query.all()
    household_head_options = [
        {'id': head.head_id, 'name': head.head.name}
        for head in household_heads
    ]

    return render_template('residents.html', residents=residents, household_head_options=household_head_options)


@residents_bp.route('/search', methods=['GET'])
@login_required
def search_residents():
    query = request.args.get('query', '')  # 修改为获取GET参数
    search_type = request.args.get('type', 'name')  # 修改为获取GET参数

    if not query:
        return jsonify({'error': '请输入搜索内容'}), 400

    if search_type == 'name':
        residents = Villager.query.filter(Villager.name.like(f'%{query}%'))
    else:
        residents = Villager.query.filter(Villager.id_card.like(f'%{query}%'))

    results = residents.all()

    if not results:
        return jsonify({'error': '未找到匹配的村民'}), 404

    if search_type == 'name' and len(results) > 1:
        return jsonify({
            'multiple': True,
            'results': [{
                'id': r.id,
                'name': r.name,
                'id_card': r.id_card,
                'area': r.area,
                'household_number': r.household_head.household_number if r.household_head else ''
            } for r in results]
        })

    resident = results[0]
    resident_data = resident.to_dict()
    resident_data['household_number'] = resident.household_head.household_number if resident.household_head else ''
    resident_data['household_members'] = [m.to_dict_simple() for m in
                                          resident.household_head.members] if resident.household_head else []
    # 确保福利资格字段被包含在返回数据中
    resident_data.update({
        'elderly_welfare_eligible': resident.elderly_welfare_eligible,
        'university_welfare_eligible': resident.university_welfare_eligible,
        'high_school_welfare_eligible': resident.high_school_welfare_eligible
    })
    return jsonify({
        'multiple': False,
        'resident': resident_data
    })


@residents_bp.route('/<int:id>')
@login_required
@area_required
def get_resident(id):
    resident = Villager.query.get_or_404(id)

    household_members = [m.to_dict_simple() for m in resident.household_head.members] if resident.household_head else []

    return jsonify({
        'resident': resident.to_dict(),
        'household_members': household_members
    })


@residents_bp.route('/new', methods=['POST'])
@login_required
@area_required
def create_resident():
    data = request.get_json()
    required_fields = ['name', 'id_card', 'gender', 'birth_date', 'bank_account', 'area']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} 不能为空'}), 400

    resident = Villager()
    db.session.add(resident)

    for key, value in data.items():
        if hasattr(resident, key) and key not in ['id']:
            if key in ['birth_date', 'nomination_date', 'move_out_date', 'move_in_date', 'death_date']:
                setattr(resident, key, datetime.strptime(value, '%Y-%m-%d').date() if value else None)
            else:
                setattr(resident, key, value)

    # 处理福利资格字段
    resident.welfare_eligible = bool(data.get('welfare_eligible'))
    resident.elderly_welfare_eligible = bool(data.get('elderly_welfare_eligible'))
    resident.university_welfare_eligible = bool(data.get('university_welfare_eligible'))
    resident.high_school_welfare_eligible = bool(data.get('high_school_welfare_eligible'))

    if not data.get('household_number'):
        resident.household_head = HouseholdHead(
            household_number=f"HH{random.randint(1000, 9999)}",
            head_id=resident.id,
            address_group='1组'
        )
    else:
        hh = HouseholdHead.query.filter_by(household_number=data['household_number']).first()
        if not hh:
            hh = HouseholdHead(
                household_number=data['household_number'],
                head_id=resident.id,
                address_group=data.get('household_address_group', '1组')
            )
            db.session.add(hh)
        resident.household_head = hh

    try:
        db.session.commit()
        flash('新建成功', 'success')  # 添加flash消息
        return jsonify({'message': '新建成功', 'id': resident.id})
    except Exception as e:
        db.session.rollback()
        flash(f'新建失败: {str(e)}', 'error')  # 添加flash消息
        return jsonify({'error': str(e)}), 500


@residents_bp.route('/<int:id>/save', methods=['POST'])
@login_required
@area_required
def save_resident_by_id(id):
    data = request.get_json()
    resident = Villager.query.get_or_404(id)
    required_fields = ['name', 'id_card', 'gender', 'birth_date', 'bank_account', 'area', 'household_number']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} 不能为空'}), 400

    household_number = data.get('household_number')
    household_head_name = data.get('household_head_name')
    address_group = data.get('household_address_group')

    hh = HouseholdHead.query.filter_by(household_number=household_number).first()
    if hh:
        # 更新现有户籍信息
        hh.address_group = address_group
    else:
        # 创建新的户籍信息，将当前编辑的居民设为户主
        hh = HouseholdHead(
            household_number=household_number,
            head_id=resident.id,
            address_group=address_group
        )
        db.session.add(hh)

    # 关联户籍信息
    resident.household_head = hh

    for key, value in data.items():
        if hasattr(resident, key) and key not in ['id']:
            if key in ['birth_date', 'nomination_date', 'move_out_date', 'move_in_date', 'death_date']:
                setattr(resident, key, datetime.strptime(value, '%Y-%m-%d').date() if value else None)
            else:
                setattr(resident, key, value)

    # 更新福利资格字段
    resident.welfare_eligible = bool(data.get('welfare_eligible'))
    resident.elderly_welfare_eligible = bool(int(data.get('elderly_welfare_eligible', 0)))
    resident.university_welfare_eligible = bool(int(data.get('university_welfare_eligible', 0)))
    resident.high_school_welfare_eligible = bool(int(data.get('high_school_welfare_eligible', 0)))

    try:
        db.session.commit()
        flash('更新成功', 'success')  # 添加flash消息
        return jsonify({'message': '更新成功', 'id': resident.id})
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败: {str(e)}', 'error')  # 添加flash消息
        return jsonify({'error': str(e)}), 500


@residents_bp.route('/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_resident(id):
    resident = Villager.query.get_or_404(id)
    db.session.delete(resident)
    try:
        db.session.commit()
        flash('删除成功', 'success')  # 添加flash消息
        return jsonify({'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'error')  # 添加flash消息
        return jsonify({'error': str(e)}), 500


@residents_bp.route('/save_household_head', methods=['POST'])
@login_required
@admin_required
def save_household_head():
    data = request.get_json()
    household_number = data.get('household_number')
    head_id = data.get('head_id')

    if not household_number or not head_id:
        return jsonify({'error': '户号和户主ID不能为空'}), 400

    household_head = HouseholdHead.query.filter_by(household_number=household_number).first()
    if household_head:
        household_head.head_id = head_id
    else:
        household_head = HouseholdHead(household_number=household_number, head_id=head_id,
                                       address_group=data.get('address_group', '一区'))
        db.session.add(household_head)

    try:
        db.session.commit()
        return jsonify({'message': '户主信息保存成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

        return jsonify({'error': str(e)}), 500


@residents_bp.route('/household_head_info', methods=['GET'])
@login_required
def household_head_info():
    h = request.args.get('h', '').strip()
    if not h:
        return jsonify({'error': '未提供户号'}), 400

    hh = HouseholdHead.query.filter_by(household_number=h).first()
    if hh:
        return jsonify({
            'exists': True,
            'head_name': hh.head.name,
            'address_group': hh.address_group
        })
    else:
        return jsonify({'exists': False})

        return jsonify({'error': str(e)}), 500


@residents_bp.route('/import', methods=['POST'])
@login_required
def import_residents():
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    file = request.files['file']
    if not file or not file.filename.endswith('.xlsx'):
        return jsonify({'error': '请上传Excel文件'}), 400

    try:
        df = pd.read_excel(file, sheet_name='Sheet1')
        required_columns = [
            '公民身份号码', '户号', '姓名', '性别', '民族', '公民身份号码（原始）',
            '出生年月日', '提名日', '截止提名日周岁', '户籍地详址', '社区村居委会',
            '户籍地组', '与户主关系', '电话', '银行卡号', '工区', '是否在籍'
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({'error': f'缺少必要列: {", ".join(missing_columns)}'}), 400

        success_count = 0
        error_records = []

        for _, row in df.iterrows():
            try:
                # 检查或创建户主信息
                household_head = HouseholdHead.query.filter_by(household_number=row['户号']).first()
                if not household_head:
                    # 找到该户号下的户主（与户主关系为"户主"的记录）
                    household_data = df[df['户号'] == row['户号']]
                    head_data = household_data[household_data['与户主关系'] == '户主'].iloc[0]

                    # 创建户主的村民记录
                    head_resident = create_or_update_resident(head_data)

                    # 创建户主信息
                    household_head = HouseholdHead(
                        household_number=row['户号'],
                        head_id=head_resident.id,
                        address_group=row['户籍地组']
                    )
                    db.session.add(household_head)

                # 创建或更新村民信息
                resident = create_or_update_resident(row)
                resident.household_head = household_head

                success_count += 1

            except Exception as e:
                error_records.append({
                    'name': row['姓名'],
                    'id_card': row['公民身份号码'],
                    'error': str(e)
                })
                continue

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'成功导入 {success_count} 条记录',
            'errors': error_records if error_records else None
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'导入失败: {str(e)}'}), 500


def create_or_update_resident(row):
    """创建或更新村民记录"""
    resident = Villager.query.filter_by(id_card=row['公民身份号码']).first()
    if not resident:
        resident = Villager()
        db.session.add(resident)

    resident.name = row['姓名']
    resident.id_card = row['公民身份号码']
    resident.original_id_card = row['公民身份号码（原始）']
    resident.gender = row['性别']
    resident.ethnicity = row['民族']
    resident.birth_date = pd.to_datetime(row['出生年月日']).date()
    resident.nomination_date = pd.to_datetime(row['提名日']).date() if pd.notna(row['提名日']) else None
    resident.nomination_age = int(row['截止提名日周岁']) if pd.notna(row['截止提名日周岁']) else None
    resident.detailed_address = row['户籍地详址']
    resident.community = row['社区村居委会']
    resident.relationship = row['与户主关系']
    resident.phone = str(row['电话']) if pd.notna(row['电话']) else None
    resident.bank_account = str(row['银行卡号'])
    resident.area = row['工区']
    resident.residency_status = True if row['是否在籍'] == '是' else False
    resident.remarks = row.get('remarks', '')  # 添加备注字段处理

    return resident
