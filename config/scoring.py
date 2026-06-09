# -*- coding: utf-8 -*-
"""Scoring and compliance configuration

2026-06-08 重构：区分"地点类型"和"实体类型"
  - 地点类型（工业园、停车场、物流园等）只是地址，不是决策主体
  - 实体类型（工厂、4S店、学校、医院等）是真正的决策主体
  - 百度地图来源 + 地点类型 + 无需求信号 → 强制低分
"""

# Import unified project scenarios
from config.project_scenarios import (
    PROJECT_SCENARIOS, SOURCE_SCORE as UNIFIED_SOURCE_SCORE,
    CORP_SCORE as UNIFIED_CORP_SCORE,
    STRONG_SIGNAL_KEYWORDS as UNIFIED_STRONG_KEYWORDS,
    MEDIUM_SIGNAL_KEYWORDS as UNIFIED_MEDIUM_KEYWORDS,
    match_scenario, get_level_by_keyword, get_category_by_keyword,
)

# ========================
# 地点类型 vs 实体类型
# ========================

# 地点类型：只是地址/场所，本身不是决策主体
# 这些POI的电话通常是物业管理处，不是真正的需求方
LOCATION_TYPES = [
    "工业园", "产业园", "物流园", "科技园", "开发区",
    "停车场", "地下停车场", "立体停车场",
    "商业广场", "步行街",
    "住宅小区", "小区",  # 小区的决策方是物业公司，不是小区本身
    "充电站", "充电桩", "换电站",  # 运营商不拥有场地，车棚决策权在物业/地产方
]

# 实体类型：是真正的决策主体，有明确的业务需求
ENTITY_TYPES = [
    "工厂", "4S店", "学校", "医院", "物业",
    "新能源", "充电桩", "充电站",
    "酒店", "商场", "购物中心",
    "政府机关", "体育馆", "会展中心",
]

# 地点类型匹配关键词（用于检测 demand_desc / customer_type 中的地点信号）
LOCATION_TYPE_KEYWORDS = [
    "工业园", "产业园", "物流园", "科技园", "开发区",
    "停车场", "停车库", "地下停车",
    "商业街", "步行街",
    "充电站", "充电桩", "换电站",  # 充电站是地点，运营商不是决策方
]


# Channel score: how valuable is this lead source
# Use unified source score config
SOURCE_SCORE = UNIFIED_SOURCE_SCORE

# Keyword intent score
KEYWORD_SCORE = {
    "报价": 25,
    "价格": 20,
    "多少钱": 20,
    "厂家": 15,
    "安装": 15,
    "定制": 12,
    "施工": 15,
    "改造": 20,
    "招标": 30,
    "测量": 10,
    "设计": 10,
    "": 0,
}

# Area proximity score
AREA_SCORE_RULES = {
    "本地": 20,
    "周边": 10,
    "外省": 0,
}
LOCAL_KEYWORDS = ["武汉"]
NEARBY_KEYWORDS = ["湖北", "黄石", "鄂州", "孝感", "黄冈",
    "咸宁", "荆州", "荆门", "宜昌", "襄阳", "十堰", "随州", "恩施",
    "仙桃", "潜江", "天门"]

# Customer type score
# 2026-06-08: 大幅降低地点类型的分数
# Use unified corp score config
CORP_SCORE = UNIFIED_CORP_SCORE

# Score -> Level mapping
LEVEL_THRESHOLDS = [
    (70, "S"),
    (50, "A"),
    (30, "B"),
    (0, "C"),
]

# Compliance
SMS_MAX_MONTH = 5000
SMS_SEND_WINDOWS = [
    ("09:00", "11:30"),
    ("14:30", "17:30"),
]
SMS_TEMPLATES_BY_LEVEL = {
    "S": None,  # S级由人工电话跟进，不发短信
    "A": "您好，{company}建筑一级资质，膜布+钢结构自主生产，1000+案例，24h出初稿。免费上门勘测，加微信sunknight002 回T退订",
    "B": "您好，{company}一级资质全链路厂家，膜布钢结构自主生产，免费上门测量出图。加微信sunknight002 回T退订",
    "C": "您好，{company}建筑一级资质膜结构厂家，1000+案例，免费测量。加微信sunknight002 回T退订",
}

# SS/A Level Keywords - High value project indicators
# 2026-06-08: 移除了地点性关键词（工业园配套、大型停车场）
SS_KEYWORDS = [
    "新建学校", "中小学改扩建", "高校新校区",
    "大型商业综合体", "购物中心新建", "冷链物流园区",
    "新建医院", "三甲医院",
    "政府采购", "公共设施",
    "招标", "公开招标", "竞争性磋商",
]
A_KEYWORDS = [
    "小区配套建设", "商业街改造", "园区室外配套工程",
    "老旧小区改造", "充电桩配套", "物流园区",
    "学校改造", "医院扩建", "公宫场馆",
]

# Auto-categorization rules: keyword -> (primary_category, secondary_category)
AUTO_CATEGORY_RULES = {
    # School -> Membrane + Glass
    "校区": ("膜结构", "玻璃遮阳棚"),
    "学校": ("膜结构", "玻璃遮阳棚"),
    "教学楼": ("膜结构", "玻璃遮阳棚"),
    "幼儿园": ("膜结构", "玻璃遮阳棚"),
    # Shopping mall -> Membrane + PV
    "商场": ("膜结构", "光伏车棚"),
    "购物中心": ("膜结构", "光伏车棚"),
    "商业广场": ("膜结构", "光伏车棚"),
    "综合体": ("膜结构", "光伏车棚"),
    # Industrial park -> 需要进一步判断，不自动分类
    # 2026-06-08: 移除工业园/物流园的自动分类，需要有需求信号才分类
    # Charging station -> PV
    "充电桩": ("光伏车棚", None),
    "充电站": ("光伏车棚", None),
    # Hospital -> Glass
    "医院": ("玻璃遮阳棚", None),
    "诊所": ("玻璃遮阳棚", None),
    # 4S shop -> Membrane
    "4S店": ("膜结构", None),
    "汽车店": ("膜结构", None),
    # Factory -> Membrane (confirmed entity type)
    "工厂": ("膜结构", None),
    "厂区": ("膜结构", None),
}

SLEEP_DAYS = 90



# ========================
# 数据质量评估规则
# ========================

# 强需求信号关键词（出现在备注/需求描述中 → 直接加 25-40 分）
# Use unified strong signal keywords
STRONG_SIGNAL_KEYWORDS = UNIFIED_STRONG_KEYWORDS
STRONG_SIGNAL_BONUS = 30

# 中等信号关键词（行业相关但无明确需求 → 加 10-15 分）
# 2026-06-08: 移除地点性关键词（停车场、工业园、物流）
# Use unified medium signal keywords
MEDIUM_SIGNAL_KEYWORDS = UNIFIED_MEDIUM_KEYWORDS
MEDIUM_SIGNAL_BONUS = 12

# 弱信号 / 噪音：纯地址无备注 → 百度地图数据默认降级
# Entity types: these are real decision-makers
ENTITY_TYPE_LIST = ["工厂", "4S店", "学校", "医院", "商业", "物业", "新能源", "酒店"]

COLD_SOURCE_LIST = ["baidu_map"]

# 质量等级阈值
QUALITY_HIGH_THRESHOLD = 50    # >=50 自动进入高质量队列
QUALITY_MEDIUM_THRESHOLD = 25  # >=25 中等质量
# <25 为低质量，不进入自动触达

# ========================
# 地点类型降级规则
# ========================
# 百度地图 + 地点类型 + 无需求信号 → 强制最高分数
LOCATION_TYPE_BAIDU_MAP_CAP = 12   # 最高12分，强制C级
# 非百度地图 + 地点类型 + 无需求信号 → 轻度降级
LOCATION_TYPE_NO_SIGNAL_CAP = 25   # 最高25分


def _detect_location_type(customer_type: str, demand_desc: str, source: str = "") -> bool:
    """检测是否为地点类型（非决策主体）

    只对百度地图 POI 数据做地点类型检测，避免误判经营范围中包含地点词的企业。

    Args:
        customer_type: 客户类型字段
        demand_desc: 需求描述字段
        source: 数据来源

    Returns:
        True if this lead is a location type (not a decision-making entity)
    """
    # 直接匹配 customer_type（所有来源都检查）
    if customer_type in ["停车场", "工业园/产业园", "物流园"]:
        return True

    # 只对百度地图 POI 检查 demand_desc 中的地点关键词
    # 因为百度地图的 demand_desc 是 "POI类型: xxx"，包含地点信息
    # 其他来源的 demand_desc 可能是经营范围，包含地点词不代表是地点类型
    if source == "baidu_map":
        text = f"{customer_type or ''} {demand_desc or ''}"
        for kw in LOCATION_TYPE_KEYWORDS:
            if kw in text:
                return True

    return False


def _has_any_demand_signal(demand_desc: str, notes: str = "", product_interest: str = "") -> bool:
    """检测是否有任何需求信号（强信号或中等信号）

    注意：product_interest 是采集器搜索关键词（如"光伏车棚"），不是客户表达的需求。
    只检查 demand_desc 和 notes 中的信号。
    """
    # 只用 demand_desc 和 notes 判断，product_interest 是我们搜的词，不是客户需求
    text = f"{demand_desc or ''} {notes or ''}"
    for kw in STRONG_SIGNAL_KEYWORDS:
        if kw in text:
            return True
    for kw in MEDIUM_SIGNAL_KEYWORDS:
        if kw in text:
            return True
    return False


def calc_total_score(lead_data):
    """Calculate total score for a lead.

    HARD RULES:
    1. No contact info (phone/email/wechat) = score capped at 20, forced to C level.
    2. Location type (工业园/停车场 etc.) without demand signal = heavily penalized.
    3. Baidu Map source + location type + no signal = forced C level, cap at 12.

    lead_data keys: source, product_interest, area, customer_type, demand_desc,
                    phone, email, wechat, notes
    Returns: (total, source_score, keyword_score, area_score, corp_score, level)
    """
    source = lead_data.get("source", "")
    product = lead_data.get("product_interest", "") or ""
    area = lead_data.get("area", "") or ""
    ctype = lead_data.get("customer_type", "") or ""
    desc = lead_data.get("demand_desc", "") or ""
    phone = lead_data.get("phone", "") or ""
    email = lead_data.get("email", "") or ""
    wechat = lead_data.get("wechat", "") or ""
    notes = lead_data.get("notes", "") or ""

    has_contact = bool(phone or email or wechat)

    # --- Detect if this is a location type ---
    is_location = _detect_location_type(ctype, desc, source)
    has_signal = _has_any_demand_signal(desc, notes, product)

    # 1. Source score
    ss = SOURCE_SCORE.get(source, 5)

    # 2. Keyword intent score (enhanced with SS/A keywords)
    ks = 0
    text = f"{product} {desc}".lower()
    for kw, pts in KEYWORD_SCORE.items():
        if kw and kw in text:
            ks = max(ks, pts)

    # SS/A keyword bonus - only if NOT a pure location type
    if not is_location or has_signal:
        for kw in SS_KEYWORDS:
            if kw in text:
                ks = max(ks, 35)  # SS level bonus
                break
        if ks < 30:
            for kw in A_KEYWORDS:
                if kw in text:
                    ks = max(ks, 25)  # A level bonus
                    break

    # 3. Area score
    as_ = AREA_SCORE_RULES["外省"]
    for kw in LOCAL_KEYWORDS:
        if kw in area:
            as_ = AREA_SCORE_RULES["本地"]
            break
    if as_ == 0:
        for kw in NEARBY_KEYWORDS:
            if kw in area:
                as_ = AREA_SCORE_RULES["周边"]
                break

    # 4. Corp type score
    # 地点类型使用低分
    if is_location and not has_signal:
        cs = 2  # 地点类型无信号，最低分
    else:
        cs = CORP_SCORE.get(ctype, 5)

    total = ss + ks + as_ + cs

    # === HARD RULE 1: No contact info = useless, cap at 20 ===
    if not has_contact:
        capped = min(total, 20)
        return capped, ss, ks, as_, cs, "C"

    # === HARD RULE 2: Location type without demand signal ===
    if is_location and not has_signal:
        if source in COLD_SOURCE_LIST:
            # 百度地图 + 地点类型 + 无信号 → 强制极低分
            total = min(total, LOCATION_TYPE_BAIDU_MAP_CAP)
        else:
            # 其他来源 + 地点类型 + 无信号 → 轻度限制
            total = min(total, LOCATION_TYPE_NO_SIGNAL_CAP)

    # === HARD RULE 3: Baidu Map cold data, no demand signal at all ===
    if source in COLD_SOURCE_LIST and not has_signal:
        total = min(total, 20)  # 百度地图+无任何信号，封顶20分

    total = min(100, max(0, total))

    # Determine level
    level = "C"
    for threshold, lvl in LEVEL_THRESHOLDS:
        if total >= threshold:
            level = lvl
            break

    # BOOST: Entity type + has phone + baidu_map => at least B
    if source in COLD_SOURCE_LIST and has_contact:
        if ctype in ENTITY_TYPE_LIST:
            if level == "C":
                level = "B"
                total = max(total, 30)
            if ss < 10:
                ss = 10
                total = min(100, total + 5)

    return total, ss, ks, as_, cs, level






