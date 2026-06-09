# -*- coding: utf-8 -*-
"""
行业垂直平台采集器

数据源：
1. 物业行业：物业帮、物业之家
2. 工厂/制造：中国制造网、1688
3. 学校/教育：中国教育装备网
4. 医院/医疗：中国医疗装备协会
5. 新能源/充电：中国充电联盟
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from loguru import logger
from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner


class IndustryHarvester:
    """行业垂直平台采集器"""

    # 行业平台配置
    INDUSTRY_SITES = {
        "物业": [
            {
                "name": "中国物业管理协会",
                "url": "http://www.ecpmi.org.cn",
                "search_path": "/search?q={keyword}",
                "keywords": ["武汉 物业公司", "湖北 物业管理"],
            },
            {
                "name": "物业帮",
                "url": "https://www.wuye帮.com",
                "search_path": "/search?keyword={keyword}",
                "keywords": ["武汉 物业", "湖北 物业公司"],
            },
        ],
        "工厂": [
            {
                "name": "中国制造网",
                "url": "https://cn.made-in-china.com",
                "search_path": "/product-search/{keyword}.html",
                "keywords": ["武汉 工厂", "湖北 制造企业"],
            },
            {
                "name": "1688",
                "url": "https://s.1688.com",
                "search_path": "/selloffer/offer_search.htm?keywords={keyword}",
                "keywords": ["武汉 工厂", "湖北 生产企业"],
            },
        ],
        "学校": [
            {
                "name": "中国教育装备网",
                "url": "http://www.ceiea.com",
                "search_path": "/search?keyword={keyword}",
                "keywords": ["武汉 学校", "湖北 学校"],
            },
        ],
        "医院": [
            {
                "name": "中国医疗装备协会",
                "url": "http://www.cmdea.org",
                "search_path": "/search?keyword={keyword}",
                "keywords": ["武汉 医院", "湖北 医院"],
            },
        ],
        "新能源": [
            {
                "name": "中国充电联盟",
                "url": "http://www.evcsta.org.cn",
                "search_path": "/search?keyword={keyword}",
                "keywords": ["武汉 充电站", "湖北 充电桩"],
            },
        ],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def harvest(self) -> int:
        """执行采集"""
        total = 0

        for industry, sites in self.INDUSTRY_SITES.items():
            for site in sites:
                try:
                    leads = self._scrape_site(site, industry)
                    count = DataCleaner.clean_and_save_batch(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[Industry] {industry}/{site['name']}: +{count}")
                    time.sleep(random.uniform(2, 5))
                except Exception as e:
                    logger.error(f"[Industry] failed [{industry}/{site['name']}]: {e}")

        return total

    def _scrape_site(self, site: dict, industry: str) -> list:
        """抓取单个行业平台"""
        results = []

        for keyword in site["keywords"]:
            try:
                url = site["url"] + site["search_path"].format(keyword=quote(keyword))
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # 查找企业列表
                for item in soup.select(".company-item, .enterprise-item, .result-item, li"):
                    try:
                        # 提取企业名称
                        name_el = item.select_one("h3 a, .company-name a, .title a, a")
                        if not name_el:
                            continue

                        name = name_el.get_text(strip=True)
                        if not name or len(name) < 3:
                            continue

                        # 提取电话
                        phone = ""
                        phone_el = item.select_one(".phone, .tel, .contact")
                        if phone_el:
                            phone = DataCleaner.extract_phone(phone_el.get_text())

                        # 提取地址
                        address = ""
                        addr_el = item.select_one(".address, .addr")
                        if addr_el:
                            address = addr_el.get_text(strip=True)

                        # 提取链接
                        href = name_el.get("href", "")
                        source_url = urljoin(site["url"], href) if href else ""

                        # 构建线索数据
                        lead = {
                            "name": name,
                            "phone": phone,
                            "address": address[:300] if address else "",
                            "source": f"industry_{industry}",
                            "source_url": source_url,
                            "area": "武汉",
                            "customer_type": industry,
                            "product_interest": industry,
                            "demand_desc": f"行业平台: {site['name']}",
                            "notes": f"来源: {site['name']}",
                        }

                        results.append(lead)

                    except Exception as e:
                        logger.debug(f"解析企业项失败: {e}")

            except Exception as e:
                logger.debug(f"抓取页面失败 [{site['name']}/{keyword}]: {e}")

        return results
