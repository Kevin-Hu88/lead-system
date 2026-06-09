# -*- coding: utf-8 -*-
"""
Housing Bureau Harvester - Search for construction project announcements
Focuses on government announcement pages and Excel/PDF downloads
"""
import os, re, time, random, requests, tempfile
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from loguru import logger
from crm.models import db, Lead
from crm.scoring import score_lead

# ============================================================
# Target Cities Configuration (verified working URLs)
# ============================================================
TARGET_CITIES = {
    "武汉": {
        "name": "武汉市住房和城市更新局",
        "base_url": "https://zgj.wuhan.gov.cn",
        "search_paths": [
            "/xxgk/tzgg/",
            "/xxgk/zxxx/",
            "/xxgk/bszn/",
        ],
        "keywords": ["在建项目", "施工许可", "竣工验收", "建设工程", "项目公示", "施工备案"],
    },
    "鄂州": {
        "name": "鄂州市住房和城乡建设局",
        "base_url": "https://www.ezhou.gov.cn",
        "search_paths": ["/sy/", "/xxgk/"],
        "keywords": ["在建", "施工许可", "建设工程"],
    },
    "孝感": {
        "name": "孝感市住房和城乡建设局",
        "base_url": "https://www.xiaogan.gov.cn",
        "search_paths": ["/sy/", "/xxgk/"],
        "keywords": ["在建", "施工许可", "建设工程"],
    },
    "黄冈": {
        "name": "黄冈市住房和城乡建设局",
        "base_url": "https://zjw.hg.gov.cn",
        "search_paths": ["/sy/", "/xxgk/"],
        "keywords": ["在建", "施工许可", "建设工程"],
    },
}

# Project classification keywords
PROJECT_KEYWORDS = {
    "学校": {"category": "膜结构", "level": "SS", "desc": "新建/改扩建学校"},
    "教学楼": {"category": "膜结构", "level": "SS", "desc": "教学楼建设"},
    "幼儿园": {"category": "膜结构", "level": "SS", "desc": "幼儿园建设"},
    "商场": {"category": "光伏车棚", "level": "SS", "desc": "大型商业综合体"},
    "购物中心": {"category": "光伏车棚", "level": "SS", "desc": "购物中心建设"},
    "产业园": {"category": "光伏车棚", "level": "S", "desc": "产业园区建设"},
    "工业园": {"category": "光伏车棚", "level": "S", "desc": "工业园区建设"},
    "小区": {"category": "玻璃遮阳棚", "level": "A", "desc": "住宅小区配套"},
    "楼盘": {"category": "玻璃遮阳棚", "level": "A", "desc": "商品房项目"},
    "医院": {"category": "玻璃遮阳棚", "level": "S", "desc": "医院建设"},
}


class HousingBureauHarvester:
    """Harvester for housing bureau construction project announcements"""
    
    def __init__(self, download_dir=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.download_dir = download_dir or os.path.join(tempfile.gettempdir(), "housing_projects")
        os.makedirs(self.download_dir, exist_ok=True)
        self.seen_urls = set()
    
    def harvest(self) -> int:
        """Run housing bureau harvest for all target cities"""
        total = 0
        
        for city, config in TARGET_CITIES.items():
            try:
                logger.info(f"[HousingBureau] Scanning {city}...")
                count = self._scan_city(city, config)
                total += count
                if count > 0:
                    logger.info(f"[HousingBureau] {city}: +{count} project leads")
                time.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.error(f"[HousingBureau] {city} failed: {e}")
        
        logger.info(f"[HousingBureau] Total: +{total} project leads")
        return total
    
    def _scan_city(self, city: str, config: dict) -> int:
        """Scan a city housing bureau website for project announcements"""
        count = 0
        base_url = config["base_url"]
        
        for path in config["search_paths"]:
            try:
                url = base_url + path
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    continue
                
                soup = BeautifulSoup(resp.text, "lxml")
                
                # Find links to project announcements
                for a in soup.select("a"):
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    
                    if not text or len(text) < 8:
                        continue
                    
                    # Check if it's a project-related announcement
                    is_project = False
                    matched_info = None
                    for kw, info in PROJECT_KEYWORDS.items():
                        if kw in text:
                            is_project = True
                            matched_info = info
                            break
                    
                    if not is_project:
                        # Check for general construction keywords
                        if not any(kw in text for kw in config["keywords"]):
                            continue
                    
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    
                    # Resolve full URL
                    full_url = href if href.startswith("http") else urljoin(base_url, href)
                    
                    # Extract project data
                    project_data = self._extract_project_data(full_url, text, city, matched_info)
                    if project_data:
                        count += self._save_project(project_data)
                    
                    time.sleep(random.uniform(1, 2))
            except Exception as e:
                logger.debug(f"[HousingBureau] {city} path {path} failed: {e}")
        
        return count
    
    def _extract_project_data(self, url: str, title: str, city: str, matched_info: dict = None) -> dict:
        """Extract project data from announcement page"""
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code != 200:
                return None
            
            # Check if it's an Excel/PDF file
            content_type = resp.headers.get("Content-Type", "")
            if any(t in content_type for t in ["excel", "spreadsheet", "pdf"]):
                return self._parse_file(resp.content, title, city, matched_info, content_type)
            
            # Parse HTML page for project info
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            
            # Extract project name
            name = title.split("-")[0].split("_")[0].strip()[:80]
            
            # Extract construction unit (建设单位)
            builder = ""
            builder_match = re.search(r"(?:建设单位|建设方|业主)[：:]\s*(.+?)(?:\n|$)", text)
            if builder_match:
                builder = builder_match.group(1).strip()[:60]
            
            # Extract project location
            location = ""
            loc_match = re.search(r"(?:地址|位置|建设地点)[：:]\s*(.+?)(?:\n|$)", text)
            if loc_match:
                location = loc_match.group(1).strip()[:100]
            
            # Extract investment amount
            investment = ""
            inv_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:万元|亿元)", text)
            if inv_match:
                investment = inv_match.group(0)
            
            # Determine category and level
            category = "膜结构"
            level = "A"
            if matched_info:
                category = matched_info.get("category", category)
                level = matched_info.get("level", level)
            else:
                for kw, info in PROJECT_KEYWORDS.items():
                    if kw in text:
                        category = info["category"]
                        level = info["level"]
                        break
            
            # Build notes
            notes_parts = []
            if builder:
                notes_parts.append(f"建设单位: {builder}")
            if location:
                notes_parts.append(f"地址: {location}")
            if investment:
                notes_parts.append(f"投资额: {investment}")
            
            return {
                "name": name,
                "source": "在建工程",
                "source_url": url,
                "demand_desc": f"[{level}级项目-住建局] {title[:150]}",
                "product_interest": f"{city}在建项目",
                "customer_type": "建设项目",
                "area": city,
                "business_category": category,
                "notes": "\n".join(notes_parts) if notes_parts else "",
            }
        except Exception as e:
            logger.debug(f"Extract project data failed: {e}")
            return None
    
    def _parse_file(self, content: bytes, title: str, city: str, matched_info: dict, content_type: str) -> dict:
        """Parse Excel/PDF file for project data"""
        try:
            if "excel" in content_type or "spreadsheet" in content_type:
                return self._parse_excel(content, title, city, matched_info)
            # PDF parsing would go here
            return None
        except Exception as e:
            logger.debug(f"Parse file failed: {e}")
            return None
    
    def _parse_excel(self, content: bytes, title: str, city: str, matched_info: dict) -> dict:
        """Parse Excel file for project data"""
        try:
            import openpyxl
            import io
            
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            
            # Look for project data in first few rows
            for row_idx, row in enumerate(ws.iter_rows(max_row=20, values_only=True)):
                if row_idx == 0:
                    continue  # Skip header
                
                for cell in row:
                    if cell and isinstance(cell, str):
                        for kw, info in PROJECT_KEYWORDS.items():
                            if kw in cell:
                                wb.close()
                                return {
                                    "name": cell[:80],
                                    "source": "在建工程",
                                    "source_url": "",
                                    "demand_desc": f"[{info['level']}级项目-住建局] {title[:150]}",
                                    "product_interest": f"{city}在建项目",
                                    "customer_type": "建设项目",
                                    "area": city,
                                    "business_category": info["category"],
                                }
            
            wb.close()
        except Exception as e:
            logger.debug(f"Parse Excel failed: {e}")
        
        return None
    
    def _save_project(self, data: dict) -> int:
        """Save project lead with appropriate scoring"""
        try:
            # Check for duplicates
            if Lead.query.filter_by(name=data["name"]).first():
                return 0
            
            lead = Lead(**data)
            db.session.add(lead)
            db.session.flush()
            
            # Score the lead
            score_lead(lead)
            
            # Apply level bonus for housing bureau data
            desc = data.get("demand_desc", "")
            if "SS" in desc:
                lead.total_score = min(100, lead.total_score + 15)
                lead.lead_level = "S"
            elif "S级" in desc:
                lead.total_score = min(100, lead.total_score + 8)
            
            db.session.commit()
            return 1
        except Exception as e:
            logger.debug(f"Save project failed: {e}")
            return 0
