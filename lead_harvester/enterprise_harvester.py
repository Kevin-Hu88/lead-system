# -*- coding: utf-8 -*-
"""
企业信息采集器 - 从搜索引擎采集目标企业联系方式

目标客户类型：
  - 物业公司：小区车棚的决策方
  - 工厂/厂区：员工停车棚需求
  - 4S店/汽车经销商：门头车棚升级
  - 学校/医院：公共设施车棚

采集策略：
  1. 百度搜索"城市+行业+电话/联系方式"
  2. 从搜索结果中提取企业名、电话、地址
  3. 去重后入库

注意：这是免费方案，数据质量中等。
  如需更高质量，接入天眼查/企查查 API（付费）。
"""
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from fake_useragent import UserAgent

from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner

ua = UserAgent()

# 目标客户类型：(行业关键词, 客户类型标签, 搜索模板)
TARGET_TYPES = [
    # 物业公司 - 小区车棚的真正决策方
    ("物业公司", "物业", "{area} 物业公司 电话"),
    ("物业管理", "物业", "{area} 物业管理公司 联系电话"),
    # 工厂 - 员工停车棚
    ("工厂", "工厂", "{area} 工厂 联系电话"),
    ("生产企业", "工厂", "{area} 生产企业 电话"),
    # 4S店 - 门头车棚
    ("4S店", "4S店", "{area} 4S店 电话"),
    ("汽车销售", "4S店", "{area} 汽车销售公司 联系方式"),
    # 学校 - 公共设施车棚
    ("学校", "学校", "{area} 学校 总务处 电话"),
    # 医院 - 公共设施车棚
    ("医院", "医院", "{area} 医院 后勤部 电话"),
]


class EnterpriseHarvester:
    """从搜索引擎采集目标企业联系方式"""

    def __init__(self):
        self.session = requests.Session()
        # 只搜本地+周边，不搜外省
        self.areas = self._get_target_areas()

    def _get_target_areas(self) -> list:
        """获取目标区域（只搜武汉各区，不搜外省）"""
        return [a for a in settings.TARGET_AREAS if a.startswith("武汉")]

    def harvest(self) -> int:
        """执行采集"""
        total = 0
        for area in self.areas:
            for industry, customer_type, template in TARGET_TYPES:
                query = template.format(area=area)
                try:
                    leads = self._search_baidu(query, area, customer_type)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[{area}] {industry}: +{count}")
                    time.sleep(random.uniform(
                        settings.REQUEST_DELAY_MIN,
                        settings.REQUEST_DELAY_MAX
                    ))
                except Exception as e:
                    logger.error(f"采集失败 [{area}/{industry}]: {e}")
        return total

    def _search_baidu(self, keyword: str, area: str, customer_type: str) -> list:
        """百度搜索提取企业信息"""
        results = []
        try:
            url = f"https://www.baidu.com/s?wd={quote(keyword)}&rn=10"
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zi=q=0.9",
            }
            resp = self.session.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select(".result, .c-container"):
                try:
                    title_el = item.select_one("h3 a, .t a")
                    desc_el = item.select_one(".c-abstract, .c-span-last, .content-right_8Zs40")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    href = title_el.get("href", "")
                    full_text = f"{title} {desc}"

                    # 提取电话（手机或座机）
                    phone = self._extract_phone(full_text)

                    # 提取企业名称（标题的第一部分）
                    name = self._extract_company_name(title)
                    if not name or len(name) < 3:
                        continue

                    # 跳过竞争对手（搜"车棚"出来的同行）
                    if self._is_competitor(name, full_text):
                        continue

                    # 只保留有电话的结果
                    if not phone:
                        continue

                    results.append({
                        "name": name[:100],
                        "phone": phone,
                        "source": "enterprise_search",
                        "source_url": href,
                        "area": area,
                        "customer_type": customer_type,
                        "demand_desc": f"[企业搜索] {title[:100]} | {desc[:100]}",
                        "product_interest": customer_type,
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"百度搜索失败: {e}")
        return results

    def _extract_phone(self, text: str) -> str:
        """从文本中提取电话号码"""
        if not text:
            return ""
        # 手机号
        mobile = re.search(r"1[3-9]\d{9}", text)
        if mobile:
            return mobile.group()
        # 座机号
        landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
        if landline:
            return landline.group()
        return ""

    def _extract_company_name(self, title: str) -> str:
        """从标题中提取企业名称"""
        # 去掉常见后缀
        for sep in ["-", "_", "—", "|", "｜", " "]:
            if sep in title:
                title = title.split(sep)[0]
        # 去掉多余描述
        for kw in ["电话", "联系方式", "地址", "官网", "首页", "怎么样", "好不好"]:
            if kw in title:
                title = title.split(kw)[0]
        return title.strip()

    def _is_competitor(self, name: str, text: str) -> bool:
        """检测是否为竞争对手（同行厂家）"""
        competitor_kws = [
            "膜结构公司", "膜结构厂家", "车棚厂家", "遮阳棚厂家",
            "雨棚厂家", "张拉膜", "膜结构工程公司",
        ]
        for kw in competitor_kws:
            if kw in name or kw in text[:50]:
                return True
        return False

    def _save_leads(self, leads: list) -> int:
        """保存线索，去重"""
        saved = 0
        for data in leads:
            try:
                # 电话去重
                if data.get("phone") and Lead.query.filter_by(phone=data["phone"]).first():
                    continue
                # 名称去重
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
