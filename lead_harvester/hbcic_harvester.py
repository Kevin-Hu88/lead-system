# -*- coding: utf-8 -*-
"""
HBCIC Harvester - 湖北省建筑市场监督与诚信一体化平台
API: http://hbjz.hbcic.net.cn/ythweb/szjs_ythpt/frame/workportal/jsgcprojectinfolistaction_yth.action
Scans construction project listings for Wuhan/Hubei projects relevant to carport/shelter business.
"""
import re, time, random, requests
from urllib.parse import urlencode
from loguru import logger
from crm.models import db, Lead
from crm.scoring import score_lead
from config.project_scenarios import PROJECT_SCENARIOS, match_scenario

API_URL = "http://hbjz.hbcic.net.cn/ythweb/szjs_ythpt/frame/workportal/jsgcprojectinfolistaction_yth.action?cmd=getProjectInfoList"
REFERER = "http://hbjz.hbcic.net.cn/ythweb/szjs_ythpt/frame/workportal/projectlink.html?prjtypenum=01&isbl=0"
MAX_PAGE_SIZE = 20

# Keywords that indicate a project is relevant to our business
RELEVANT_KEYWORDS = {
    # High value - school/education
    "\u5b66\u6821": ("\u819c\u7ed3\u6784", "SS"),     # 学校 -> 膜结构, SS
    "\u5e7c\u513f\u56ed": ("\u819c\u7ed3\u6784", "SS"), # 幼儿园
    "\u6559\u5b66\u697c": ("\u819c\u7ed3\u6784", "SS"), # 教学楼
    "\u9ad8\u6821": ("\u819c\u7ed3\u6784", "SS"),       # 高校
    "\u5927\u5b66": ("\u819c\u7ed3\u6784", "SS"),       # 大学
    # High value - medical
    "\u533b\u9662": ("\u73bb\u7483\u906e\u9633\u68da", "S"),  # 医院
    "\u536b\u751f\u9662": ("\u73bb\u7483\u906e\u9633\u68da", "S"), # 卫生院
    # High value - commercial
    "\u5546\u4e1a": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 商业
    "\u8d2d\u7269\u4e2d\u5fc3": ("\u5149\u4f0f\u8f66\u68da", "SS"), # 购物中心
    "\u7efc\u5408\u4f53": ("\u5149\u4f0f\u8f66\u68da", "SS"),  # 综合体
    "\u5e02\u573a": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 市场
    # Medium value - residential
    "\u5c0f\u533a": ("\u73bb\u7483\u906e\u9633\u68da", "A"),  # 小区
    "\u4f4f\u5b85": ("\u73bb\u7483\u906e\u9633\u68da", "A"),  # 住宅
    "\u5c45\u4f4f": ("\u73bb\u7483\u906e\u9633\u68da", "A"),  # 居住
    "\u516c\u5bd3": ("\u73bb\u7483\u906e\u9633\u68da", "A"),  # 公寓
    # Medium value - industrial/logistics
    "\u4ea7\u4e1a\u56ed": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 产业园
    "\u5de5\u4e1a\u56ed": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 工业园
    "\u7269\u6d41": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 物流
    # Infrastructure
    "\u505c\u8f66\u573a": ("\u819c\u7ed3\u6784", "A"),  # 停车场
    "\u5145\u7535": ("\u5149\u4f0f\u8f66\u68da", "A"),  # 充电
    # Government/public
    "\u653f\u5e9c": ("\u819c\u7ed3\u6784", "A"),  # 政府
    "\u529e\u516c": ("\u73bb\u7483\u906e\u9633\u68da", "B"),  # 办公
}

# Wuhan area codes in project numbers
WUHAN_CODES = ["4201"]

# Broader Hubei city codes
HUBEI_CODES = [
    "4201", # \u6b66\u6c49
    "4202", # \u9ec4\u77f3
    "4203", # "\u5341\u5830"
    "4205", # "\u5b9c\u660c"
    "4206", # "\u8944\u9633"
    "4207", # "\u9102\u5dde"
    "4208", # "\u8346\u95e8"
    "4209", # "\u5b6d\u611f"
    "4210", # "\u8346\u5dde"
    "4211", # "\u9ec4\u5188"
    "4212", # "\u54b8\u5b81"
    "4213", # "\u968f\u5dde"
    "4228", # "\u6069\u65bd"
    "4290", # "\u6f5c\u6c5f/\u4ed9\u6843/\u5929\u95e8"
]


class HbciCHarvester:
    """Harvester for \u6e56\u5317\u7701\u5efa\u7b51\u5e02\u573a\u76d1\u7763\u4e0e\u8bda\u4fe1\u4e00\u4f53\u5316\u5e73\u53f0"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": REFERER,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        })
        self.seen_nos = set()
        self.progress_cb = None  # callback(added, scanned, total)

    def harvest(self, max_pages=200, area_filter="wuhan") -> int:
        """
        Scan recent construction projects.
        max_pages: how many pages to scan (20 per page, 200 pages = 4000 projects)
        area_filter: "wuhan" for Wuhan only, "hubei" for all Hubei
        """
        total_added = 0
        codes = WUHAN_CODES if area_filter == "wuhan" else HUBEI_CODES

        for page in range(max_pages):
            try:
                projects = self._get_page(page)
                if not projects:
                    logger.info(f"[HBCIC] No more projects at page {page}")
                    break

                for p in projects:
                    pno = p.get("projectno", "")
                    # Filter by area code
                    if not any(pno.startswith(c) for c in codes):
                        continue
                    # Check relevance
                    name = p.get("projectname", "")
                    category, level = self._classify(name)
                    if not category:
                        continue
                    # Dedup
                    if pno in self.seen_nos:
                        continue
                    self.seen_nos.add(pno)

                    saved = self._save_project(p, category, level)
                    total_added += saved

                if self.progress_cb:
                    self.progress_cb(total_added, (page + 1) * MAX_PAGE_SIZE, 0)

                time.sleep(random.uniform(0.3, 0.8))
            except Exception as e:
                logger.debug(f"[HBCIC] Page {page} error: {e}")
                time.sleep(1)

        logger.info(f"[HBCIC] Total: +{total_added} project leads from {max_pages} pages")
        return total_added

    def _get_page(self, page_index: int) -> list:
        params = {
            "pageindex": str(page_index),
            "pagesize": str(MAX_PAGE_SIZE),
            "projectname": "",
            "projectno": "",
            "prjtypenum": "01",  # \u623f\u5c4b\u5efa\u7b51
            "blstatus": "",
        }
        body = urlencode(params).encode("utf-8")
        r = self.session.post(API_URL, data=body, timeout=15)
        j = r.json()
        return j.get("custom", {}).get("projectinfoList", [])

    def _classify(self, name: str) -> tuple:
        """Return (category, level) or (None, None) if not relevant."""
        for kw, (cat, level) in RELEVANT_KEYWORDS.items():
            if kw in name:
                return cat, level
        return None, None

    def _save_project(self, project: dict, category: str, level: str) -> int:
        try:
            from crm.models import Lead
            name = project.get("projectname", "").strip()[:100]
            pno = project.get("projectno", "")
            area = project.get("areaname", "")
            addr = project.get("jianshedidian", "")
            date = project.get("bjrq", "")

            # Check for existing
            if Lead.query.filter(Lead.name == name).first():
                return 0

            lead = Lead(
                name=name,
                source="\u5728\u5efa\u5de5\u7a0b",
                source_url=f"http://hbjz.hbcic.net.cn/ythweb/szjs_ythpt/frame/workportal/projectlink.html?prjname={name}",
                address=addr[:300] if addr else "",
                area=area.split("-")[0] if "-" in area else area,
                customer_type="\u5efa\u8bbe\u9879\u76ee",
                product_interest=f"\u5efa\u7b51\u5de5\u7a0b/{category}",
                business_category=category,
                demand_desc=f"[{level}\u7ea7\u9879\u76ee-HBCIC] {name} | \u7f16\u53f7:{pno} | \u5730\u5740:{addr} | \u65e5\u671f:{date}",
                notes=f"\u9879\u76ee\u7f16\u53f7: {pno}\n\u6240\u5c5e\u5730\u533a: {area}\n\u5efa\u8bbe\u5730\u70b9: {addr}\n\u767b\u8bb0\u65e5\u671f: {date}",
            )
            db.session.add(lead)
            db.session.flush()
            score_lead(lead)

            # Level bonus
            if level == "SS":
                lead.total_score = min(100, lead.total_score + 15)
                lead.source_score = min(50, lead.source_score + 10)
            elif level == "S":
                lead.total_score = min(100, lead.total_score + 8)

            if lead.total_score >= 70:
                lead.lead_level = "S"
            elif lead.total_score >= 50:
                lead.lead_level = "A"

            db.session.commit()
            return 1
        except Exception as e:
            db.session.rollback()
            logger.debug(f"[HBCIC] Save failed: {e}")
            return 0
