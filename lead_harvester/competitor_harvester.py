# -*- coding: utf-8 -*-
"""
Competitor Harvester - Find competitor companies via Baidu search
Generates 企查查/天眼查 links for qualification verification
"""
import re, time, random, requests
from urllib.parse import quote
from loguru import logger
from config.competitors import COMPETITORS

SEARCH_KEYWORDS = [
    "{region}膜结构工程有限公司",
    "{region}车棚厂家",
    "{region}钢结构工程公司",
    "{region}光伏车棚公司",
    "{region}遮阳棚厂家",
]

# Generic terms that are NOT company names
BLACKLIST = ["厂家", "公司", "膜结构", "车棚",
             "遮阳棚", "钢结构", "光伏", "雨棚",
             "价格", "报价", "品牌", "排名", "推荐"]


class CompetitorHarvester:
    """Harvest competitor company data from search engines."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.seen_names = set()

    def harvest_region(self, region: str) -> list:
        """Search for competitors in a specific region."""
        results = []
        for kw_tpl in SEARCH_KEYWORDS:
            kw = kw_tpl.format(region=region)
            try:
                companies = self._search_baidu(kw, region)
                results.extend(companies)
                time.sleep(random.uniform(1.5, 3))
            except Exception as e:
                logger.debug(f"[Competitor] Search failed for '{kw}': {e}")

        # Dedup
        unique = []
        for c in results:
            if c["name"] not in self.seen_names:
                self.seen_names.add(c["name"])
                unique.append(c)

        logger.info(f"[Competitor] {region}: found {len(unique)} companies")
        return unique

    def harvest_all(self) -> dict:
        """Search all regions in COMPETITORS config."""
        all_results = {}
        for region in COMPETITORS:
            existing = [c["name"] for c in COMPETITORS.get(region, [])]
            self.seen_names.update(existing)
            results = self.harvest_region(region)
            if results:
                all_results[region] = results
            time.sleep(random.uniform(2, 4))
        return all_results

    def _search_baidu(self, keyword: str, region: str) -> list:
        """Search Baidu for company information."""
        results = []
        try:
            url = f"https://www.baidu.com/s?wd={quote(keyword)}&rn=10"
            r = self.session.get(url, timeout=15)
            if r.status_code != 200:
                return results

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "lxml")

            for item in soup.select(".result, .c-container"):
                try:
                    title_el = item.select_one("h3 a, .t a")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")

                    # Extract company name from title
                    name = self._extract_company_name(title)
                    if not name or len(name) < 6:
                        continue
                    if name in self.seen_names:
                        continue

                    # Skip generic/bad names
                    if self._is_generic(name):
                        continue

                    # Generate 企查查/天眼查 search URLs
                    qcc_url = f"https://www.qcc.com/search?key={quote(name)}"
                    ty_url = f"https://www.tianyancha.com/search?key={quote(name)}"

                    # Get description for context
                    desc_el = item.select_one(".c-abstract, .c-span-last")
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    full_text = title + " " + desc

                    strength = self._estimate_strength(full_text)
                    qualifications = self._extract_qualifications(full_text)
                    focus = self._extract_focus(full_text)

                    results.append({
                        "name": name,
                        "strength": strength,
                        "qualifications": qualifications,
                        "focus": focus,
                        "notes": title[:80],
                        "source_url": href,
                        "qcc_url": qcc_url,
                        "ty_url": ty_url,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[Competitor] Baidu search failed: {e}")
        return results

    def _extract_company_name(self, title: str) -> str:
        """Extract real company name from search result title."""
        # Priority 1: XX有限公司 (most specific)
        m = re.search(r"([一-鿿]{2,20}(?:有限公司|股份有限公司))", title)
        if m:
            return m.group(1)

        # Priority 2: XX技术有限公司, XX工程有限公司
        m = re.search(r"([一-鿿]{2,15}(?:技术|工程|科技|建设|建材|钢构)[一-鿿]{0,5}(?:有限公司|股份有限公司))", title)
        if m:
            return m.group(1)

        # Priority 3: XX集团
        m = re.search(r"([一-鿿]{2,15}(?:集团|集团公司))", title)
        if m:
            return m.group(1)

        return ""

    def _is_generic(self, name: str) -> str:
        """Check if name is a generic term, not a real company."""
        # If the name is ONLY generic terms, reject it
        clean = name
        for bl in BLACKLIST:
            clean = clean.replace(bl, "")
        # If nothing meaningful remains, it is generic
        if len(clean.strip()) < 2:
            return True
        # If name starts with generic term and has no specific prefix
        for bl in ["公司", "厂家", "推荐", "价格", "报价"]:
            if name.startswith(bl):
                return True
        return False

    def _estimate_strength(self, text: str) -> str:
        """Estimate competitor strength from context."""
        s_kw = ["一级", "甲级", "特级", "上市", "集团", "国家级", "大型", "双一级"]
        a_kw = ["二级", "乙级", "中型", "多年", "专业", "设计资质"]
        b_kw = ["三级", "丙级", "小型", "新成立"]
        for kw in s_kw:
            if kw in text: return "S"
        for kw in a_kw:
            if kw in text: return "A"
        for kw in b_kw:
            if kw in text: return "B"
        return "B"

    def _extract_qualifications(self, text: str) -> list:
        """Extract qualification mentions."""
        quals = []
        patterns = [
            r"(钢结构专业[一二三]级)",
            r"(建筑工程总承包[一二三]级)",
            r"([一-鿿]+(?:设计|施工)资质)",
            r"(双[一二]级资质)",
            r"(ISO\d{4,6})",
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            quals.extend(matches)
        return list(set(quals))[:5]

    def _extract_focus(self, text: str) -> str:
        """Extract business focus."""
        focuses = []
        kw_map = {
            "膜结构": "膜结构",
            "车棚": "车棚",
            "遮阳棚": "遮阳棚",
            "光伏": "光伏",
            "钢结构": "钢结构",
            "雨棚": "雨棚",
            "气膜": "气膜",
        }
        for kw, label in kw_map.items():
            if kw in text and label not in focuses:
                focuses.append(label)
        return "/".join(focuses[:3]) if focuses else "建筑工程"
