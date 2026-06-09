# -*- coding: utf-8 -*-
"""
Project Harvester - Construction project leads from government platforms
Sources:
1. jzsc.mohurd.gov.cn (四库一平台 - Housing & Construction Ministry)
2. Local housing bureau announcements
3. National investment project approval platform
"""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from crm.models import db, Lead
from crm.scoring import score_lead

# SS Level Keywords - Highest value projects
SS_PROJECT_KEYWORDS = [
    "新建学校", "中小学改扩建", "高校新校区",
    "大型商业综合体", "购物中心新建", "冷链物流园区",
    "新建医院", "三甲医院", "政府采购",
]

# A Level Keywords - Medium value projects
A_PROJECT_KEYWORDS = [
    "小区配套建设", "商业街改造", "园区室外配套",
    "老旧小区改造", "充电桩配套", "物流园区",
]

# Auto-categorization rules
CATEGORY_RULES = {
    "学校": "膜结构",
    "教学楼": "膜结构",
    "幼儿园": "膜结构",
    "商场": "光伏车棚",
    "购物中心": "光伏车棚",
    "产业园": "光伏车棚",
    "充电桩": "光伏车棚",
    "医院": "玻璃遮阳棚",
}


class ProjectHarvester:
    """Harvester for construction project leads from government platforms"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.seen_urls = set()
    
    def harvest(self) -> int:
        """Run all project harvesters"""
        total = 0
        
        # Source 1: CCGP project announcements (reuse existing)
        from lead_harvester.bid_harvester import BidHarvester
        bid_harvester = BidHarvester()
        for kw in SS_PROJECT_KEYWORDS[:5]:
            try:
                leads = bid_harvester._search_ccgp(kw, pages=2)
                count = self._save_project_leads(leads, "SS")
                total += count
                if count > 0:
                    logger.info(f"[Project-CCGP-SS] {kw}: +{count}")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"[Project-CCGP-SS] failed [{kw}]: {e}")
        
        for kw in A_PROJECT_KEYWORDS[:5]:
            try:
                leads = bid_harvester._search_ccgp(kw, pages=2)
                count = self._save_project_leads(leads, "A")
                total += count
                if count > 0:
                    logger.info(f"[Project-CCGP-A] {kw}: +{count}")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"[Project-CCGP-A] failed [{kw}]: {e}")
        
        # Source 2: Baidu search for government project announcements
        for kw in SS_PROJECT_KEYWORDS[:3]:
            try:
                leads = self._search_gov_projects(kw)
                count = self._save_project_leads(leads, "SS")
                total += count
                if count > 0:
                    logger.info(f"[Project-Baidu-SS] {kw}: +{count}")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.debug(f"[Project-Baidu-SS] failed [{kw}]: {e}")
        
        logger.info(f"[ProjectHarvest] Total: +{total} project leads")
        return total
    
    def _search_gov_projects(self, keyword: str) -> list:
        """Search Baidu for government project announcements"""
        results = []
        try:
            query = f"{keyword} 公示 site:gov.cn 2026"
            url = f"https://www.baidu.com/s?wd={quote(query)}&rn=10"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return results
            
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select(".result, .c-container"):
                try:
                    title_el = item.select_one("h3 a, .t a")
                    if not title_el:
                        continue
                    
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    
                    # Must be government project
                    if not any(kw in title for kw in ["公示", "备案", "立项", "施工许可"]):
                        continue
                    
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    
                    name = title.split("-")[0].split("_")[0].strip()[:60]
                    if not name:
                        continue
                    
                    # Determine area
                    area = ""
                    for region in ["武汉", "湖北", "黄石", "鄂州", "孝感", "黄冈", "咸宁", "荆州", "荆门", "宜昌", "襄阳", "十堰", "随州", "恩施"]:
                        if region in title:
                            area = region
                            break
                    
                    # Auto-categorize
                    category = "膜结构"
                    for kw, cat in CATEGORY_RULES.items():
                        if kw in title:
                            category = cat
                            break
                    
                    results.append({
                        "name": name,
                        "source": "在建工程",
                        "source_url": href,
                        "demand_desc": f"[SS级项目] {title[:200]}",
                        "product_interest": keyword,
                        "customer_type": "建设项目",
                        "area": area,
                        "business_category": category,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Gov project search failed: {e}")
        return results
    
    def _save_project_leads(self, leads: list, level: str = "S") -> int:
        """Save project leads with appropriate scoring"""
        saved = 0
        for data in leads:
            try:
                # Check for duplicates
                if data.get("phone") and Lead.query.filter_by(phone=data["phone"]).first():
                    continue
                if Lead.query.filter_by(name=data["name"]).first():
                    continue
                
                lead = Lead(**data)
                db.session.add(lead)
                db.session.flush()  # Get lead ID
                
                # Score with project bonus
                score_lead(lead)
                
                # Apply level-specific bonus
                if level == "SS":
                    lead.total_score = min(100, lead.total_score + 15)
                    lead.source_score = min(50, lead.source_score + 10)
                elif level == "S":
                    lead.total_score = min(100, lead.total_score + 8)
                
                # Force level if high enough
                if lead.total_score >= 70:
                    lead.lead_level = "S"
                elif lead.total_score >= 50:
                    lead.lead_level = "A"
                
                saved += 1
            except Exception as e:
                logger.debug(f"Save project lead failed: {e}")
        
        if saved > 0:
            db.session.commit()
        return saved
