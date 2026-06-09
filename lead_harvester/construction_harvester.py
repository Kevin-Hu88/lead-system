# -*- coding: utf-8 -*-
"""
在建工程采集器 v2 - 深度挖掘需求场景

核心改进：
1. 需求场景映射：每个项目类型 → 具体产品需求 + 跟进话术
2. 项目阶段识别：规划/招标/在建 → 不同优先级
3. 二次搜索补全电话：搜到项目名后，再搜"项目名+联系方式"
4. 扩展搜索词：覆盖更多真实场景
"""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from fake_useragent import UserAgent
from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner
from config.project_scenarios import PROJECT_SCENARIOS, match_scenario

ua = UserAgent()

# ============================================================
# 噪音过滤：排除非项目类内容
# ============================================================
NOISE_KEYWORDS = [
    # 天气/新闻/资讯
    "天气预报", "天气查询", "新闻", "资讯", "头条",
    # 政府公告/公示/政策
    "公告公示", "公示", "政策", "法规", "条例", "办法",
    "审批", "许可", "备案公示", "招标公告公示",
    # 教育/招聘/考试
    "招聘", "考试", "报名", "招生", "录取",
    # 无关内容
    "天气", "温度", "降水", "风力",
    # 网站导航/列表页
    "首页", "导航", "大全", "列表", "黄页",
]

# 项目相关正向关键词（必须至少匹配一个才认为是有效项目）
PROJECT_POSITIVE_KEYWORDS = [
    "新建", "在建", "施工", "建设", "改造", "扩建",
    "交付", "交房", "竣工", "开工", "开盘",
    "招标", "采购", "比选", "磋商",
    "项目", "工程", "地块", "小区", "园区",
    "车棚", "遮阳棚", "雨棚", "膜结构", "光伏",
]

# ============================================================
# 需求场景映射：项目类型 → (产品需求, 跟进话术, 优先级加成)
# ============================================================
DEMAND_SCENARIOS = {
    "新建小区": {
        "products": ["膜结构车棚", "充电桩雨棚", "非机动车棚"],
        "pitch": "新建小区交房配套，业主停车刚需，提前介入可做整体方案",
        "score_bonus": 15,
        "urgency": "high",
    },
    "旧小区改造": {
        "products": ["膜结构车棚", "充电桩雨棚", "电动车充电棚"],
        "pitch": "老旧小区改造是政策风口，充电桩配套是硬性要求，物业有预算",
        "score_bonus": 20,
        "urgency": "high",
    },
    "充电站新建": {
        "products": ["光伏车棚", "充电桩雨棚", "遮阳棚"],
        "pitch": "充电站配套车棚是标配，光伏车棚还能发电，运营商有预算",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "工业园新建": {
        "products": ["膜结构车棚", "光伏车棚", "厂区遮阳棚"],
        "pitch": "产业园招商配套，厂区车棚是基础设施，找开发商或管委会",
        "score_bonus": 10,
        "urgency": "medium",
    },
    "学校新建": {
        "products": ["膜结构车棚", "玻璃遮阳棚", "操场遮阳棚"],
        "pitch": "学校车棚安全要求高，资质是硬门槛，找总务处或基建处",
        "score_bonus": 18,
        "urgency": "high",
    },
    "医院新建": {
        "products": ["玻璃遮阳棚", "膜结构车棚", "无障碍车棚"],
        "pitch": "医院车棚要求高，无障碍设计是加分项，找后勤部",
        "score_bonus": 15,
        "urgency": "medium",
    },
    "商业综合体": {
        "products": ["膜结构车棚", "光伏车棚", "景观遮阳棚"],
        "pitch": "商业综合体注重形象，景观膜结构是卖点，找商管公司",
        "score_bonus": 12,
        "urgency": "medium",
    },
    "物流园新建": {
        "products": ["膜结构车棚", "大型货车棚", "仓库遮阳棚"],
        "pitch": "物流园货车停车棚需求大，面积大利润高，找园区管委会",
        "score_bonus": 10,
        "urgency": "medium",
    },
    "光伏车棚": {
        "products": ["光伏车棚", "BIPV车棚"],
        "pitch": "光伏+车棚一体化，政策补贴支持，找新能源公司或开发商",
        "score_bonus": 15,
        "urgency": "high",
    },
    "钢结构工程": {
        "products": ["膜结构车棚", "钢结构车棚", "张拉膜"],
        "pitch": "钢结构工程是上游，可搭车做车棚配套，找总包方",
        "score_bonus": 8,
        "urgency": "low",
    },
}

# ============================================================
# 项目阶段关键词 → (阶段标签, 优先级)
# ============================================================
STAGE_KEYWORDS = {
    # 招标阶段 - 最有价值，可参与
    "招标": ("招标中", "S"),
    "公开招标": ("招标中", "S"),
    "竞争性磋商": ("招标中", "S"),
    "询价": ("招标中", "S"),
    # 施工阶段 - 已定标，找总包方
    "施工": ("施工中", "A"),
    "在建": ("施工中", "A"),
    "开工": ("施工中", "A"),
    "建设中": ("施工中", "A"),
    # 规划阶段 - 提前布局
    "规划": ("规划中", "B"),
    "立项": ("规划中", "B"),
    "备案": ("规划中", "B"),
    "签约": ("规划中", "B"),
    # 交付阶段 - 配套需求
    "交付": ("待交付", "A"),
    "交房": ("待交付", "A"),
    "竣工": ("待交付", "A"),
}

# ============================================================
# 扩展搜索词：覆盖更多真实场景
# ============================================================
CONSTRUCTION_QUERIES = [
    # === 住宅类 ===
    ("武汉 新建小区 交付 2026", "新建小区"),
    ("武汉 新盘 开盘 车位", "新建小区"),
    ("武汉 棚户区改造 安置房", "新建小区"),
    ("湖北 旧改 充电桩 配套 车棚", "旧小区改造"),
    ("武汉 老旧小区改造 停车", "旧小区改造"),
    # === 充电设施 ===
    ("武汉 充电站 新建 建设", "充电站新建"),
    ("湖北 充电桩 配套设施 车棚", "充电站新建"),
    ("武汉 新能源 充电设施 规划", "充电站新建"),
    # === 工业/物流 ===
    ("武汉 产业园 新建 招商", "工业园新建"),
    ("湖北 工业园区 二期 建设", "工业园新建"),
    ("武汉 物流园 新建 项目", "物流园新建"),
    # === 公共设施 ===
    ("武汉 学校 新建 工程 2026", "学校新建"),
    ("武汉 中小学 改扩建 项目", "学校新建"),
    ("湖北 医院 新院区 建设", "医院新建"),
    # === 商业 ===
    ("武汉 商业综合体 新建 项目", "商业综合体"),
    ("武汉 购物中心 开业 配套", "商业综合体"),
    # === 上游工程 ===
    ("湖北 光伏车棚 项目 招标", "光伏车棚"),
    ("湖北 钢结构 工程 招标", "钢结构工程"),
    ("湖北 膜结构 工程 项目", "钢结构工程"),
]


class ConstructionHarvester:
    """在建工程采集器 v2 - 深度挖掘需求场景"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': ua.random,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def harvest(self) -> int:
        total = 0
        for query, category in CONSTRUCTION_QUERIES:
            try:
                leads = self._search(query, category)
                count = self._save_leads(leads)
                total += count
                if count > 0:
                    logger.info(f"[Construction] {category}/{query[:20]}: +{count}")
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"[Construction] failed [{query[:20]}]: {e}")
        return total

    def _search(self, query: str, category: str) -> list:
        results = []
        try:
            url = f"https://cn.bing.com/search?q={quote(query)}&count=20"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select(".b_algo"):
                try:
                    title_el = item.select_one("h2 a")
                    desc_el = item.select_one(".b_caption p, .b_algoSlug")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    href = title_el.get("href", "")
                    full_text = f"{title} {desc}"

                    # Extract phone
                    phone = self._extract_phone(full_text)

                    # Extract project name
                    name = title.split("-")[0].split("_")[0].strip()
                    if len(name) > 60:
                        name = name[:60]
                    if not name:
                        continue

                    # DataCleaner will handle noise/competitor/dedup checks

                    # Detect project stage
                    stage, stage_level = self._detect_stage(full_text)

                    # Get demand scenario
                    scenario = DEMAND_SCENARIOS.get(category, {
                        "products": ["车棚", "遮阳棚"],
                        "pitch": "在建项目，有车棚/遮阳棚配套需求",
                        "score_bonus": 5,
                        "urgency": "medium",
                    })

                    # Build demand description with scenario
                    products_str = "、".join(scenario["products"])
                    demand_desc = (
                        f"[{category}] [{stage}] "
                        f"需求产品: {products_str} | "
                        f"跟进策略: {scenario['pitch']} | "
                        f"{title[:80]}"
                    )

                    # Map category to customer type
                    ctype = self._map_customer_type(category)

                    # Calculate score bonus
                    score_bonus = scenario["score_bonus"]
                    if stage == "招标中":
                        score_bonus += 20  # 招标阶段额外加分
                    elif stage == "施工中":
                        score_bonus += 10

                    results.append({
                        "name": name,
                        "phone": phone,
                        "source": "在建工程",
                        "source_url": href,
                        "area": self._detect_area(full_text),
                        "demand_desc": demand_desc,
                        "product_interest": products_str,
                        "customer_type": ctype,
                        "notes": (
                            f"项目阶段: {stage}\n"
                            f"推荐产品: {products_str}\n"
                            f"跟进话术: {scenario['pitch']}\n"
                            f"优先级加成: +{score_bonus}分"
                        ),
                    })

                    # If no phone found, try secondary search
                    if not phone:
                        phone2 = self._search_phone(name)
                        if phone2:
                            results[-1]["phone"] = phone2

                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Construction search failed: {e}")
        return results

    def _extract_phone(self, text: str) -> str:
        """Extract phone from text"""
        mobile = re.search(r"1[3-9]\d{9}", text)
        if mobile:
            return mobile.group()
        landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
        if landline:
            return landline.group()
        return ""

    def _search_phone(self, project_name: str) -> str:
        """Secondary search: project name + phone/contact"""
        try:
            query = f"{project_name} 电话 联系方式"
            url = f"https://cn.bing.com/search?q={quote(query)}&count=5"
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return ""
            text = resp.text
            mobile = re.search(r"1[3-9]\d{9}", text)
            if mobile:
                return mobile.group()
            landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
            if landline:
                return landline.group()
        except:
            pass
        return ""

    def _detect_stage(self, text: str) -> tuple:
        """Detect project stage from text"""
        for kw, (stage, level) in STAGE_KEYWORDS.items():
            if kw in text:
                return stage, level
        return "在建", "A"

    def _map_customer_type(self, category: str) -> str:
        """Map category to customer type"""
        mapping = {
            "新建小区": "物业",
            "旧小区改造": "物业",
            "充电站新建": "新能源",
            "工业园新建": "工厂",
            "物流园新建": "工厂",
            "学校新建": "学校",
            "医院新建": "医院",
            "商业综合体": "商业",
            "光伏车棚": "新能源",
            "钢结构工程": "工厂",
        }
        return mapping.get(category, "建设项目")

    def _detect_area(self, text: str) -> str:
        """Detect area from text"""
        areas = ["武汉", "黄石", "鄂州", "孝感", "黄冈", "咸宁",
                 "荆州", "荆门", "宜昌", "襄阳", "十堰", "随州", "恩施"]
        for area in areas:
            if area in text:
                return area
        return "湖北"

    def _is_noise(self, name: str, text: str) -> bool:
        """Check if this is noise content (not a real project)"""
        combined = f"{name} {text}".lower()
        for kw in NOISE_KEYWORDS:
            if kw in combined:
                return True
        return False

    def _is_competitor(self, name: str, text: str) -> bool:
        """Check if this is a competitor"""
        kws = ["膜结构公司", "膜结构厂家", "车棚厂家", "遮阳棚厂家", "雨棚厂家"]
        for kw in kws:
            if kw in name or kw in text[:50]:
                return True
        return False

    def _save_leads(self, leads: list) -> int:
        """Save leads using DataCleaner"""
        saved = 0
        for data in leads:
            cleaned = DataCleaner.clean_lead_data(data)
            if not cleaned:
                continue
            try:
                lead = Lead(**cleaned)
                db.session.add(lead)
                db.session.flush()

                # Apply score bonus from demand scenario
                from crm.scoring import score_lead
                score_lead(lead)

                # Add scenario bonus to total score
                notes = cleaned.get("notes", "")
                bonus_match = re.search(r"优先级加成: \+(\d+)分", notes)
                if bonus_match:
                    bonus = int(bonus_match.group(1))
                    lead.total_score = min(100, lead.total_score + bonus)
                    lead.score = lead.total_score
                    if lead.total_score >= 70:
                        lead.lead_level = "S"
                    elif lead.total_score >= 50:
                        lead.lead_level = "A"
                    elif lead.total_score >= 30:
                        lead.lead_level = "B"
                    else:
                        lead.lead_level = "C"

                saved += 1
            except Exception as e:
                logger.debug(f"Save lead failed: {e}")
        if saved > 0:
            db.session.commit()
        return saved
