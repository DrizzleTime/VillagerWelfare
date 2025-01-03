from datetime import datetime
from io import BytesIO
import pandas as pd
from flask import Blueprint, render_template, request, send_file, jsonify
from models import Villager, WelfareRecord, db, WelfareConfig, UniversitySubsidy, HighSchoolReimbursement
from sqlalchemy import and_, extract
from wraps import login_required

export_bp = Blueprint('export', __name__)


@export_bp.route('/')
@login_required
def export_view():
    current_year = datetime.now().year
    return render_template('export.html', current_year=current_year)


@export_bp.route('/by_age')
@login_required
def export_by_age():
    try:

        # 获取参数并进行日期转换
        nomination_date = datetime.strptime(
            request.args.get('nomination_date'), '%Y-%m-%d').date()
        min_age = int(request.args.get('min_age', 0))

        # 修改数据库中所有的数据的提名日为传入的提名日
        Villager.query.update({Villager.nomination_date: nomination_date})
        db.session.commit()

        # 获取所有满足提名日期条件的村民
        villagers = Villager.query.filter(
            Villager.nomination_date == nomination_date,
            Villager.birth_date.isnot(None)  # 确保有出生日期
        ).all()

        # 过滤出符合年龄条件的村民
        filtered_villagers = []
        for v in villagers:
            try:
                # 计算提名日期时的年龄
                birth_date = v.birth_date
                age = nomination_date.year - birth_date.year
                # 检查是否已过生日
                if (nomination_date.month, nomination_date.day) < (birth_date.month, birth_date.day):
                    age -= 1

                if age >= min_age:
                    filtered_villagers.append(v)
                    print(f"符合条件的村民: {v.name}, 年龄: {age}岁")
            except Exception as e:
                print(f"处理村民 {v.name} 时出错: {str(e)}")
                continue

        print(f"查询到的记录数: {len(filtered_villagers)}")

        if not filtered_villagers:
            print("未找到符合条件的记录")
            # 返回一个空的DataFrame，但包含所有列
            empty_df = pd.DataFrame(columns=[
                '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期',
                '提名日', '截止提名日周岁', '户籍地详细地址', '户籍地组',
                '与户主的关系', '电话', '工区', '银行卡号', '在籍状态'  # 新增字段
            ])
            return export_dataframe_to_excel(empty_df, f'年龄大于{min_age}岁的人员信息_无数据')

        # 转换为DataFrame
        data = []
        for v in filtered_villagers:
            birth_date = v.birth_date
            age = nomination_date.year - birth_date.year
            if (nomination_date.month, nomination_date.day) < (birth_date.month, birth_date.day):
                age -= 1

            row = {
                '公民身份证号码': v.id_card,
                '户号': v.household_head.household_number if v.household_head else '',
                '姓名': v.name,
                '性别': v.gender,
                '民族': v.ethnicity,
                '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
                '提名日': v.nomination_date.strftime('%Y-%m-%d') if v.nomination_date else '',
                '截止提名日周岁': age,  # 使用计算得到的年龄
                '户籍地详细地址': v.detailed_address,
                '户籍地组': v.household_head.address_group if v.household_head else '',
                '与户主的关系': v.relationship,
                '电话': v.phone,
                '工区': v.area,
                '银行卡号': v.bank_account,
                '在籍状态': '是' if v.residency_status else '否'  # 新增字段
            }
            data.append(row)
            print(f"添加记录: {v.name} - {age}岁")

        df = pd.DataFrame(data)
        return export_dataframe_to_excel(df, f'年龄大于{min_age}岁的人员信息')

    except Exception as e:
        print(f"导出过程发生错误: {str(e)}")
        empty_df = pd.DataFrame(columns=['错误信息'])
        empty_df.loc[0] = [f'导出失败: {str(e)}']
        return export_dataframe_to_excel(empty_df, '导出错误')


@export_bp.route('/deceased')
@login_required
def export_deceased():
    year = request.args.get('year', datetime.now().year, type=int)
    villagers = Villager.query.filter(
        extract('year', Villager.death_date) == year,
        Villager.deceased == True
    ).all()

    # 即使没有数据也返回带表头的Excel
    if not villagers:
        empty_df = pd.DataFrame(columns=[
            '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期', '死亡日期',
            '户籍地详细地址', '户籍地组', '与户主的关系', '电话', '工区', '银行卡号',
            '在籍状态'  # 新增字段
        ])
        return export_dataframe_to_excel(empty_df, f'{year}年度死亡人员信息')

    data = []
    for v in villagers:
        row = {
            '公民身份证号码': v.id_card,
            '户号': v.household_head.household_number if v.household_head else '',
            '姓名': v.name,
            '性别': v.gender,
            '民族': v.ethnicity,
            '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
            '死亡日期': v.death_date.strftime('%Y-%m-%d') if v.death_date else '',
            '户籍地详细地址': v.detailed_address,
            '户籍地组': v.household_head.address_group if v.household_head else '',
            '与户主的关系': v.relationship,
            '电话': v.phone,
            '工区': v.area,
            '银行卡号': v.bank_account,
            '在籍状态': '是' if v.residency_status else '否'  # 新增字段
        }
        data.append(row)

    df = pd.DataFrame(data)
    return export_dataframe_to_excel(df, f'{year}年度死亡人员信息')


@export_bp.route('/newborn')
@login_required
def export_newborn():
    year = request.args.get('year', datetime.now().year, type=int)
    villagers = Villager.query.filter(
        extract('year', Villager.birth_date) == year
    ).all()

    if not villagers:
        empty_df = pd.DataFrame(columns=[
            '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期',
            '户籍地详细地址', '户籍地组', '与户主的关系', '电话', '工区', '银行卡号',
            '在籍状态'  # 新增字段
        ])
        return export_dataframe_to_excel(empty_df, f'{year}年度出生人员信息')

    data = []
    for v in villagers:
        row = {
            '公民身份证号码': v.id_card,
            '户号': v.household_head.household_number if v.household_head else '',
            '姓名': v.name,
            '性别': v.gender,
            '民族': v.ethnicity,
            '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
            '户籍地详细地址': v.detailed_address,
            '户籍地组': v.household_head.address_group if v.household_head else '',
            '与户主的关系': v.relationship,
            '电话': v.phone,
            '工区': v.area,
            '银行卡号': v.bank_account,
            '在籍状态': '是' if v.residency_status else '否'  # 新增字段
        }
        data.append(row)

    df = pd.DataFrame(data)
    return export_dataframe_to_excel(df, f'{year}年度出生人员信息')


@export_bp.route('/moved_out')
@login_required
def export_moved_out():
    year = request.args.get('year', datetime.now().year, type=int)
    villagers = Villager.query.filter(
        extract('year', Villager.move_out_date) == year,
        Villager.moved_out == True
    ).all()

    if not villagers:
        empty_df = pd.DataFrame(columns=[
            '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期',
            '户籍地详细地址', '户籍地组', '与户主的关系', '电话', '工区', '银行卡号',
            '迁出日期', '迁出地', '在籍状态'  # 新增字段
        ])
        return export_dataframe_to_excel(empty_df, f'{year}年度迁出人员信息')

    data = []
    for v in villagers:
        row = {
            '公民身份证号码': v.id_card,
            '户号': v.household_head.household_number if v.household_head else '',
            '姓名': v.name,
            '性别': v.gender,
            '民族': v.ethnicity,
            '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
            '户籍地详细地址': v.detailed_address,
            '户籍地组': v.household_head.address_group if v.household_head else '',
            '与户主的关系': v.relationship,
            '电话': v.phone,
            '工区': v.area,
            '银行卡号': v.bank_account,
            '迁出日期': v.move_out_date.strftime('%Y-%m-%d') if v.move_out_date else '',
            '迁出地': v.move_out_location or '',
            '在籍状态': '是' if v.residency_status else '否'  # 新增字段
        }
        data.append(row)

    df = pd.DataFrame(data)
    return export_dataframe_to_excel(df, f'{year}年度迁出人员信息')


@export_bp.route('/moved_in')
@login_required
def export_moved_in():
    year = request.args.get('year', datetime.now().year, type=int)
    villagers = Villager.query.filter(
        extract('year', Villager.move_in_date) == year,
        Villager.moved_in == True
    ).all()

    if not villagers:
        empty_df = pd.DataFrame(columns=[
            '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期',
            '户籍地详细地址', '户籍地组', '与户主的关系', '电话', '工区', '银行卡号',
            '迁入日期', '迁入地', '在籍状态'  # 新增字段
        ])
        return export_dataframe_to_excel(empty_df, f'{year}年度迁入人员信息')

    data = []
    for v in villagers:
        row = {
            '公民身份证号码': v.id_card,
            '户号': v.household_head.household_number if v.household_head else '',
            '姓名': v.name,
            '性别': v.gender,
            '民族': v.ethnicity,
            '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
            '户籍地详细地址': v.detailed_address,
            '户籍地组': v.household_head.address_group if v.household_head else '',
            '与户主的关系': v.relationship,
            '电话': v.phone,
            '工区': v.area,
            '银行卡号': v.bank_account,
            '迁入日期': v.move_in_date.strftime('%Y-%m-%d') if v.move_in_date else '',
            '迁入地': v.move_in_location or '',
            '在籍状态': '是' if v.residency_status else '否'  # 新增字段
        }
        data.append(row)

    df = pd.DataFrame(data)
    return export_dataframe_to_excel(df, f'{year}年度迁入人员信息')


@export_bp.route('/welfare_export', methods=['POST'])
@login_required
def welfare_export():
    export_type = request.form.get('export_type')
    year_input = int(request.form.get('year_input'))
    filter_by = request.form.get('filter_by')

    # 检查是否配置了该年份的福利信息
    config = WelfareConfig.query.filter_by(year=year_input).first()
    if not config:
        return jsonify({
            'error': f'未找到{year_input}年度的福利配置信息，请先配置该年度的福利信息',
            'need_config': True
        }), 404

    filename = f"welfare_export_{
        datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    villagers = Villager.query.all()

    # 初始化各个福利项目的数据
    basic_data = []
    elderly_data = []
    university_data = []
    highschool_data = []
    main_data = []  # 新增总表数据
    # bank_account_data = []  # 移除银行卡分组数据

    today = datetime.now().date()  # 获取当前日期

    for v in villagers:
        config = WelfareConfig.query.filter_by(year=year_input).first()
        if not config:
            continue

        # 基础福利
        basic_welfare = calculate_basic_welfare(v, year_input)
        basic_data.append({
            '公民身份证号码': v.id_card,
            '姓名': v.name,
            '年份': config.year,
            '基础福利金额': basic_welfare['amount'],
            '发放日期': config.basic_welfare_issue_date.strftime('%Y-%m-%d') if config.basic_welfare_issue_date else '',
            '是否发放': '是' if (
                    config.basic_welfare_issue_date and config.basic_welfare_issue_date <= today) else '否',
            '备注': basic_welfare['message']  # 添加备注说明金额减半原因
        })

        # 养老金
        elderly_welfare = calculate_elderly_welfare(v, year_input)
        if elderly_welfare['eligible']:
            elderly_data.append({
                '公民身份证号码': v.id_card,
                '姓名': v.name,
                '年份': config.year,
                '养老金金额': elderly_welfare['amount'],
                '发放日期': config.elderly_welfare_issue_date.strftime(
                    '%Y-%m-%d') if config.elderly_welfare_issue_date else '',  # 修改这里
                '是否发放': '是' if (
                        config.elderly_welfare_issue_date and config.elderly_welfare_issue_date <= today) else '否'
                # 修改这里
            })

        # 大学补贴
        university_total = 0
        for subsidy in v.university_subsidies:
            university_data.append({
                '公民身份证号码': v.id_card,
                '姓名': v.name,
                '学校名称': subsidy.school_name,
                '金额': subsidy.amount,
                '发放日期': subsidy.issue_date.strftime('%Y-%m-%d') if subsidy.issue_date else '',
                '是否发放': '是' if (subsidy.issue_date and subsidy.issue_date <= today) else '否'
            })
            university_total += subsidy.amount

        # 高中报销
        highschool_total = 0
        for reimbursement in v.high_school_reimbursements:
            highschool_data.append({
                '公民身份证号码': v.id_card,
                '姓名': v.name,
                '学校名称': reimbursement.school_name,
                '金额': reimbursement.amount,
                '发放日期': reimbursement.issue_date.strftime('%Y-%m-%d') if reimbursement.issue_date else '',
                '是否发放': '是' if (reimbursement.issue_date and reimbursement.issue_date <= today) else '否'
            })
            highschool_total += reimbursement.amount

        # 计算合计福利金额
        total_welfare = basic_welfare['amount'] + \
            elderly_welfare['amount'] + university_total + highschool_total

        # 获取年龄
        age = v.calculate_age()

        # 收集总表数据
        main_data.append({
            '公民身份证号码': v.id_card,
            '户号': v.household_head.household_number if v.household_head else '',
            '姓名': v.name,
            '性别': v.gender,
            '民族': v.ethnicity,
            '出生日期': v.birth_date.strftime('%Y-%m-%d') if v.birth_date else '',
            '户籍地详细地址': v.detailed_address,
            '户籍地组': v.household_head.address_group if v.household_head else '',
            '与户主的关系': v.relationship,
            '电话': v.phone,
            '工区': v.area,
            '银行卡号': v.bank_account,
            '在籍状态': '是' if v.residency_status else '否',
            '年龄': age,
            '基础福利金额': basic_welfare['amount'],
            '基础福利备注': basic_welfare['message'],
            '养老金金额': elderly_welfare['amount'],
            '大学补贴总额': university_total,
            '高中报销总额': highschool_total,
            '合计福利金额': total_welfare,
            '福利银行卡号': v.welfare_bank_account or (v.household_head.head.bank_account if v.household_head else '') or v.bank_account or '0'
        })

    # 转换为 DataFrame
    main_df = pd.DataFrame(main_data)  # 转换总表数据

    # 根据 filter_by 参数生成相应的 DataFrame
    if filter_by == 'bank_account':
        if not main_df.empty:
            # 按福利银行卡号分组并汇总
            bank_account_df = main_df.groupby('福利银行卡号').agg({
                '公民身份证号码': 'first',
                '户号': 'first',
                '姓名': 'first',
                '性别': 'first',
                '民族': 'first',
                '出生日期': 'first',
                '户籍地详细地址': 'first',
                '户籍地组': 'first',
                '与户主的关系': 'first',
                '电话': 'first',
                '工区': 'first',
                '在籍状态': 'first',
                '年龄': 'first',
                '基础福利金额': 'sum',
                '养老金金额': 'sum',
                '大学补贴总额': 'sum',
                '高中报销总额': 'sum',
                '合计福利金额': 'sum'
            }).reset_index()
            bank_account_df = bank_account_df.rename(
                columns={'福利银行卡号': '银行卡号'})  # 重命名列名为"银行卡号"
    # else:
    # main_df 已经是总表

    # 转换其他 DataFrame
    basic_df = pd.DataFrame(basic_data)
    elderly_df = pd.DataFrame(elderly_data)
    university_df = pd.DataFrame(university_data)
    highschool_df = pd.DataFrame(highschool_data)

    # 创建Excel文件并添加多个工作表
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if filter_by == 'bank_account' and not main_df.empty:
            bank_account_df.to_excel(
                writer, sheet_name='按银行卡导出', index=False)  # 写入按银行卡导出
        elif filter_by != 'bank_account' and not main_df.empty:
            # 重新排序列，确保银行卡号和福利银行卡号在合适的位置
            columns_order = [
                '公民身份证号码', '户号', '姓名', '性别', '民族', '出生日期',
                '户籍地详细地址', '户籍地组', '与户主的关系', '电话', '工区',
                '银行卡号', '福利银行卡号', '在籍状态', '年龄', '基础福利金额',
                '基础福利备注', '养老金金额', '大学补贴总额', '高中报销总额', '合计福利金额'
            ]
            main_df = main_df[columns_order]
            main_df.to_excel(writer, sheet_name='总表', index=False)  # 写入总表

        if not basic_df.empty:
            basic_df.to_excel(writer, sheet_name='基础福利', index=False)
        if not elderly_df.empty:
            elderly_df.to_excel(writer, sheet_name='养老金', index=False)
        if not university_df.empty:
            university_df.to_excel(writer, sheet_name='大学补贴', index=False)
        if not highschool_df.empty:
            highschool_df.to_excel(writer, sheet_name='高中报销', index=False)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# 移除或注释掉 create_welfare_by_card_dataframe 函数
# def create_welfare_by_card_dataframe(records):
#     """创建按银行卡分组的福利记录DataFrame"""
#     # ...existing code...
#     pass

def export_villagers_to_excel(villagers, filename, **kwargs):
    """生成Excel文件"""
    # ...existing code...
    # 此函数现在不再使用，因为导出逻辑已在 `welfare_export` 中处理
    pass


def calculate_basic_welfare(villager, year):
    config = WelfareConfig.query.filter_by(year=year).first()
    if not config or not villager.welfare_eligible:
        return {'eligible': False, 'amount': 0, 'message': '不符合福利条件'}

    year = datetime.now().year
    amount = config.basic_welfare_amount
    message = '享受全额基础福利'

    # 检查是否需要减半福利金额
    need_half = False

    # 当年出生的情况
    if villager.birth_date and villager.birth_date.year == year:
        if villager.birth_date.month > 6:  # 下半年出生
            need_half = True
            message = f'{year}年{villager.birth_date.month}月出生，发放半年基础福利'

    # 当年死亡的情况
    elif villager.deceased and villager.death_date and villager.death_date.year == year:
        if villager.death_date.month <= 6:  # 上半年死亡
            need_half = True
            message = f'{year}年{villager.death_date.month}月死亡，发放半年基础福利'

    # 当年迁入的情况
    elif villager.moved_in and villager.move_in_date and villager.move_in_date.year == year:
        if villager.move_in_date.month > 6:  # 下半年迁入
            need_half = True
            message = f'{year}年{villager.move_in_date.month}月迁入，发放半年基础福利'

    # 当年迁出的情况
    elif villager.moved_out and villager.move_out_date and villager.move_out_date.year == year:
        if villager.move_out_date.month <= 6:  # 上半年迁出
            need_half = True
            message = f'{year}年{villager.move_out_date.month}月迁出，发放半年基础福利'

    if need_half:
        amount /= 2

    return {
        'eligible': villager.welfare_eligible,
        'amount': amount,
        'message': message
    }


def calculate_elderly_welfare(villager, year):
    config = WelfareConfig.query.filter_by(year=year).first()
    if not config or not config.elderly_welfare_issue_date:
        return {'eligible': False, 'amount': 0, 'stage': None}

    # 计算发放日期时的年龄
    issue_date = config.elderly_welfare_issue_date
    issue_date = config.elderly_welfare_issue_date
    age_at_issue = (issue_date.year - villager.birth_date.year) + 1  # 修改为 +1，不再考虑月份日判断

    amount = 0
    stage = None

    if age_at_issue >= 70:
        if age_at_issue < 80:
            amount = config.elderly_welfare_stage1_amount
            stage = 'stage1'
        elif age_at_issue < 90:
            amount = config.elderly_welfare_stage2_amount
            stage = 'stage2'
        elif age_at_issue < 100:
            amount = config.elderly_welfare_stage3_amount
            stage = 'stage3'
        else:
            amount = config.elderly_welfare_stage4_amount
            stage = 'stage4'

    return {'eligible': age_at_issue >= 70, 'amount': amount, 'stage': stage}


def export_dataframe_to_excel(df, filename):
    """将DataFrame导出为Excel文件"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{filename}.xlsx'
    )


def create_welfare_records_dataframe(records):
    """创建福利记录DataFrame"""
    data = []
    for record in records:
        villager = record.villager
        row = get_villager_base_info(villager)
        row.update({
            '福利项目': record.type,
            '福利金额': record.amount,
            '是否发放': '是' if record.issued else '否',
            '发放日期': record.issue_date.strftime('%Y-%m-%d') if record.issue_date else '',
            '银行账户': record.bank_account  # 新增字段
        })
        data.append(row)
    return pd.DataFrame(data)


def get_villager_base_info(villager):
    """获取村民基本信息"""
    return {
        '公民身份证号码': villager.id_card,
        '户号': villager.household_head.household_number if villager.household_head else '',
        '姓名': villager.name,
        '性别': villager.gender,
        '民族': villager.ethnicity,
        '出生日期': villager.birth_date.strftime('%d/%m/%Y'),
        '提名日': villager.nomination_date.strftime('%Y-%m-%d') if villager.nomination_date else '',
        '截止提名日周岁': villager.nomination_age,
        '户籍地详细地址': villager.detailed_address,
        '户籍地组': villager.household_head.address_group if villager.household_head else '',
        '与户主的关系': villager.relationship,
        '电话': villager.phone,
        '工区': villager.area,
        '银行卡号': villager.bank_account,
        '在籍状态': '是' if villager.residency_status else '否'  # 新增字段
    }
