import os
from trello import TrelloClient
from datetime import datetime, timedelta

# ===== 第1部分：配置你的Trello账号 =====
API_KEY = ""
TOKEN = ""

# ===== 第2部分：连接到Trello =====
client = TrelloClient(
    api_key=API_KEY,
    token=TOKEN
)

# ===== 第3部分：找到你的看板 =====
boards = client.list_boards()
target_board = None
for board in boards:
    if board.name == "无人机巡检系统开发":
        target_board = board
        break

if target_board is None:
    print("❌ 没有找到名为'无人机巡检系统开发'的看板，请先创建！")
    exit()

print(f"✅ 找到看板：{target_board.name}")

# ===== 第4部分：获取三个列表的ID =====
lists = target_board.list_lists()
list_map = {}
for lst in lists:
    list_map[lst.name] = lst.id
    print(f"📋 列表：{lst.name} (ID: {lst.id})")

# 获取列表对象（用于后续移动卡片）
todo_list = None
doing_list = None
done_list = None
for lst in lists:
    if lst.name == "待办":
        todo_list = lst
    elif lst.name == "进行中":
        doing_list = lst
    elif lst.name == "已完成":
        done_list = lst


# ===== 新增：获取或创建标签（用于风险标记） =====
def get_or_create_label(board, label_name, color):
    """获取已有标签，如果不存在则创建"""
    existing_labels = board.get_labels()
    for label in existing_labels:
        if label.name == label_name:
            return label
    # 如果不存在，创建新标签
    return board.add_label(label_name, color)


# 创建"⚠️风险"标签（红色）
risk_label = get_or_create_label(target_board, "⚠️风险", "red")
# 创建"✅正常"标签（绿色）
normal_label = get_or_create_label(target_board, "✅正常", "green")

print(f"🏷️ 已准备好标签：{risk_label.name}、{normal_label.name}")


# ===== 第5部分：核心功能——创建任务（带截止日期） =====
def create_task(title, description="", list_name="待办", days_to_complete=5):
    """在指定列表创建一张新任务卡片，并设置截止日期"""
    if list_name not in list_map:
        print(f"❌ 列表'{list_name}'不存在")
        return None

    # 找到目标列表对象
    target_list = None
    for lst in lists:
        if lst.id == list_map[list_name]:
            target_list = lst
            break

    if target_list:
        # 计算截止日期
        due_date = datetime.now() + timedelta(days=days_to_complete)
        # 注意：add_card 的 due 参数需要字符串格式
        due_date_str = due_date.isoformat()

        # 创建卡片并设置截止日期
        card = target_list.add_card(
            title,
            description,
            due=due_date_str
        )
        # 添加"正常"标签（绿色）
        card.add_label(normal_label)
        print(f"✅ 创建任务成功：{title} → {list_name}（{days_to_complete}天后截止）")
        return card


# ===== 第6部分：核心功能——真实风险检查（基于截止日期） =====
def check_card_risk(card):
    """
    基于真实截止日期检查单张卡片的风险
    返回: ('状态', 剩余天数)
    状态: '严重风险'、'风险'、'正常'
    """
    if not card.due_date:
        print(f"⚠️ 任务 '{card.name}' 未设置截止日期，跳过检查")
        return '未设置', None

    # 计算剩余天数
    now = datetime.now()
    if card.due_date.tzinfo:
        now = datetime.now(card.due_date.tzinfo)

    days_left = (card.due_date - now).days

    if days_left < 0:
        print(f"🔴 严重预警：任务 '{card.name}' 已逾期 {abs(days_left)} 天！")
        return '严重风险', days_left
    elif days_left < 2:
        print(f"🟡 风险预警：任务 '{card.name}' 即将在 {days_left} 天内到期！")
        return '风险', days_left
    else:
        print(f"🟢 任务 '{card.name}' 状态正常，剩余 {days_left} 天。")
        return '正常', days_left


def update_card_labels(card, status):
    """根据风险状态更新卡片的标签"""
    current_labels = card.labels
    for label in current_labels:
        if label.name in ["⚠️风险", "✅正常"]:
            card.remove_label(label)

    if status in ['严重风险', '风险']:
        card.add_label(risk_label)
    else:
        card.add_label(normal_label)


# ===== 第7部分：核心功能——自动处理风险（移动卡片+建议） =====
def auto_handle_risk(card, status, days_left):
    """
    自动处理风险卡片：
    1. 如果严重风险（逾期），自动将卡片移回"待办"
    2. 输出资源调配建议
    """
    if status == '严重风险':
        card.change_list(todo_list.id)
        print(f"   🔄 自动操作：已将任务 '{card.name}' 移回【待办】列表，等待重新评估")

        print(f"   💡 建议：任务 '{card.name}' 已逾期，建议：")
        print(f"      - 立即与负责人沟通，确认阻塞原因")
        print(f"      - 评估是否需要增加人手或调整依赖关系")
        print(f"      - 考虑将部分子任务拆分并行处理")

    elif status == '风险':
        print(f"   💡 建议：任务 '{card.name}' 即将到期，建议：")
        print(f"      - 提醒负责人加快进度")
        print(f"      - 确认是否有外部依赖需要提前协调")


# ===== 第8部分：运行你的Agent =====
print("\n🤖 Agent启动！开始模拟项目管理...\n")

# 1. 清空看板上的旧卡片
print("🧹 正在清理旧卡片...")
all_cards = target_board.get_cards()
for card in all_cards:
    card.delete()
print(f"✅ 已清理 {len(all_cards)} 张旧卡片\n")

# 2. 创建一组任务
tasks_with_days = [
    ("无人机飞行控制算法开发", 3),
    ("传感器数据融合模块", 5),
    ("避障路径规划测试", 4),
    ("地面站监控界面", 7)
]

print("📋 开始创建任务...")
for task_name, days in tasks_with_days:
    create_task(task_name, "由AI Agent自动创建", "待办", days)

print("\n" + "=" * 50)
print("📊 当前项目状态：所有任务已录入待办列表")
print("=" * 50 + "\n")

# 3. 模拟项目推进：将部分任务移动到"进行中"
print("🚀 模拟项目推进：将部分任务移入【进行中】...")
cards = target_board.get_cards()
for i, card in enumerate(cards):
    if i < 2:
        card.change_list(doing_list.id)
        print(f"   📌 {card.name} → 进行中")
    else:
        print(f"   📌 {card.name} → 待办（等待中）")

print("\n" + "=" * 50 + "\n")

# 4. 模拟时间流逝：手动将"算法开发"任务的截止日期提前（模拟已延期）
print("⏰ 模拟：'无人机飞行控制算法开发'任务已延期3天...")
cards = target_board.get_cards()
for card in cards:
    if "算法开发" in card.name:
        # 关键修复：set_due 方法接受 datetime 对象，不需要转字符串
        past_date = datetime.now() - timedelta(days=3)
        card.set_due(past_date)  # 直接传入 datetime 对象
        print(f"   ⚠️ 已将 '{card.name}' 的截止日期调整为3天前（模拟延期）")
        break

print("\n" + "=" * 50 + "\n")

# 5. 运行风险监控模块
print("🔔 运行风险监控模块（基于真实截止日期）...\n")

high_risk_cards = []

cards = target_board.get_cards()
for card in cards:
    print(f"🔍 检查任务：{card.name}")
    status, days_left = check_card_risk(card)

    update_card_labels(card, status)

    if status in ['严重风险', '风险']:
        high_risk_cards.append((card, status, days_left))

print("\n" + "=" * 50 + "\n")

# 6. 自动处理风险卡片
if high_risk_cards:
    print("🤖 启动自动风险处理模块...\n")
    for card, status, days_left in high_risk_cards:
        auto_handle_risk(card, status, days_left)
        print("")
else:
    print("✅ 所有任务状态正常，无风险需要处理！")

print("\n" + "=" * 50)
print("📊 最终项目状态总结")
print("=" * 50)

# 7. 生成项目进度报告
cards = target_board.get_cards()
total = len(cards)
todo_count = 0
doing_count = 0
done_count = 0
risk_count = 0

for card in cards:
    card_list_name = None
    for lst in lists:
        if card.list_id == lst.id:
            card_list_name = lst.name
            break

    if card_list_name == "待办":
        todo_count += 1
    elif card_list_name == "进行中":
        doing_count += 1
    elif card_list_name == "已完成":
        done_count += 1

    for label in card.labels:
        if label.name == "⚠️风险":
            risk_count += 1
            break

print(f"📋 总任务数：{total}")
print(f"   【待办】：{todo_count} 个")
print(f"   【进行中】：{doing_count} 个")
print(f"   【已完成】：{done_count} 个")
print(f"⚠️ 风险任务：{risk_count} 个")

print("\n✅ Agent运行完毕！")
print("💡 提示：去Trello看板查看卡片上的标签变化和移动结果。")