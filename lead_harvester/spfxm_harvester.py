# -*- coding: utf-8 -*-
"""
SPFXM Harvester v3 - 武汉商品房项目查询系统
URL: http://spfxm.whfgxx.org.cn:8083/spfxmcx/spfcx_index.aspx

核心改进：
v3: 进入每个项目明细页，抓取联系电话、开发企业、栋数、套数等
"""
import re, time, random
from loguru import logger
from crm.models import db, Lead
from crm.scoring import score_lead

SITE_URL = "http://spfxm.whfgxx.org.cn:8083/spfxmcx/spfcx_index.aspx"

# 区域列表
DISTRICTS = [
    "", "江岸区", "江汉区", "硚口区", "武昌区",
    "洪山区", "东西湖区", "汉南区", "蔡甸区",
    "江夏区", "黄陂区", "新洲区",
]

# ============================================================
# 项目年龄 → 需求场景
# ============================================================
# 新建项目（3年内）：配套车棚，找开发商
# 老项目（10+年）：翻新需求，找物业
PROJECT_AGE_MAP = {
    "new": {  # 3年内
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "新建项目配套车棚，找开发商或物业公司",
        "score_bonus": 15,
        "stage": "新建",
    },
    "mid": {  # 3-10年
        "products": ["膜结构车棚", "遮阳棚"],
        "pitch": "项目运营中，可能有增补或翻新需求",
        "score_bonus": 8,
        "stage": "运营中",
    },
    "old": {  # 10年以上
        "products": ["膜结构车棚", "翻新改造", "充电桩雨棚"],
        "pitch": "老项目翻新改造，充电桩配套是政策要求，找物业公司",
        "score_bonus": 12,
        "stage": "翻新",
    },
}

# 项目类型 → 需求场景映射
PROJECT_DEMAND_MAP = {
    "居住": {
        "customer_type": "物业",
        "products": ["膜结构车棚", "充电桩雨棚", "非机动车棚"],
        "pitch": "新建小区交房配套，业主停车刚需，找物业公司或开发商",
        "score_bonus": 15,
        "stage": "在建",
    },
    "住宅": {
        "customer_type": "物业",
        "products": ["膜结构车棚", "充电桩雨棚"],
        "pitch": "住宅项目必须配套车棚，找物业或开发商",
        "score_bonus": 15,
        "stage": "在建",
    },
    "商业": {
        "customer_type": "商业",
        "products": ["光伏车棚", "景观遮阳棚", "膜结构车棚"],
        "pitch": "商业项目注重形象，景观膜结构是卖点，找商管公司",
        "score_bonus": 12,
        "stage": "在建",
    },
    "商务": {
        "customer_type": "商业",
        "products": ["光伏车棚", "膜结构车棚"],
        "pitch": "商务楼配套车棚，找物业管理方",
        "score_bonus": 10,
        "stage": "在建",
    },
    "酒店": {
        "customer_type": "酒店",
        "products": ["膜结构车棚", "景观遮阳棚"],
        "pitch": "酒店门头车棚提升形象，找酒店管理方",
        "score_bonus": 10,
        "stage": "在建",
    },
    "学校": {
        "customer_type": "学校",
        "products": ["膜结构车棚", "玻璃遮阳棚", "操场遮阳棚"],
        "pitch": "学校车棚安全要求高，资质是硬门槛，找总务处",
        "score_bonus": 18,
        "stage": "在建",
    },
    "幼儿园": {
        "customer_type": "学校",
        "products": ["膜结构车棚", "玻璃遮阳棚"],
        "pitch": "幼儿园车棚安全第一，找园长或后勤",
        "score_bonus": 18,
        "stage": "在建",
    },
    "医院": {
        "customer_type": "医院",
        "products": ["玻璃遮阳棚", "膜结构车棚", "无障碍车棚"],
        "pitch": "医院车棚要求高，无障碍设计是加分项，找后勤部",
        "score_bonus": 15,
        "stage": "在建",
    },
    "产业园": {
        "customer_type": "工厂",
        "products": ["光伏车棚", "膜结构车棚"],
        "pitch": "产业园招商配套，找园区管委会或开发商",
        "score_bonus": 10,
        "stage": "在建",
    },
    "工业园": {
        "customer_type": "工厂",
        "products": ["膜结构车棚", "光伏车棚"],
        "pitch": "工业园配套车棚，找园区管理方",
        "score_bonus": 10,
        "stage": "在建",
    },
    "停车": {
        "customer_type": "物业",
        "products": ["膜结构车棚", "光伏车棚"],
        "pitch": "停车场配套车棚是刚需，找停车场运营方",
        "score_bonus": 12,
        "stage": "在建",
    },
    "充电": {
        "customer_type": "新能源",
        "products": ["光伏车棚", "充电桩雨棚"],
        "pitch": "充电站配套车棚，光伏车棚还能发电",
        "score_bonus": 12,
        "stage": "在建",
    },
}


class SpfxmHarvester:
    """武汉商品房项目查询系统采集器 v3 - 抓取明细页"""

    def __init__(self):
        self.seen_names = set()

    def harvest(self) -> int:
        """执行采集"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait, Select
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            logger.warning("[SPFXM] Selenium not installed, skipping")
            return 0

        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")

        driver = None
        total_added = 0

        try:
            driver = webdriver.Chrome(options=opts)
            driver.set_page_load_timeout(30)
            driver.get(SITE_URL)
            time.sleep(3)

            # Check if site is alive
            if "错误" in driver.title or "404" in driver.title or "cannot" in driver.title.lower():
                logger.warning("[SPFXM] Site appears to be down, skipping")
                return 0

            logger.info(f"[SPFXM] Loaded: {driver.title}")

            # Query each district
            for district in DISTRICTS:
                try:
                    count = self._query_district(driver, district)
                    total_added += count
                    if count > 0:
                        logger.info(f"[SPFXM] {district or '全部'}: +{count}")
                    time.sleep(random.uniform(1, 3))
                except Exception as e:
                    logger.debug(f"[SPFXM] District '{district}' failed: {e}")

        except Exception as e:
            logger.error(f"[SPFXM] Failed: {e}")
        finally:
            if driver:
                driver.quit()

        logger.info(f"[SPFXM] Total: +{total_added} project leads")
        return total_added

    def _query_district(self, driver, district: str) -> int:
        """查询单个区域"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC

        added = 0

        # Navigate to search page
        driver.get(SITE_URL)
        time.sleep(2)

        # Find and fill district dropdown
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in selects:
                label = sel.get_attribute("id") or sel.get_attribute("name") or ""
                if "区" in label.lower() or "area" in label.lower() or "quyu" in label.lower():
                    select = Select(sel)
                    if district:
                        for opt in select.options:
                            if district in opt.text:
                                select.select_by_visible_text(opt.text)
                                break
                    else:
                        select.select_by_index(0)
                    break
        except Exception:
            pass

        # Click search button
        try:
            buttons = driver.find_elements(By.TAG_NAME, "input")
            for btn in buttons:
                if btn.get_attribute("type") == "submit" or "查询" in (btn.get_attribute("value") or ""):
                    btn.click()
                    time.sleep(3)
                    break
        except Exception:
            pass

        # Extract results from table
        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                # Get header to understand columns
                headers = []
                if rows:
                    header_cells = rows[0].find_elements(By.TAG_NAME, "th")
                    if not header_cells:
                        header_cells = rows[0].find_elements(By.TAG_NAME, "td")
                    headers = [c.text.strip() for c in header_cells]

                for row in rows[1:]:  # skip header
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3:
                        continue
                    
                    # Find project link in the row
                    project_link = None
                    for cell in cells:
                        links = cell.find_elements(By.TAG_NAME, "a")
                        if links:
                            project_link = links[0]
                            break
                    
                    # Extract basic info from list row
                    project_data = self._extract_row(cells, headers, district)
                    if not project_data:
                        continue
                    
                    # If we found a project link, click into detail page
                    if project_link:
                        try:
                            detail_info = self._scrape_detail_page(driver, project_link)
                            if detail_info:
                                project_data.update(detail_info)
                        except Exception as e:
                            logger.debug(f"[SPFXM] Detail page failed: {e}")
                    
                    saved = self._save_project(project_data)
                    added += saved
        except Exception as e:
            logger.debug(f"[SPFXM] Extract failed: {e}")

        return added

    def _scrape_detail_page(self, driver, link_element) -> dict:
        """点击项目链接，进入明细页抓取详细信息"""
        from selenium.webdriver.common.by import By
        
        detail = {}
        
        try:
            # Click the project link
            link_element.click()
            time.sleep(2)
            
            # Get page text
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Extract developer (开发企业)
            dev_match = re.search(r"开发企业\s*\n\s*(.+?)(?:\n|$)", page_text)
            if dev_match:
                detail["developer"] = dev_match.group(1).strip()
            
            # Extract phone (联系电话)
            phone_match = re.search(r"联系电话\s*\n\s*(1[3-9]\d{9}|0\d{2,3}[-]?\d{7,8})", page_text)
            if phone_match:
                detail["phone"] = phone_match.group(1).strip()
            
            # Extract number of buildings (房屋栋数)
            buildings_match = re.search(r"房屋栋数\s*\n\s*(\d+)", page_text)
            if buildings_match:
                detail["buildings"] = buildings_match.group(1).strip()
            
            # Extract number of units (房屋套数)
            units_match = re.search(r"房屋套数\s*\n\s*(\d+)", page_text)
            if units_match:
                detail["units"] = units_match.group(1).strip()
            
            # Extract building area (建筑面积)
            area_match = re.search(r"建筑面积\s*\n\s*([\d.]+)", page_text)
            if area_match:
                detail["building_area"] = area_match.group(1).strip()
            
            # Extract location (项目坐落)
            location_match = re.search(r"项目坐落\s*\n\s*(.+?)(?:\n|$)", page_text)
            if location_match:
                detail["location"] = location_match.group(1).strip()
            
            # Go back to list
            driver.back()
            time.sleep(1)
            
        except Exception as e:
            logger.debug(f"[SPFXM] Detail extraction failed: {e}")
            # Try to go back if we're stuck
            try:
                driver.back()
            except:
                pass
        
        return detail

    def _extract_row(self, cells, headers: list, district: str) -> dict:
        """提取项目数据"""
        texts = [c.text.strip() for c in cells]
        if not any(texts):
            return None

        # Try to map columns by header names
        data = {}
        for i, header in enumerate(headers):
            if i >= len(texts):
                break
            text = texts[i]
            if not text:
                continue

            header_lower = header.lower()
            if "项目" in header or "名称" in header:
                data["project_name"] = text
            elif "开发" in header or "企业" in header:
                data["developer"] = text
            elif "区" in header or "区域" in header:
                data["district"] = text
            elif "地址" in header:
                data["address"] = text

        # Fallback
        if "project_name" not in data:
            data["project_name"] = texts[0]

        name = data.get("project_name", "")
        if not name or len(name) < 4:
            return None
        if name in self.seen_names:
            return None
        self.seen_names.add(name)

        return {
            "name": name[:100],
            "source": "商品房项目",
            "source_url": SITE_URL,
            "district": data.get("district", district),
        }

    def _save_project(self, data: dict) -> int:
        """保存项目"""
        try:
            name = data.get("name", "")
            if Lead.query.filter_by(name=name).first():
                return 0

            # Extract year from notes
            year = None
            year_match = re.search(r"开工年份:\s*(\d{4})", data.get("notes", ""))
            if year_match:
                year = int(year_match.group(1))
            
            # Detect demand scenario
            demand = self._detect_demand(name, year)

            # Build area
            district = data.get("district", "")
            area = f"武汉{district}" if district else "武汉"

            # Build notes
            notes_parts = []
            if data.get("developer"):
                notes_parts.append(f"开发企业: {data['developer']}")
            if data.get("phone"):
                notes_parts.append(f"联系电话: {data['phone']}")
            if data.get("buildings"):
                notes_parts.append(f"房屋栋数: {data['buildings']}栋")
            if data.get("units"):
                notes_parts.append(f"房屋套数: {data['units']}套")
            if data.get("building_area"):
                notes_parts.append(f"建筑面积: {data['building_area']}m²")
            if data.get("location"):
                notes_parts.append(f"项目坐落: {data['location']}")
            notes_parts.append(f"推荐产品: {'、'.join(demand['products'])}")
            notes_parts.append(f"跟进策略: {demand['pitch']}")

            lead = Lead(
                name=name[:100],
                phone=data.get("phone", ""),
                contact_person=data.get("developer", ""),
                source="商品房项目",
                source_url=SITE_URL,
                area=area,
                customer_type=demand["customer_type"],
                product_interest="、".join(demand["products"]),
                business_category=demand["products"][0] if demand["products"] else "膜结构",
                demand_desc=(
                    f"[{demand['stage']}] [{demand['customer_type']}] "
                    f"需求产品: {'、'.join(demand['products'])} | "
                    f"{name}"
                ),
                notes="\n".join(notes_parts),
            )
            db.session.add(lead)
            db.session.flush()

            # Score
            score_lead(lead)
            lead.total_score = min(100, lead.total_score + demand["score_bonus"])
            lead.score = lead.total_score

            # Re-determine level
            if lead.total_score >= 70:
                lead.lead_level = "S"
            elif lead.total_score >= 50:
                lead.lead_level = "A"
            elif lead.total_score >= 30:
                lead.lead_level = "B"
            else:
                lead.lead_level = "C"

            db.session.commit()
            return 1
        except Exception as e:
            db.session.rollback()
            logger.debug(f"[SPFXM] Save failed: {e}")
            return 0

    def _detect_demand(self, project_name: str, year: int = None) -> dict:
        """根据项目名称和年龄检测需求场景"""
        # First try keyword matching
        for keyword, demand in PROJECT_DEMAND_MAP.items():
            if keyword in project_name:
                # If we have year info, adjust the demand
                if year:
                    age_demand = self._get_age_demand(year)
                    # Merge: use keyword demand for customer_type/products, age for pitch
                    return {
                        "customer_type": demand["customer_type"],
                        "products": demand["products"],
                        "pitch": age_demand["pitch"],
                        "score_bonus": demand["score_bonus"] + age_demand.get("score_bonus", 0),
                        "stage": age_demand["stage"],
                    }
                return demand
        
        # No keyword match, use age-based demand
        if year:
            return self._get_age_demand(year)
        
        return {
            "customer_type": "建设项目",
            "products": ["膜结构车棚", "遮阳棚"],
            "pitch": "在建项目，有车棚/遮阳棚配套需求",
            "score_bonus": 5,
            "stage": "在建",
        }
    
    def _get_age_demand(self, year: int) -> dict:
        """根据项目年龄返回需求场景"""
        import datetime
        current_year = datetime.datetime.now().year
        age = current_year - year
        
        if age <= 3:
            return PROJECT_AGE_MAP["new"]
        elif age <= 10:
            return PROJECT_AGE_MAP["mid"]
        else:
            return PROJECT_AGE_MAP["old"]


