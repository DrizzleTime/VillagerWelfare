import random
import string

from faker import Faker

from app import app, db
from models import Villager, HouseholdHead  # 保持导入不变

fake = Faker(['zh_CN'])


def generate_id_card():
    """生成18位身份证号"""
    # 随机地区码(江苏省江阴市)
    area_code = "320281"
    # 随机出生日期
    birth_date = fake.date_of_birth(minimum_age=40, maximum_age=90)
    date_str = birth_date.strftime("%Y%m%d")
    # 随机序号
    sequence = ''.join(random.choices(string.digits, k=3))
    # 验证码（简化处理）
    check_code = random.choice(string.digits + 'X')
    return f"{area_code}{date_str}{sequence}{check_code}"


def generate_bank_account():
    """生成16位银行账号"""
    return ''.join(random.choices(string.digits, k=16))


def generate_household_number(existing_numbers):
    """生成唯一的户号"""
    while True:
        household_number = f"HH{''.join(random.choices(string.digits, k=4))}"
        if household_number not in existing_numbers:
            return household_number


def generate_villagers(count=1000):
    """生成指定数量的村民数据"""
    # 生成一些户号，每户1-5人，确保唯一
    household_numbers = set()
    while len(household_numbers) < count // 3:
        household_numbers.add(generate_household_number(existing_numbers=household_numbers))
    household_numbers = list(household_numbers)

    areas = ['一区', '二区', '三区', '四区', '五区']
    address_groups = [f'{i}组' for i in range(1, 11)]

    with app.app_context():
        existing_id_cards = set(
            r.id_card for r in Villager.query.with_entities(Villager.id_card).all())
        generated_id_cards = set()

        for household in household_numbers:
            # 随机决定此户的人数
            num_members = random.randint(1, 5)

            # 生成户主
            while True:
                id_card = generate_id_card()
                if id_card not in existing_id_cards and id_card not in generated_id_cards:
                    generated_id_cards.add(id_card)
                    break

            villager = Villager(
                name=fake.name(),
                id_card=id_card,
                gender=random.choice(['男', '女']),
                birth_date=fake.date_of_birth(minimum_age=40, maximum_age=90),
                ethnicity='汉族',
                phone=fake.phone_number(),
                bank_account=generate_bank_account(),
                area=random.choice(areas),
                detailed_address=fake.address(),
                relationship='户主',
                welfare_eligible=random.choice([True, False]),
                nomination_date=fake.date_between(
                    start_date='-5y', end_date='today'),
                residency_status=True
            )
            db.session.add(villager)
            db.session.flush()  # 保持不变

            # 创建户主记录
            household_head = HouseholdHead(
                household_number=household,
                head_id=villager.id,
                address_group=random.choice(address_groups)  # 设置 address_group
            )
            db.session.add(household_head)

            # 将当前居民设为户主并关联至上面创建的户主记录
            villager.relationship = '户主'
            villager.household_head = household_head

            # 生成其他成员
            for _ in range(num_members - 1):
                household_relationship = random.choice(['配偶', '子', '女', '儿媳', '女婿'])
                while True:
                    id_card = generate_id_card()
                    if id_card not in existing_id_cards and id_card not in generated_id_cards:
                        generated_id_cards.add(id_card)
                        break

                member = Villager(
                    name=fake.name(),
                    id_card=id_card,
                    gender=random.choice(['男', '女']),
                    birth_date=fake.date_of_birth(minimum_age=40, maximum_age=90),
                    ethnicity='汉族',
                    phone=fake.phone_number(),
                    bank_account=generate_bank_account(),
                    area=random.choice(areas),
                    detailed_address=fake.address(),
                    relationship=household_relationship,
                    welfare_eligible=random.choice([True, False]),
                    nomination_date=fake.date_between(
                        start_date='-5y', end_date='today'),
                    residency_status=True
                )

                # 关联到户主
                member.household_head = household_head

                db.session.add(member)

            # 随机设置一些特殊状态
            if random.random() < 0.1:  # 10%的概率搬出
                villager.moved_out = True
                villager.move_out_date = fake.date_between(
                    start_date='-2y', end_date='today')
                villager.move_out_location = fake.address()
                villager.residency_status = False

            if random.random() < 0.05:  # 5%的概率去世
                villager.deceased = True
                villager.death_date = fake.date_between(
                    start_date='-1y', end_date='today')
                villager.residency_status = False
                villager.welfare_eligible = False

        try:
            db.session.commit()
            print(f"成功生成 {count} 条村民数据")
        except Exception as e:
            db.session.rollback()
            print(f"数据生成失败: {str(e)}")


if __name__ == '__main__':
    generate_villagers()
