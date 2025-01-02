from flask import Blueprint, render_template, request, jsonify
from models import db, Villager, HouseholdHead
import pandas as pd
from wraps import login_required, admin_required

import_bp = Blueprint('import', __name__)

def clean_string(value):
    """清理字符串中的特殊字符"""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        # 处理数字类型的身份证号
        return str(int(value))  # 移除可能的小数点
    return str(value).strip().replace('\xa0', '').replace('`', '')

def validate_id_card(id_card):
    """验证身份证号格式"""
    if not id_card:
        return False
    id_card = str(id_card).strip()
    # 处理18位身份证
    if len(id_card) == 18:
        return True
    # 处理15位身份证
    if len(id_card) == 15:
        return True
    return False

@import_bp.route('/view')
@login_required
def import_view():
    return render_template('import.html')

@import_bp.route('/upload', methods=['POST'])
@login_required
@admin_required
def import_data():
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
        
    file = request.files['file']
    if not file or not file.filename.endswith('.xlsx'):
        return jsonify({'error': '请上传Excel文件'}), 400

    success_count = 0
    error_records = []

    try:
        # 添加调试信息
        print(f"开始读取文件: {file.filename}")
        df = pd.read_excel(file)
        print(f"Excel列名: {df.columns.tolist()}")
        
        # 修改必需列的检查逻辑，使用实际的Excel列名
        required_columns = {
            '公民身份号码': '公民身份号码',
            '户号': '户号',
            '姓名': '姓名',
            '性别': '性别',
            '民族': '民族',
            '公民身份号码（原始）': '公民身份号码（原始）',  # 修改为实际的列名
            '出生年月日': '出生年月日',
            '提名日': '提名日',  # 修改为实际的列名
            '截止提名日周岁': '截止提名日周岁',  # 修改为实际的列名
            '户籍地详址': '户籍地详址',  # 修改为实际的列名
            '社区村居委会': '社区村居委会',  # 修改为实际的列名
            '户籍地组': '户籍地组',  # 修改为实际的列名
            '与户主关系': '与户主关系',
            '电话': '电话',
            '银行卡号': '银行卡号',
            '工区': '工区',
            '是否在籍': '是否在籍'
        }
        
        # 创建列名映射
        column_mapping = {}
        for excel_col, db_col in required_columns.items():
            if excel_col in df.columns:
                column_mapping[excel_col] = db_col
            else:
                return jsonify({'error': f'缺少必要列: {excel_col}'}), 400

        print(f"列名映射: {column_mapping}")

        # 预处理数据，清理所有字符串列中的特殊字符
        for column in df.columns:
            if df[column].dtype == 'object':
                df[column] = df[column].apply(lambda x: clean_string(x) if pd.notna(x) else x)

        # 预处理：按户号分组处理数据
        household_groups = df.groupby('户号')
        
        for household_number, group in household_groups:
            try:
                print(f"处理户号: {household_number}")
                # 清理户号中的特殊字符
                clean_household_number = clean_string(household_number)
                
                # 检查现有户主信息
                household_head = HouseholdHead.query.filter_by(household_number=clean_household_number).first()
                
                if not household_head:
                    # 按照关系字段寻找户主
                    head_records = group[group['与户主关系'].str.contains('户主', na=False)]
                    print("head_records",head_records)
                    if len(head_records) == 1:
                        head_data = head_records.iloc[0]
                        head_relationship = '户主'
                    elif len(head_records) > 1:
                        # 多个户主，记录错误并选择第一个
                        head_data = head_records.iloc[0]
                        head_relationship = '户主'
                        error_records.append({
                            'name': head_data['姓名'],
                            'id_card': head_data['公民身份号码'],
                            'error': '同一户号存在多个户主，默认选择第一条记录作为户主'
                        })
                    else:
                        # 没有明确的户主，尝试找到夫或妻
                        head_records = group[group['与户主关系'].str.contains('夫|妻', na=False)]
                        if len(head_records) == 1:
                            head_data = head_records.iloc[0]
                            head_relationship = '户主'
                        elif len(head_records) > 1:
                            # 多个夫或妻，记录错误并选择第一个
                            head_data = head_records.iloc[0]
                            head_relationship = '户主'
                            error_records.append({
                                'name': head_data['姓名'],
                                'id_card': head_data['公民身份号码'],
                                'error': '同一户号存在多个夫/妻，默认选择第一条记录作为户主'
                            })
                        else:
                            # 仍没有明确的户主，选择第一条记录
                            head_data = group.iloc[0]
                            head_relationship = '户主'
                            error_records.append({
                                'name': head_data['姓名'],
                                'id_card': head_data['公民身份号码'],
                                'error': '同一户号没有明确的户主，默认选择第一条记录作为户主'
                            })
                    
                    try:
                        # 创建户主的村民记录
                        head_resident = create_or_update_resident(head_data, head_relationship, column_mapping)
                        db.session.flush()  # 确保获得head_resident.id
                        
                        if not head_resident.id:
                            raise ValueError("创建户主记录失败：无法获取户主ID")
                        
                        # 创建户主信息
                        household_head = HouseholdHead(
                            household_number=clean_household_number,
                            head_id=head_resident.id,
                            address_group=clean_string(head_data['户籍地组'])
                        )
                        db.session.add(household_head)
                        db.session.flush()
                    except Exception as e:
                        db.session.rollback()
                        print(f"创建户主记录失败: {str(e)}")
                        error_records.append({
                            'name': head_data['姓名'],
                            'id_card': head_data['公民身份号码'],
                            'error': f'创建户主记录失败: {str(e)}'
                        })
                        continue

                # 处理该户所有成员
                for _, row in group.iterrows():
                    try:
                        relationship = clean_string(row['与户主关系']) or '成员'
                        resident = create_or_update_resident(row, relationship, column_mapping)
                        resident.household_head = household_head
                        success_count += 1
                    except Exception as e:
                        print(f"处理成员记录失败: {str(e)}")
                        error_records.append({
                            'name': row['姓名'],
                            'id_card': row['公民身份号码'],
                            'error': str(e)
                        })
                        continue

            except Exception as e:
                print(f"处理户籍信息失败: {str(e)}")
                error_records.append({
                    'name': f'户号 {household_number}',
                    'id_card': 'N/A',
                    'error': f'处理户籍信息失败: {str(e)}'
                })
                continue

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'成功导入 {success_count} 条记录',
            'errors': error_records if error_records else None
        })

    except Exception as e:
        print(f"导入过程发生错误: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'导入失败: {str(e)}',
            'errors': error_records
        }), 500

@import_bp.route('/check', methods=['POST'])
@login_required
@admin_required
def check_data():
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
        
    file = request.files['file']
    if not file or not file.filename.endswith('.xlsx'):
        return jsonify({'error': '请上传Excel文件'}), 400

    try:
        df = pd.read_excel(file)
        print("读取到的列名:", df.columns.tolist())  # 添加调试信息
        
        # 检查必需的列
        if '公民身份号码' not in df.columns:
            return jsonify({'error': '未找到"公民身份号码"列，请检查Excel文件格式'}), 400
        
        # 预处理数据，清理所有字符串列中的特殊字符
        if df['公民身份号码'].dtype == 'float64' or df['公民身份号码'].dtype == 'int64':
            # 如果是数字格式，转换为字符串并移除小数点
            df['公民身份号码'] = df['公民身份号码'].apply(lambda x: str(int(x)) if pd.notna(x) else None)
        else:
            # 如果是字符串格式，清理特殊字符
            df['公民身份号码'] = df['公民身份号码'].apply(lambda x: clean_string(x) if pd.notna(x) else None)
            
        # 获取有效的身份证号
        id_cards = df['公民身份号码'].dropna().unique()
        
        # 查找已存在的记录
        existing_records = []
        total_records = len(df)
        update_records = 0
        
        for id_card in id_cards:
            if not id_card or pd.isna(id_card):
                continue
                
            try:
                # 清理身份证号
                clean_id = clean_string(id_card)
                if validate_id_card(clean_id):
                    villager = Villager.query.filter_by(id_card=clean_id).first()
                    if villager:
                        update_records += 1
                        existing_records.append({
                            'name': villager.name,
                            'id_card': villager.id_card,
                            'update_time': villager.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                        })
            except Exception as e:
                print(f"处理身份证号时出错: {id_card}, 错误: {str(e)}")
                continue
        
        return jsonify({
            'total': total_records,
            'new': total_records - update_records,
            'update': update_records,
            'existing_records': existing_records
        })
    
    except Exception as e:
        import traceback
        print(f"检查数据时发生错误: {str(e)}")
        print(traceback.format_exc())  # 打印详细错误堆栈
        return jsonify({'error': f'检查数据时发生错误: {str(e)}'}), 500

def create_or_update_resident(row, relationship, column_mapping):
    """创建或更新村民记录"""
    try:
        # 清理身份证号
        id_card = clean_string(row['公民身份号码'])
        if not validate_id_card(id_card):
            raise ValueError(f"无效的身份证号: {id_card}")

        resident = Villager.query.filter_by(id_card=id_card).first()
        if not resident:
            resident = Villager()
            db.session.add(resident)

        # 基本信息 - 使用clean_string函数清理数据
        resident.name = clean_string(row['姓名'])
        resident.id_card = id_card
        resident.original_id_card = clean_string(row['公民身份号码（原始）'])
        resident.gender = clean_string(row['性别'])
        resident.ethnicity = clean_string(row['民族'])

        # 日期和数字处理
        try:
            resident.birth_date = pd.to_datetime(row['出生年月日']).date()
        except:
            print(f"出生日期格式错误: {row['出生年月日']}")
            resident.birth_date = None

        try:
            resident.nomination_date = pd.to_datetime(row['提名日']).date() if pd.notna(row['提名日']) else None
        except:
            print(f"提名日期格式错误: {row['提名日']}")
            resident.nomination_date = None

        # 其他字段
        resident.age_at_nomination = int(float(row['截止提名日周岁'])) if pd.notna(row['截止提名日周岁']) else None
        resident.detailed_address = clean_string(row['户籍地详址'])
        resident.community = clean_string(row['社区村居委会'])
        resident.relationship = clean_string(relationship)
        resident.phone = clean_string(row['电话'])
        
        # 银行卡号处理
        if pd.notna(row['银行卡号']):
            bank_account = str(row['银行卡号'])
            if '.' in bank_account:
                bank_account = str(int(float(bank_account)))
            resident.bank_account = clean_string(bank_account)
        else:
            # 默认使用户主的银行卡号
            if resident.household_head:
                resident.bank_account = resident.household_head.head.bank_account
            else:
                resident.bank_account = '0'

        resident.area = clean_string(row['工区'])
        resident.residency_status = True if clean_string(str(row['是否在籍'])).lower() in ['是', '1', 'true'] else False

        return resident
    except Exception as e:
        print(f"创建/更新居民记录时出错: {str(e)}")
        raise
