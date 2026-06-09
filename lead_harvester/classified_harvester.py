# -*- coding: utf-8 -*-
"""Classified harvester - 58同城 + Baidu search. Extracts individual listing URLs."""
import re, time, random, requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from loguru import logger
from fake_useragent import UserAgent
from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner

ua = UserAgent()

SEARCH_TERMS = [
    "\u8f66\u68da", "\u906e\u9633\u68da", "\u96e8\u68da", "\u505c\u8f66\u68da",
    "\u819c\u7ed3\u6784", "\u63a8\u62c9\u68da", "\u7535\u52a8\u68da", "\u4f38\u7f29\u68da",
]

CITY_CODES = {
    "\u6b66\u6c49": "wh", "\u9ec4\u77f3": "huangshi", "\u9102\u5dde": "ezhou",
    "\u5b5d\u611f": "xiaogan", "\u9ec4\u5188": "huanggang", "\u54b8\u5b81": "xianning",
    "\u8346\u5dde": "jingzhou", "\u8346\u95e8": "jingmen", "\u5b9c\u660c": "yichang",
    "\u8944\u9633": "xiangyang", "\u5341\u5830": "shiyan", "\u957f\u6c99": "cs",
}


class ClassifiedHarvester:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def harvest(self) -> int:
        total = 0

        # 1. 58同城 - extract individual listing URLs
        for term in SEARCH_TERMS[:4]:
            for city_name, city_code in list(CITY_CODES.items())[:3]:
                try:
                    leads = self._search_58(city_code, city_name, term)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[58] {city_name}/{term}: +{count}")
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(f"[58] failed [{city_name}/{term}]: {e}")

        # 2. Baidu search for classified listings
        for term in SEARCH_TERMS[:3]:
            try:
                leads = self._search_baidu_classified(term)
                count = self._save_leads(leads)
                total += count
                if count > 0:
                    logger.info(f"[Baidu-cls] {term}: +{count}")
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error(f"[Baidu-cls] failed [{term}]: {e}")

        return total

    def _search_58(self, city_code: str, city_name: str, keyword: str) -> list:
        """58同城 search - extract individual listing links with URLs."""
        results = []
        try:
            url = f"https://{city_code}.58.com/sou/"
            params = {"key": keyword}
            resp = self.session.get(url, params=params, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "lxml")

            # Find listing links: pattern //city.58.com/category/ID.shtml
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True)

                # Must be an actual listing URL
                if not re.search(r"58\.com/\w+/\d+x?\.shtml", href):
                    continue
                # Must have meaningful text
                if not text or len(text) < 6 or len(text) > 100:
                    continue
                # Skip navigation/footer junk
                if any(kw in text for kw in ["\u767b\u5f55", "\u6ce8\u518c", "\u53d1\u5e03", "\u9996\u9875", "\u5e2e\u52a9"]):
                    continue

                # Normalize URL
                if href.startswith("//"):
                    full_url = "https:" + href
                elif href.startswith("/"):
                    full_url = f"https://{city_code}.58.com" + href
                else:
                    full_url = href

                # Try to extract phone from the listing text or nearby elements
                parent = a.parent
                full_text = parent.get_text() if parent else text
                phone = ""
                pm = re.search(r"1[3-9]\d{9}", full_text)
                if pm:
                    phone = pm.group()

                results.append({
                    "name": text[:80],
                    "phone": phone,
                    "source": "58\u540c\u57ce",
                    "source_url": full_url.split("?")[0],  # Clean URL
                    "area": city_name,
                    "demand_desc": f"[58\u540c\u57ce] {text[:150]}",
                    "product_interest": keyword,
                    "customer_type": "\u5206\u7c7b\u4fe1\u606f",
                })

        except Exception as e:
            logger.debug(f"58 search failed: {e}")
        return results

    def _search_baidu_classified(self, keyword: str) -> list:
        """Baidu search for classified listings with URLs."""
        results = []
        try:
            query = f"{keyword} \u6c42\u8d2d \u8054\u7cfb\u7535\u8bdd"
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
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    href = title_el.get("href", "")
                    phone = ""
                    pm = re.search(r"1[3-9]\d{9}", f"{title} {desc}")
                    if pm:
                        phone = pm.group()
                    name = title.split("-")[0].split("_")[0].strip()
                    if len(name) > 60:
                        name = name[:60]
                    if not name:
                        continue
                    results.append({
                        "name": name, "phone": phone,
                        "source": "\u5206\u7c7b\u4fe1\u606f",
                        "source_url": href,
                        "demand_desc": f"[分类] {title[:100]} | {desc[:100]}",
                        "product_interest": keyword,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Baidu classified failed: {e}")
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
