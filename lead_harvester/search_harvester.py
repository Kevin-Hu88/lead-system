# -*- coding: utf-8 -*-
"""
搜索引擎采集器 v2 - 精准捕捉有需求的客户

核心改进：
1. 高意图关键词：搜"车棚安装"的人比搜"车棚"的人需求更明确
2. 地域定向：只搜武汉+湖北相关结果
3. 竞争对手过滤：排除同行厂家
4. 需求场景映射：根据搜索词判断客户需求
5. 多引擎搜索：Bing + 百度
"""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from fake_useragent import UserAgent

from config import settings
from crm.models import db, Lead
from crm.scoring import score_lead
from lead_harvester.data_cleaner import DataCleaner

ua = UserAgent()

# ============================================================
# 高意图搜索词 → (关键词, 客户类型, 需求描述, 优先级)
# ============================================================
HIGH_INTENT_QUERIES = [
    # === 明确需求：找厂家/安装 ===
    ("武汉 车棚 安装 电话", "物业", "找车棚安装服务", "high"),
    ("武汉 停车棚 定制 厂家", "物业", "定制停车棚", "high"),
    ("武汉 膜结构车棚 报价", "物业", "询问车棚报价", "high"),
    ("湖北 车棚 工程 联系方式", "物业", "车棚工程咨询", "high"),
    ("武汉 遮阳棚 安装 多少钱", "物业", "遮阳棚安装咨询", "high"),
    
    # === 充电桩配套 ===
    ("武汉 充电桩 车棚 配套", "新能源", "充电桩配套车棚", "high"),
    ("湖北 充电站 车棚 建设", "新能源", "充电站车棚建设", "high"),
    ("武汉 电动车 充电棚 安装", "物业", "电动车充电棚", "high"),
    
    # === 老旧小区改造 ===
    ("武汉 老旧小区 车棚 改造", "物业", "老旧小区车棚改造", "high"),
    ("湖北 小区 车棚 翻新", "物业", "小区车棚翻新", "medium"),
    
    # === 学校/医院 ===
    ("武汉 学校 车棚 建设", "学校", "学校车棚建设", "high"),
    ("武汉 医院 车棚 安装", "医院", "医院车棚安装", "high"),
    ("湖北 幼儿园 车棚 定制", "学校", "幼儿园车棚", "high"),
    
    # === 4S店/商业 ===
    ("武汉 4S店 车棚 改造", "4S店", "4S店车棚改造", "high"),
    ("武汉 商场 车棚 安装", "商业", "商场车棚", "medium"),
    
    # === 工厂/物流 ===
    ("武汉 工厂 车棚 建设", "工厂", "工厂车棚建设", "medium"),
    ("湖北 物流园 车棚 安装", "工厂", "物流园车棚", "medium"),
]

# 竞争对手关键词（排除同行）
COMPETITOR_KEYWORDS = [
    "膜结构公司", "膜结构厂家", "车棚厂家", "遮阳棚厂家",
    "雨棚厂家", "张拉膜公司", "膜结构工程公司", "车棚公司",
    "专业车棚", "车棚制作", "车棚加工",
]

# Noise keywords to filter out irrelevant content
NOISE_KEYWORDS = [
    "天气预报", "天气查询", "新闻", "资讯", "头条",
    "公告公示", "公示", "政策", "法规", "条例",
    "招聘", "考试", "报名", "招生",
    "首页", "导航", "大全", "列表", "黄页",
]


class SearchHarvester:
    """搜索引擎采集器 v2 - 精准捕捉有需求的客户"""

    def __init__(self):
        self.session = requests.Session()

    def harvest(self) -> int:
        """执行采集"""
        total = 0
        for query, customer_type, demand_desc, priority in HIGH_INTENT_QUERIES:
            try:
                # Search Bing
                leads_bing = self._search_bing(query)
                # Search Baidu
                leads_baidu = self._search_baidu(query)
                
                # Combine and deduplicate
                all_leads = leads_bing + leads_baidu
                all_leads = self._deduplicate(all_leads)
                
                # Add metadata
                for lead in all_leads:
                    lead["customer_type"] = customer_type
                    lead["demand_desc"] = f"[{priority}] {demand_desc} | {lead.get('demand_desc', '')}"
                    lead["area"] = self._extract_area(lead.get("name", "") + " " + lead.get("demand_desc", ""))
                
                count = self._save_leads(all_leads)
                total += count
                if count > 0:
                    logger.info(f"[搜索] {query[:20]}: +{count}")
                
                time.sleep(random.uniform(
                    settings.REQUEST_DELAY_MIN,
                    settings.REQUEST_DELAY_MAX
                ))
            except Exception as e:
                logger.error(f"[搜索] failed [{query[:20]}]: {e}")
        
        return total

    def _search_bing(self, keyword: str) -> list:
        """Bing搜索"""
        results = []
        try:
            url = f"https://cn.bing.com/search?q={quote(keyword)}&first=1"
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                results = self._parse_search_results(resp.text, "bing")
        except Exception as e:
            logger.debug(f"Bing搜索失败: {e}")
        return results

    def _search_baidu(self, keyword: str) -> list:
        """百度搜索"""
        results = []
        try:
            url = f"https://www.baidu.com/s?wd={quote(keyword)}&rn=10"
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                results = self._parse_search_results(resp.text, "baidu")
        except Exception as e:
            logger.debug(f"百度搜索失败: {e}")
        return results

    def _parse_search_results(self, html: str, engine: str) -> list:
        """解析搜索结果"""
        results = []
        soup = BeautifulSoup(html, "lxml")
        
        # Selectors based on search engine
        if engine == "bing":
            items = soup.select("#b_results .b_algo")
        else:  # baidu
            items = soup.select(".result, .c-container")
        
        for item in items:
            try:
                # Extract title and description
                if engine == "bing":
                    title_el = item.select_one("h2 a")
                    desc_el = item.select_one(".b_caption p, .b_algoSlug")
                else:
                    title_el = item.select_one("h3 a, .t a")
                    desc_el = item.select_one(".c-abstract, .c-span-last")
                
                if not title_el:
                    continue
                
                title = title_el.get_text(strip=True)
                desc = desc_el.get_text(strip=True) if desc_el else ""
                href = title_el.get("href", "")
                full_text = f"{title} {desc}"
                
                # Skip competitors
                if self._is_competitor(full_text):
                    continue
                
                # Extract phone
                phone = self._extract_phone(full_text)
                
                # Extract company name
                name = self._extract_company_name(title)
                if not name or len(name) < 3:
                    continue
                
                # Only keep results with phone or high relevance
                if not phone and not any(kw in full_text for kw in ["车棚", "遮阳", "雨棚", "膜结构"]):
                    continue
                
                results.append({
                    "name": name[:100],
                    "phone": phone,
                    "source": "search",
                    "source_url": href,
                    "demand_desc": f"[{engine}] {title[:100]} | {desc[:100]}",
                    "product_interest": "车棚/遮阳棚",
                })
            except Exception:
                continue
        
        return results

    def _is_competitor(self, text: str) -> bool:
        """检测是否为竞争对手"""
        for kw in COMPETITOR_KEYWORDS:
            if kw in text:
                return True
        return False

    def _extract_phone(self, text: str) -> str:
        """从文本中提取电话"""
        # 手机号
        mobile = re.search(r"1[3-9]\d{9}", text)
        if mobile:
            return mobile.group()
        # 座机号
        landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
        if landline:
            return landline.group()
        return ""

    def _extract_company_name(self, title: str) -> str:
        """从标题中提取企业名称"""
        for sep in ["-", "_", "—", "|", "｜", " "]:
            if sep in title:
                title = title.split(sep)[0]
        for kw in ["电话", "联系方式", "地址", "官网", "首页", "怎么样", "好不好"]:
            if kw in title:
                title = title.split(kw)[0]
        return title.strip()

    def _extract_area(self, text: str) -> str:
        """从文本中提取区域"""
        areas = ["武汉", "黄石", "鄂州", "孝感", "黄冈", "咸宁",
                 "荆州", "荆门", "宜昌", "襄阳", "十堰", "随州", "恩施"]
        for area in areas:
            if area in text:
                return area
        return "湖北"

    def _deduplicate(self, leads: list) -> list:
        """去重"""
        seen = set()
        unique = []
        for lead in leads:
            key = lead.get("phone") or lead.get("name", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(lead)
        return unique

    def _save_leads(self, leads: list) -> int:
        """保存线索"""
        saved = 0
        for data in leads:
            try:
                # 电话去重
                if data.get("phone") and Lead.query.filter_by(phone=data["phone"]).first():
                    continue
                # 名称去重
                if data.get("name") and Lead.query.filter_by(name=data["name"]).first():
                    continue
                
                lead = Lead(**data)
                db.session.add(lead)
                db.session.flush()
                
                # Score
                score_lead(lead)
                saved += 1
            except Exception:
                pass
        
        if saved > 0:
            db.session.commit()
        
        return saved
