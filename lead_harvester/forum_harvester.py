# -*- coding: utf-8 -*-
"""
Forum harvester - use Baidu search to find forum/Q&A posts about carports.
(Baidu Tieba direct access returns 403, so we search via Baidu web search instead)
"""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from fake_useragent import UserAgent
from config import settings
from crm.models import db, Lead

ua = UserAgent()

FORUM_QUERIES = [
    "\u8f66\u68da \u5b89\u88c5 \u627e\u8c01",
    "\u819c\u7ed3\u6784\u8f66\u68da \u591a\u5c11\u94b1\u4e00\u5e73",
    "\u505c\u8f66\u68da \u5382\u5bb6 \u63a8\u8350",
    "\u7535\u52a8\u906e\u9633\u68da \u54ea\u5bb6\u597d",
    "\u96e8\u68da \u5b9a\u5236 \u62a5\u4ef7",
    "\u5145\u7535\u6869\u8f66\u68da \u5efa\u8bbe",
    "\u819c\u7ed3\u6784 \u5de5\u7a0b \u65bd\u5de5\u961f",
    "\u8f66\u68da \u62a5\u4ef7 \u6c42\u52a9",
    "\u906e\u9633\u68da \u5b89\u88c5 \u591a\u5c11\u94b1",
    "\u8f66\u68da \u7ef4\u4fee \u627e\u5e02\u6c11\u70ed\u7ebf",
]


class ForumHarvester:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def harvest(self) -> int:
        total = 0
        for query in FORUM_QUERIES:
            try:
                leads = self._search_baidu(query)
                count = self._save_leads(leads)
                total += count
                if count > 0:
                    logger.info(f"[Forum] {query}: +{count}")
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"[Forum] failed [{query}]: {e}")
        return total

    def _search_baidu(self, keyword: str) -> list:
        """Search Baidu for forum/Q&A posts"""
        results = []
        try:
            url = f"https://www.baidu.com/s?wd={quote(keyword)}&rn=10"
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
                    # Extract phone
                    phone = ""
                    pm = re.search(r"1[3-9]\d{9}", f"{title} {desc}")
                    if pm:
                        phone = pm.group()
                    # Classify source from URL
                    source = "\u95ee\u7b54\u5e73\u53f0"
                    if "tieba" in href:
                        source = "\u767e\u5ea6\u8d34\u5427"
                    elif "zhihu" in href:
                        source = "\u77e5\u4e4e"
                    elif "zhidao" in href:
                        source = "\u767e\u5ea6\u77e5\u9053"
                    elif "baijiahao" in href or "百家号" in desc:
                        source = "\u81ea\u5a92\u4f53"
                    name = title.split("-")[0].split("_")[0].strip()
                    if len(name) > 60:
                        name = name[:60]
                    if not name:
                        continue
                    results.append({
                        "name": name, "phone": phone,
                        "source": source,
                        "source_url": href,
                        "demand_desc": f"[问答] {title[:100]} | {desc[:100]}",
                        "product_interest": keyword.split()[0],
                        "customer_type": "\u95ee\u7b54\u54a8\u8be2",
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Baidu forum search failed: {e}")
        return results

    def _save_leads(self, leads: list) -> int:
        saved = 0
        for data in leads:
            try:
                if data.get("phone") and Lead.query.filter_by(phone=data["phone"]).first():
                    continue
                if data.get("name") and Lead.query.filter_by(name=data["name"]).first():
                    continue
                lead = Lead(**data)
                db.session.add(lead)
                saved += 1
            except Exception:
                pass
        if saved > 0:
            db.session.commit()
        return saved
