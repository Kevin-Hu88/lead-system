# -*- coding: utf-8 -*-
"""
Bid harvester v3 - Expanded keywords + multi-page CCGP + Baidu regional
Target: 30-50 S-level leads/day
"""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner

# Selenium for dynamic pages
try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options as EdgeOptions
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

# Full industry keyword library (23 keywords)
# Business category keywords
BUSINESS_CATEGORIES = {
    "膜结构": {
        "label": "膜结构",
        "keywords": [
            "膜结构车棚", "膜结构工程", "张拉膜结构", "景观膜结构", "膜结构",
            "非机动车停车棚", "电动自行车停车棚", "推拉棚", "伸缩棚",
            "园区雨棚改造", "出入口遮阳篷", "车棚安装工程", "车棚改造工程",
            "老旧小区车棚", "停车场遮阳棚施工", "雨棚", "遮阳棚",
            # 上游立项阶段词 - 项目刚立项，竞争小
            "钢结构工程", "雨棚改造", "停车棚修缮", "屋顶加固",
            "学校操场翻新", "物流园二期", "厂房翻新改造",
        ],
    },
    "玻璃遮阳棚": {
        "label": "玻璃遮阳棚",
        "keywords": [
            "玻璃雨棚", "玻璃遮阳棚", "玻璃车棚", "钢结构玻璃雨棚",
            "铝合金遮阳棚", "耐力板车棚", "阳光板车棚", "PC板车棚",
            "玻璃幕墙遮阳", "采光顶遮阳", "玻璃顶棚", "钢结构雨棚",
            "停车棚", "车棚", "遮阳工程", "停车设施",
        ],
    },
    "光伏车棚": {
        "label": "光伏车棚",
        "keywords": [
            "光伏车棚", "光伏发电车棚", "太阳能车棚", "光伏停车棚",
            "充电桩车棚", "光储充一体化", "光伏遮阳棚", "BIPV车棚",
            "分布式光伏车棚", "光伏雨棚", "光伏廊架", "车棚光伏",
            "充电桩停车棚", "光伏电站", "分布式光伏",
            # 上游立项阶段词
            "分布式光伏备案", "光伏电站建设", "新能源充电设施",
            "光储充项目", "屋顶光伏发电",
        ],
    },
}

# Default: all keywords combined (for backward compatibility)
BID_KEYWORDS = []
for cat in BUSINESS_CATEGORIES.values():
    BID_KEYWORDS.extend(cat["keywords"])
BID_KEYWORDS = list(dict.fromkeys(BID_KEYWORDS))  # Deduplicate, preserve order

# Hubei region keywords for Baidu search
HUBEI_REGIONS = ["武汉", "湖北", "鄂州", "孝感", "黄冈", "咸宁", "荆州", "宜昌", "襄阳", "十堰"]


class BidHarvester:

    def __init__(self):
        self.session = requests.Session()
        self._rotate_ua()
        self.seen_urls = set()

    def _rotate_ua(self):
        """Rotate user agent - Safari works best with CCGP"""
        agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        ]
        self.session.headers.update({
            "User-Agent": random.choice(agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    def harvest(self, category: str = None) -> int:
        """Harvest leads, optionally filtered by business category"""
        total = 0
        
        # Get keywords for the specified category or all categories
        if category and category in BUSINESS_CATEGORIES:
            keywords = BUSINESS_CATEGORIES[category]["keywords"]
            logger.info(f"[BidHarvest] Category: {category}, Keywords: {len(keywords)}")
        else:
            keywords = BID_KEYWORDS
            logger.info(f"[BidHarvest] All categories, Keywords: {len(keywords)}")

        # Source 1: CCGP - multi-page per keyword
        for kw in keywords:
            try:
                leads = self._search_ccgp(kw, pages=3)
                count = self._save_leads(leads)
                total += count
                if count > 0:
                    logger.info(f"[CCGP] {kw}: +{count}")
                time.sleep(random.uniform(3.0, 6.0))
            except Exception as e:
                logger.error(f"[CCGP] failed [{kw}]: {e}")

        # Source 2: Baidu regional search (Hubei-focused)
        for kw in BID_KEYWORDS[:10]:
            for region in HUBEI_REGIONS[:5]:
                try:
                    leads = self._search_baidu_regional(kw, region)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[Baidu-{region}] {kw}: +{count}")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    logger.debug(f"[Baidu-{region}] failed [{kw}]: {e}")

        # Source 3: Bing search (less restrictive than Baidu)
        for kw in BID_KEYWORDS[:10]:
            try:
                leads = self._search_bing_bid(kw)
                count = self._save_leads(leads)
                total += count
                if count > 0:
                    logger.info(f"[Bing-bid] {kw}: +{count}")
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                logger.debug(f"[Bing-bid] failed [{kw}]: {e}")

        # Source 4: Qianlima.com (Selenium)
        if HAS_SELENIUM:
            for kw in BID_KEYWORDS[:8]:
                try:
                    leads = self._search_qianlima(kw)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[Qianlima] {kw}: +{count}")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    logger.debug(f"[Qianlima] failed [{kw}]: {e}")

            # Source 5: Hubei public resource platform (Selenium)
            for kw in BID_KEYWORDS[:5]:
                try:
                    leads = self._search_hbggzy(kw)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[HBGgzy] {kw}: +{count}")
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    logger.debug(f"[HBGgzy] failed [{kw}]: {e}")

        return total

    def _search_ccgp(self, keyword: str, pages: int = 3) -> list:
        """Search ccgp.gov.cn with multiple bid types and broader matching"""
        results = []
        # Search across different bid types for maximum coverage
        search_configs = [
            {"bidType": "1", "dbselect": "bidx"},   # 招标公告
            {"bidType": "1", "dbselect": "v1"},     # 采购意向
        ]
        # Relevant keywords for carport/shelter projects
        RELEVANT_KEYWORDS = [
            "车棚", "遮阳棚", "雨棚", "膜结构", "停车棚", "充电桩棚", "推拉棚", "伸缩棚",
            "光伏车棚", "张拉膜", "景观膜", "遮阳篷", "遮阳工程",
            # 上游工程词 - 立项阶段就命中
            "钢结构工程", "雨棚改造", "停车棚修缮", "屋顶加固", "操场翻新",
            "光伏备案", "光伏电站", "充电设施", "光储充",
            "分布式光伏", "屋顶光伏", "新能源车棚",
            # 建设工程配套词
            "室外配套", "园区配套", "老旧小区改造", "学校新建", "医院新建",
            "物流园", "工业园", "产业园",
        ]
        # Exclusion keywords - filter out agricultural greenhouses, ads, irrelevant
        EXCLUDE_KEYWORDS = ["大棚", "温室", "种植", "养殖", "农业", "蔬菜", "草莓", "木耳", "蘑菇", "棚改", "棚户", "拆迁", "十里棚", "品牌", "厂家", "报价", "价格", "选购", "推荐榜", "排行榜", "怎么选", "哪个好", "服务商", "供应商"]
        for cfg_idx, cfg in enumerate(search_configs):
            if cfg_idx > 0:
                time.sleep(random.uniform(5, 10))  # Longer delay between search types
            for page in range(1, pages + 1):
                try:
                    url = "http://search.ccgp.gov.cn/bxsearch"
                    params = {
                        "searchtype": "1", "page_index": str(page), "bidSort": "0",
                        "bidType": cfg["bidType"], "dbselect": cfg["dbselect"], "kw": keyword,
                        "start_time": "2025:01:01", "end_time": "2026:12:31",
                        "timeType": "6",
                    }
                    resp = self.session.get(url, params=params, timeout=20)
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "lxml")
                    page_results = 0
                    # CCGP results are in .vT-srch-result-list-bid li
                    for item in soup.select(".vT-srch-result-list-bid li, .vT-srch-result-list li"):
                        try:
                            a = item.select_one("a")
                            if not a:
                                continue
                            text = a.get_text(strip=True)
                            href = a.get("href", "")
                            if not text or len(text) < 8:
                                continue
                            if not href or not href.startswith("http"):
                                continue
                            # Must be a real procurement notice
                            if not any(kw in text for kw in ["招标", "采购", "公告", "比选", "询价", "竞争性", "磋商", "谈判"]):
                                continue
                            # Must NOT contain exclusion keywords
                            if any(kw in text for kw in EXCLUDE_KEYWORDS):
                                continue
                            if href in self.seen_urls:
                                continue
                            self.seen_urls.add(href)
                            # Extract date and buyer from span
                            date_text = ""
                            buyer = ""
                            span = item.select_one("span")
                            if span:
                                span_text = span.get_text(strip=True)
                                date_match = re.search(r"(\d{4}\.\d{2}\.\d{2})", span_text)
                                if date_match:
                                    date_text = date_match.group(1)
                                buyer_match = re.search(r"采购人[：:]\s*(.+?)(?:\s|$)", span_text)
                                if buyer_match:
                                    buyer = buyer_match.group(1).strip()
                            # Build name from title
                            name = text.split("招标")[0].split("采购")[0].split("公开")[0].split("竞争性")[0].strip()
                            if len(name) > 80:
                                name = name[:80]
                            if not name:
                                name = text[:60]
                            # Extract buyer org from title if not found in span
                            if not buyer:
                                org_match = re.search(r"([一-龥]{4,}(?:局|委|院|学校|医院|公司|中心|政府|大队|街道|办事处))", text)
                                if org_match:
                                    buyer = org_match.group(1)
                            # Extract area
                            area = ""
                            for region in HUBEI_REGIONS + ["黄石", "随州", "恩施", "仙桃", "潜江", "天门", "武汉"]:
                                if region in text or region in buyer:
                                    area = region
                                    break
                            # Determine business category from keyword
                            biz_cat = "膜结构"
                            for cat_name, cat_info in BUSINESS_CATEGORIES.items():
                                if keyword in cat_info["keywords"]:
                                    biz_cat = cat_name
                                    break
                            desc = "[S级招标] {0}".format(text[:200])
                            if buyer:
                                desc += " | 采购人: " + buyer
                            if date_text:
                                desc += " | " + date_text
                            results.append({
                                "name": name,
                                "source": "招标平台",
                                "source_url": href,
                                "demand_desc": desc,
                                "product_interest": keyword,
                                "customer_type": "招标项目",
                                "area": area,
                                "business_category": biz_cat,
                            })
                            page_results += 1
                        except Exception:
                            continue
                    if page_results == 0:
                        break
                        break
                except Exception:
                    break
        return results

    def _search_baidu_regional(self, keyword: str, region: str) -> list:
        """Baidu search for Hubei regional bidding notices"""
        results = []
        try:
            query = f"{region} {keyword} 招标公告 site:ccgp.gov.cn OR site:hbggzy.cn"
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
                    if not any(kw in title for kw in ["车棚", "遮阳", "雨棚", "膜结构", "停车", "棚", "招标", "采购"]):
                        continue
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    name = title.split("-")[0].split("_")[0].split("招标")[0].strip()[:60]
                    if not name:
                        continue
                    results.append({
                        "name": name,
                        "source": "招标平台",
                        "source_url": href,
                        "demand_desc": f"[S级招标-{region}] {title[:200]}",
                        "product_interest": keyword,
                        "customer_type": "招标项目",
                        "area": region,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Baidu regional search failed: {e}")
        return results

    def _search_baidu_bid(self, keyword: str) -> list:
        """Baidu general search for bidding notices"""
        results = []
        try:
            query = f"{keyword} 招标公告 2026"
            url = f"https://www.baidu.com/s?wd={quote(query)}&rn=10"
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select(".result, .c-container"):
                try:
                    title_el = item.select_one("h3 a, .t a")
                    desc_el = item.select_one(".c-abstract, .c-span-last")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    if "招标" not in title and "采购" not in title and "公告" not in title:
                        continue
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    phone = ""
                    pm = re.search(r"1[3-9]\d{9}", f"{title} {desc}")
                    if pm:
                        phone = pm.group()
                    name = title.split("-")[0].split("_")[0].split("招标")[0].strip()[:60]
                    if not name:
                        continue
                    results.append({
                        "name": name, "phone": phone,
                        "source": "招标平台",
                        "source_url": href,
                        "demand_desc": f"[S级招标] {title[:100]} | {desc[:100]}",
                        "product_interest": keyword,
                        "customer_type": "招标项目",
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Baidu bid search failed: {e}")
        return results

    def _get_selenium_driver(self):
        """Create a headless Edge driver"""
        opts = EdgeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,720")
        driver = webdriver.Edge(options=opts)
        driver.set_page_load_timeout(15)
        return driver

    def _search_qianlima(self, keyword: str) -> list:
        """Search qianlima.com (千里马招标) with Selenium"""
        results = []
        if not HAS_SELENIUM:
            return results
        driver = None
        try:
            driver = self._get_selenium_driver()
            url = "https://www.qianlima.com/zb/search?keyword={0}".format(quote(keyword))
            driver.get(url)
            time.sleep(2)
            soup = __import__("bs4").BeautifulSoup(driver.page_source, "lxml")
            for item in soup.select(".search-result-item, .zb-item, .list-item, a[href*='/zb/']"):
                try:
                    title_el = item.select_one("a, .title, h3")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    if not title or len(title) < 10:
                        continue
                    if not any(kw in title for kw in ["车棚", "遮阳", "雨棚", "膜结构", "停车", "棚", "推拉", "伸缩"]):
                        continue
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    full_url = href if href.startswith("http") else "https://www.qianlima.com" + href
                    name = title.split("-")[0].split("招标")[0].strip()[:60]
                    if not name:
                        name = title[:60]
                    area = ""
                    for region in HUBEI_REGIONS + ["黄石", "随州", "恩施", "仙桃", "潜江", "天门"]:
                        if region in title:
                            area = region
                            break
                    results.append({
                        "name": name, "source": "招标平台",
                        "source_url": full_url,
                        "demand_desc": "[S级招标-千里马] {0}".format(title[:200]),
                        "product_interest": keyword,
                        "customer_type": "招标项目",
                        "area": area,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Qianlima search failed: {e}")
        finally:
            if driver:
                try: driver.quit()
                except: pass
        return results

    def _search_hbggzy(self, keyword: str) -> list:
        """Search hubei public resource platform with Selenium"""
        results = []
        if not HAS_SELENIUM:
            return results
        driver = None
        try:
            driver = self._get_selenium_driver()
            driver.get("https://www.hbggzy.cn/jyxx/003001/trade_info_msg.html")
            time.sleep(3)
            soup = __import__("bs4").BeautifulSoup(driver.page_source, "lxml")
            for a in soup.select("a"):
                try:
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    if not text or len(text) < 10:
                        continue
                    if not any(kw in text for kw in ["车棚", "遮阳", "雨棚", "膜结构", "停车", "棚"]):
                        continue
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    full_url = href if href.startswith("http") else "https://www.hbggzy.cn" + href
                    name = text.split("招标")[0].split("采购")[0].strip()[:60]
                    if not name:
                        name = text[:60]
                    results.append({
                        "name": name, "source": "招标平台",
                        "source_url": full_url,
                        "demand_desc": "[S级招标-湖北公共资源] {0}".format(text[:200]),
                        "product_interest": keyword,
                        "customer_type": "招标项目",
                        "area": "湖北",
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"HBGgzy search failed: {e}")
        finally:
            if driver:
                try: driver.quit()
                except: pass
        return results

    def _search_bing_bid(self, keyword: str) -> list:
        """Bing search for bidding notices (less restrictive than Baidu)"""
        results = []
        try:
            query = "{0} 招标公告 2026 site:ccgp.gov.cn".format(keyword)
            url = "https://cn.bing.com/search?q={0}&count=20".format(quote(query))
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select(".b_algo"):
                try:
                    title_el = item.select_one("h2 a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    if not any(kw in title for kw in ["车棚", "遮阳", "雨棚", "膜结构", "停车", "棚"]):
                        continue
                    if href in self.seen_urls:
                        continue
                    self.seen_urls.add(href)
                    name = title.split("-")[0].split("_")[0].split("招标")[0].strip()[:60]
                    if not name:
                        continue
                    area = ""
                    for region in HUBEI_REGIONS + ["黄石", "随州", "恩施"]:
                        if region in title:
                            area = region
                            break
                    # Determine business category
                    biz_cat = "膜结构"
                    for cat_name, cat_info in BUSINESS_CATEGORIES.items():
                        if keyword in cat_info["keywords"]:
                            biz_cat = cat_name
                            break
                    results.append({
                        "name": name, "source": "招标平台",
                        "source_url": href,
                        "demand_desc": "[S级招标-Bing] {0}".format(title[:200]),
                        "product_interest": keyword,
                        "customer_type": "招标项目",
                        "area": area,
                        "business_category": biz_cat,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Bing bid search failed: {e}")
        return results

    def _save_leads(self, leads: list) -> int:
        saved = 0
        for data in leads:
            try:
                if data.get("phone") and Lead.query.filter_by(phone=data["phone"]).first():
                    continue
                if Lead.query.filter_by(name=data["name"]).first():
                    continue
                lead = Lead(**data)
                db.session.add(lead)
                saved += 1
            except Exception:
                pass
        if saved > 0:
            db.session.commit()
        return saved
