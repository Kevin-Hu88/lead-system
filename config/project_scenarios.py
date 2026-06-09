# -*- coding: utf-8 -*-
"""
统一项目场景配置 - 所有采集器共用

定义：
1. 项目场景分类（直接需求/间接需求/配套需求）
2. 需求等级（SS/S/A/B/C）
3. 产品匹配规则
4. 跟进话术模板
5. 评分加成规则
"""

# ============================================================
# 项目场景定义
# ============================================================
# 结构: keyword -> {category, level, scenario, products, pitch, score_bonus, urgency}

PROJECT_SCENARIOS = {
    # ============================================================
    # SS级 - 直接需求：项目本身就涉及车棚/遮阳棚/膜结构
    # ============================================================
    "车棚": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["膜结构车棚", "停车棚"],
        "pitch": "车棚工程直接需求，需确认规格和预算",
        "score_bonus": 25,
        "urgency": "high",
    },
    "遮阳棚": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["遮阳棚", "膜结构遮阳棚"],
        "pitch": "遮阳棚工程直接需求",
        "score_bonus": 25,
        "urgency": "high",
    },
    "膜结构": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["膜结构车棚", "张拉膜", "景观膜"],
        "pitch": "膜结构工程直接需求",
        "score_bonus": 25,
        "urgency": "high",
    },
    "雨棚": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["雨棚", "膜结构雨棚"],
        "pitch": "雨棚工程直接需求",
        "score_bonus": 25,
        "urgency": "high",
    },
    "停车棚": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["停车棚", "膜结构停车棚"],
        "pitch": "停车棚建设直接需求",
        "score_bonus": 25,
        "urgency": "high",
    },
    "非机动车棚": {
        "category": "膜结构",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["非机动车棚", "电动车棚"],
        "pitch": "非机动车棚建设直接需求",
        "score_bonus": 25,
        "urgency": "high",
    },
    "充电桩车棚": {
        "category": "光伏车棚",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["光伏车棚", "充电桩雨棚"],
        "pitch": "充电桩配套车棚，光伏车棚还能发电",
        "score_bonus": 25,
        "urgency": "high",
    },
    "光伏车棚": {
        "category": "光伏车棚",
        "level": "SS",
        "scenario": "直接需求",
        "products": ["光伏车棚", "BIPV车棚"],
        "pitch": "光伏车棚直接需求，政策补贴支持",
        "score_bonus": 25,
        "urgency": "high",
    },

    # ============================================================
    # S级 - 间接需求：项目类型必须配套车棚
    # ============================================================
    "学校": {
        "category": "膜结构",
        "level": "S",
        "scenario": "间接需求",
        "products": ["膜结构车棚", "玻璃遮阳棚", "操场遮阳棚"],
        "pitch": "学校车棚安全要求高，资质是硬门槛，找总务处或基建处",
        "score_bonus": 20,
        "urgency": "high",
    },
    "教学楼": {
        "category": "膜结构",
        "level": "S",
        "scenario": "间接需求",
        "products": ["膜结构车棚", "玻璃遮阳棚"],
        "pitch": "教学楼配套车棚/雨棚",
        "score_bonus": 20,
        "urgency": "high",
    },
    "幼儿园": {
        "category": "膜结构",
        "level": "S",
        "scenario": "间接需求",
        "products": ["膜结构车棚", "玻璃遮阳棚"],
        "pitch": "幼儿园配套车棚，安全第一",
        "score_bonus": 20,
        "urgency": "high",
    },
    "高校": {
        "category": "膜结构",
        "level": "S",
        "scenario": "间接需求",
        "products": ["膜结构车棚", "玻璃遮阳棚", "景观膜"],
        "pitch": "高校新校区配套，面积大利润高",
        "score_bonus": 20,
        "urgency": "high",
    },
    "大学": {
        "category": "膜结构",
        "level": "S",
        "scenario": "间接需求",
        "products": ["膜结构车棚", "玻璃遮阳棚", "景观膜"],
        "pitch": "大学配套车棚，找基建处",
        "score_bonus": 20,
        "urgency": "high",
    },
    "医院": {
        "category": "玻璃遮阳棚",
        "level": "S",
        "scenario": "间接需求",
        "products": ["玻璃遮阳棚", "膜结构车棚", "无障碍车棚"],
        "pitch": "医院车棚要求高，无障碍设计是加分项，找后勤部",
        "score_bonus": 20,
        "urgency": "high",
    },
    "卫生院": {
        "category": "玻璃遮阳棚",
        "level": "S",
        "scenario": "间接需求",
        "products": ["玻璃遮阳棚", "膜结构车棚"],
        "pitch": "卫生院配套车棚",
        "score_bonus": 18,
        "urgency": "medium",
    },

    # ============================================================
    # A级 - 配套需求：项目需要车棚配套
    # ============================================================
    "小区": {
        "category": "玻璃遮阳棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚", "非机动车棚"],
        "pitch": "小区交房配套，业主停车刚需，找物业公司",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "楼盘": {
        "category": "玻璃遮阳棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "楼盘配套车棚，找开发商或物业",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "住宅": {
        "category": "玻璃遮阳棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "住宅项目配套车棚",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "居住": {
        "category": "玻璃遮阳棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "居住项目配套车棚",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "安置房": {
        "category": "玻璃遮阳棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "安置房配套车棚，政府项目有预算",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "老旧小区": {
        "category": "膜结构",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "充电桩雨棚", "电动车充电棚"],
        "pitch": "老旧小区改造是政策风口，充电桩配套是硬性要求",
        "score_bonus": 18,
        "urgency": "high",
    },
    "商场": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "景观遮阳棚", "膜结构车棚"],
        "pitch": "商场注重形象，景观膜结构是卖点，找商管公司",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "购物中心": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "景观遮阳棚", "膜结构车棚"],
        "pitch": "购物中心配套车棚，面积大利润高",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "综合体": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "景观遮阳棚", "膜结构车棚"],
        "pitch": "商业综合体配套车棚",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "酒店": {
        "category": "膜结构",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "景观遮阳棚"],
        "pitch": "酒店配套车棚，提升形象",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "充电站": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "充电桩雨棚", "遮阳棚"],
        "pitch": "充电站配套车棚是标配，光伏车棚还能发电",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "充电桩": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "充电桩雨棚"],
        "pitch": "充电桩配套车棚",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "光储充": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "BIPV车棚"],
        "pitch": "光储充一体化项目，光伏车棚是核心配套",
        "score_bonus": 18,
        "urgency": "medium",
    },
    "光伏": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["光伏车棚", "BIPV车棚"],
        "pitch": "光伏项目配套车棚",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "产业园": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "光伏车棚", "厂区遮阳棚"],
        "pitch": "产业园招商配套，厂区车棚是基础设施，找管委会",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "工业园": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "光伏车棚", "厂区遮阳棚"],
        "pitch": "工业园配套车棚，找园区管委会",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "物流园": {
        "category": "光伏车棚",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "大型货车棚", "仓库遮阳棚"],
        "pitch": "物流园货车停车棚需求大，面积大利润高",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "厂房": {
        "category": "膜结构",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "厂区遮阳棚"],
        "pitch": "厂区车棚配套",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "停车场": {
        "category": "膜结构",
        "level": "A",
        "scenario": "配套需求",
        "products": ["膜结构车棚", "遮阳棚"],
        "pitch": "停车场车棚配套",
        "score_bonus": 10,
        "urgency": "low",
    },

    # ============================================================
    # B级 - 潜在需求：可能需要车棚
    # ============================================================
    "商业": {
        "category": "光伏车棚",
        "level": "B",
        "scenario": "潜在需求",
        "products": ["光伏车棚", "景观遮阳棚"],
        "pitch": "商业项目可能需要车棚配套",
        "score_bonus": 8,
        "urgency": "low",
    },
    "政府": {
        "category": "膜结构",
        "level": "B",
        "scenario": "潜在需求",
        "products": ["膜结构车棚", "玻璃遮阳棚"],
        "pitch": "政府公共设施可能需要车棚",
        "score_bonus": 8,
        "urgency": "low",
    },
    "办公": {
        "category": "玻璃遮阳棚",
        "level": "B",
        "scenario": "潜在需求",
        "products": ["玻璃遮阳棚", "膜结构车棚"],
        "pitch": "办公设施可能需要车棚配套",
        "score_bonus": 5,
        "urgency": "low",
    },
}


# ============================================================
# 来源评分配置
# ============================================================
SOURCE_SCORE = {
    # 高价值来源
    "招标平台": 35,
    "gov_data": 30,        # 政府公开数据
    "tianyancha": 25,      # 天眼查
    "qichacha": 25,        # 企查查
    "工商数据": 20,
    "manual": 10,

    # 中价值来源
    "商品房项目": 20,
    "在建工程": 18,
    "enterprise_search": 15,
    "hbcic": 18,           # 建筑工程平台
    "industry_*": 12,      # 行业垂直平台

    # 低价值来源
    "baidu_map": 5,
    "search": 8,
    "classified": 7,       # 分类信息
    "forum": 9,            # 论坛问答
    "import": 5,
}


# ============================================================
# 客户类型评分配置
# ============================================================
CORP_SCORE = {
    # === 高价值实体类型（决策主体）===
    "招标项目": 20,
    "4S店": 18,
    "新能源": 17,
    "工厂": 16,
    "物业": 14,
    "商业": 12,
    "学校": 10,
    "医院": 10,
    "酒店": 10,

    # === 中价值类型 ===
    "建设项目": 12,
    "分类信息": 8,
    "其他": 5,

    # === 低价值地点类型（非决策主体）===
    "停车场": 3,
    "工业园/产业园": 2,
    "物流园": 3,
    "小区": 6,
}


# ============================================================
# 需求信号关键词
# ============================================================
STRONG_SIGNAL_KEYWORDS = [
    # 直接需求
    "车棚", "遮阳棚", "膜结构", "雨棚", "停车棚",
    "非机动车棚", "充电桩车棚", "光伏车棚",
    # 采购信号
    "招标", "采购", "比选", "磋商", "询价", "竞标",
    "报价", "测量", "安装", "施工",
    # 项目信号
    "新建", "在建", "改造", "扩建", "翻新",
    "交付", "交房", "竣工", "开工",
    # 需求信号
    "需要", "求购", "计划", "预算",
]

MEDIUM_SIGNAL_KEYWORDS = [
    # 行业相关
    "车棚", "遮阳棚", "膜结构", "光伏",
    "仓库", "厂房", "钢结构",
    # 充电设施
    "充电桩", "充电站", "新能源",
]


# ============================================================
# 辅助函数
# ============================================================
def get_scenario_by_keyword(keyword: str) -> dict:
    """根据关键词获取项目场景"""
    return PROJECT_SCENARIOS.get(keyword)

def get_level_by_keyword(keyword: str) -> str:
    """根据关键词获取需求等级"""
    scenario = PROJECT_SCENARIOS.get(keyword)
    return scenario["level"] if scenario else "C"

def get_category_by_keyword(keyword: str) -> str:
    """根据关键词获取产品分类"""
    scenario = PROJECT_SCENARIOS.get(keyword)
    return scenario["category"] if scenario else "膜结构"

def get_score_bonus_by_keyword(keyword: str) -> int:
    """根据关键词获取评分加成"""
    scenario = PROJECT_SCENARIOS.get(keyword)
    return scenario["score_bonus"] if scenario else 0

def match_scenario(text: str) -> dict:
    """从文本中匹配项目场景，返回最佳匹配"""
    if not text:
        return None
    text_lower = text.lower()
    best_match = None
    best_bonus = 0

    for keyword, scenario in PROJECT_SCENARIOS.items():
        if keyword in text_lower:
            if scenario["score_bonus"] > best_bonus:
                best_match = scenario
                best_bonus = scenario["score_bonus"]

    return best_match
