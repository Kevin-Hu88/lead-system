# -*- coding: utf-8 -*-
"""
政府公开数据采集器

数据源：
1. 武汉市自然资源和规划局（规划公示）
2. 武汉市住房和城市更新局（施工许可、竣工验收）
3. 各区住建局（项目备案）
4. 全国建筑市场监管公共服务平台（四库一平台）
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
from config.project_scenarios import PROJECT_SCENARIOS, match_scenario


class GovDataHarvester:
    """政府公开数据采集器"""

    # 目标政府网站（聚焦有膜结构/车棚/遮阳棚需求的项目）
    GOV_SITES = [
        # === 直接需求：项目本身就涉及车棚/遮阳棚/膜结构 ===
        {
            "name": "车棚/遮阳棚项目",
            "search_queries": [
                "武汉 车棚 工程 招标 公告",
                "武汉 遮阳棚 安装 采购 公告",
                "武汉 膜结构 工程 招标 公告",
                "湖北 车棚 建设 项目 公示",
                "武汉 雨棚 改造 工程 公告",
                "武汉 停车棚 新建 项目 公示",
                "湖北 充电桩 车棚 配套 采购",
                "武汉 非机动车棚 建设 公告",
            ],
        },
        # === 间接需求：新建小区/学校/医院必须配套车棚 ===
        {
            "name": "新建小区/住宅项目",
            "search_queries": [
                "武汉 新建小区 交付 配套 公示",
                "武汉 住宅项目 竣工验收 公示",
                "武汉 商品房 交付 配套设施",
                "武汉 老旧小区改造 停车 配套 公告",
                "武汉 棚户区改造 安置房 配套",
            ],
        },
        {
            "name": "学校/教育项目",
            "search_queries": [
                "武汉 新建学校 工程 招标 公告",
                "武汉 学校 改扩建 项目 公示",
                "湖北 幼儿园 新建 工程 公告",
                "武汉 高校 新校区 建设 公示",
                "武汉 中小学 改造 工程 招标",
            ],
        },
        {
            "name": "医院/医疗项目",
            "search_queries": [
                "武汉 新建医院 工程 招标 公告",
                "武汉 医院 改扩建 项目 公示",
                "湖北 卫生院 新建 工程 公告",
                "武汉 医疗设施 建设 项目",
            ],
        },
        # === 配套需求：商业/工业/物流项目需要车棚配套 ===
        {
            "name": "商业/综合体项目",
            "search_queries": [
                "武汉 商业综合体 新建 项目 公示",
                "武汉 购物中心 建设 工程 公告",
                "武汉 商业广场 配套 建设",
                "武汉 酒店 新建 工程 招标",
            ],
        },
        {
            "name": "工业/物流项目",
            "search_queries": [
                "武汉 产业园 新建 项目 公示",
                "武汉 工业园 建设 工程 公告",
                "湖北 物流园 新建 项目 公示",
                "武汉 厂房 建设 工程 招标",
            ],
        },
        # === 充电设施：充电桩必须配套车棚 ===
        {
            "name": "充电设施项目",
            "search_queries": [
                "武汉 充电站 新建 建设 公告",
                "武汉 充电桩 配套 设施 采购",
                "湖北 光伏车棚 项目 招标 公告",
                "武汉 光储充 一体化 项目 公示",
                "武汉 新能源 充电设施 建设",
            ],
        },
        # === 政府采购：公共设施车棚 ===
        {
            "name": "政府采购项目",
            "search_queries": [
                "site:ccgp.gov.cn 武汉 车棚 采购 公告",
                "site:ccgp.gov.cn 武汉 遮阳棚 采购 公告",
                "site:ccgp.gov.cn 湖北 膜结构 采购 公告",
                "site:ccgp.gov.cn 武汉 充电桩 车棚 采购",
                "site:ccgp.gov.cn 武汉 雨棚 改造 采购",
            ],
        },
    ]

    # Use unified project scenarios
    PROJECT_KEYWORDS = PROJECT_SCENARIOS

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.seen_urls = set()

    def harvest(self) -> int:
        """执行采集"""
        total = 0

        for site in self.GOV_SITES:
            try:
                leads = self._scrape_site(site)
                count = DataCleaner.clean_and_save_batch(leads)
                total += count
                if count > 0:
                    logger.info(f"[GovData] {site['name']}: +{count}")
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"[GovData] failed [{site['name']}]: {e}")

        return total

    def _scrape_site(self, site: dict) -> list:
        """通过Bing搜索抓取政府公告"""
        results = []
        from urllib.parse import quote

        for query in site.get("search_queries", []):
            try:
                # 使用Bing搜索
                search_url = f"https://cn.bing.com/search?q={quote(query)}&count=20"
                resp = self.session.get(search_url, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                # 解析搜索结果
                for item in soup.select(".b_algo"):
                    try:
                        title_el = item.select_one("h2 a")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        href = title_el.get("href", "")

                        # 提取描述 - 尝试多种选择器
                        desc = ""
                        for sel in [".b_caption p", ".b_algoSlug", ".b_lineclamp2", "p"]:
                            desc_el = item.select_one(sel)
                            if desc_el:
                                desc = desc_el.get_text(strip=True)
                                if desc:
                                    break

                        full_text = f"{title} {desc}"

                        if not title or len(title) < 5:
                            continue

                        # 检查是否包含项目关键词
                        project_info = self._match_project(full_text)
                        if not project_info:
                            continue

                        # 检查是否已抓取过
                        if href in self.seen_urls:
                            continue
                        self.seen_urls.add(href)

                        # 提取电话
                        phone = DataCleaner.extract_phone(full_text)

                        # 构建线索数据
                        lead = {
                            "name": title[:100],
                            "phone": phone,
                            "source": "gov_data",
                            "source_url": href,
                            "area": "武汉",
                            "customer_type": project_info["category"],
                            "product_interest": project_info["category"],
                            "demand_desc": f"[{project_info['level']}级项目] {project_info.get('scenario', '')} - {project_info.get('pitch', '')}",
                            "notes": f"来源: {site['name']}",
                        }

                        results.append(lead)

                    except Exception as e:
                        logger.debug(f"解析搜索结果失败: {e}")

                time.sleep(0.5)

            except Exception as e:
                logger.debug(f"搜索失败 [{site['name']}/{query}]: {e}")

        return results

    def _match_project(self, title: str) -> dict:
        """匹配项目类型"""
        title_lower = title.lower()
        for keyword, info in self.PROJECT_KEYWORDS.items():
            if keyword in title_lower:
                return info
        return None
