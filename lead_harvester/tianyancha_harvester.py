# -*- coding: utf-8 -*-
"""
天眼查/企查查 API 采集器

功能：
- 通过企业名称/关键词搜索目标客户
- 获取工商信息、法人电话、经营范围
- 支持天眼查和企查查两个数据源

使用前需要：
1. 注册天眼查/企查查开发者账号
2. 获取API Key
3. 在config/settings.py中配置
"""
import re
import time
import random
import requests
from loguru import logger
from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner


class TianyanchaHarvester:
    """天眼查/企查查API采集器"""

    # 目标客户类型：(行业关键词, 客户类型标签, 经营范围关键词)
    TARGET_TYPES = [
        # 物业公司 - 小区车棚的真正决策方
        ("物业管理", "物业", ["物业管理", "物业服务", "社区服务"]),
        ("物业公司", "物业", ["物业管理", "物业服务"]),
        # 工厂 - 员工停车棚
        ("工厂", "工厂", ["生产", "制造", "加工"]),
        ("生产企业", "工厂", ["生产", "制造"]),
        # 4S店 - 门头车棚
        ("4S店", "4S店", ["汽车销售", "汽车维修", "汽车服务"]),
        ("汽车销售", "4S店", ["汽车销售", "汽车零售"]),
        # 学校 - 公共设施车棚
        ("学校", "学校", ["教育", "培训", "学校"]),
        ("幼儿园", "学校", ["学前教育", "幼儿园"]),
        # 医院 - 公共设施车棚
        ("医院", "医院", ["医疗", "医院", "卫生"]),
        # 商业 - 商场车棚
        ("商场", "商业", ["商业", "零售", "购物中心"]),
        ("购物中心", "商业", ["商业", "零售"]),
        # 新能源 - 充电桩车棚
        ("新能源", "新能源", ["新能源", "充电", "光伏"]),
        ("充电站", "新能源", ["充电", "新能源"]),
        # 酒店 - 酒店车棚
        ("酒店", "酒店", ["酒店", "住宿", "宾馆"]),
    ]

    def __init__(self):
        self.tianyancha_key = getattr(settings, 'TIANYANCHA_API_KEY', '')
        self.qichacha_key = getattr(settings, 'QICHACHA_API_KEY', '')
        self.areas = [a for a in settings.TARGET_AREAS if a.startswith("武汉")]

    def harvest(self) -> int:
        """执行采集"""
        if not self.tianyancha_key and not self.qichacha_key:
            logger.warning("天眼查/企查查API Key未配置，跳过企业信息采集")
            return 0

        total = 0
        for area in self.areas:
            for industry, customer_type, scope_keywords in self.TARGET_TYPES:
                try:
                    leads = self._search(area, industry, customer_type, scope_keywords)
                    count = DataCleaner.clean_and_save_batch(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[企查查] {area}/{industry}: +{count}")
                    time.sleep(random.uniform(1, 3))
                except Exception as e:
                    logger.error(f"[企查查] failed [{area}/{industry}]: {e}")

        return total

    def _search(self, area: str, industry: str, customer_type: str, scope_keywords: list) -> list:
        """搜索企业信息"""
        results = []

        # 优先使用天眼查
        if self.tianyancha_key:
            results = self._search_tianyancha(area, industry, customer_type, scope_keywords)

        # 如果天眼查没有结果，使用企查查
        if not results and self.qichacha_key:
            results = self._search_qichacha(area, industry, customer_type, scope_keywords)

        return results

    def _search_tianyancha(self, area: str, industry: str, customer_type: str, scope_keywords: list) -> list:
        """天眼查API搜索"""
        results = []
        try:
            url = "https://api.tianyancha.com/services/open/ic/baseinfo/normal"
            headers = {
                "Authorization": self.tianyancha_key,
                "Content-Type": "application/json"
            }

            for keyword in scope_keywords[:2]:  # 只搜前2个关键词
                params = {
                    "keyword": f"{area}{keyword}",
                    "pageNum": 1,
                    "pageSize": 10,
                }

                resp = requests.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if data.get("error_code") != 0:
                    continue

                items = data.get("result", {}).get("items", [])
                for item in items:
                    lead = self._parse_tianyancha(item, area, customer_type)
                    if lead:
                        results.append(lead)

                time.sleep(0.5)

        except Exception as e:
            logger.debug(f"天眼查搜索失败: {e}")

        return results

    def _parse_tianyancha(self, item: dict, area: str, customer_type: str) -> dict:
        """解析天眼查返回数据"""
        try:
            name = item.get("name", "").strip()
            if not name:
                return None

            # 提取电话
            phone = item.get("phone", "")
            if not phone:
                phone = DataCleaner.extract_phone(item.get("contactInfo", ""))

            # 提取地址
            address = item.get("regLocation", "") or item.get("base", "")

            # 提取经营范围
            scope = item.get("businessScope", "")

            # 提取法人
            legal_person = item.get("legalPersonName", "")

            return {
                "name": name,
                "phone": phone,
                "address": address[:300] if address else "",
                "source": "tianyancha",
                "area": DataCleaner.normalize_area(area),
                "customer_type": customer_type,
                "product_interest": customer_type,
                "demand_desc": f"经营范围: {scope[:200]}" if scope else "",
                "contact_person": legal_person,
                "notes": f"法人: {legal_person}" if legal_person else "",
            }
        except Exception as e:
            logger.debug(f"解析天眼查数据失败: {e}")
            return None

    def _search_qichacha(self, area: str, industry: str, customer_type: str, scope_keywords: list) -> list:
        """企查查API搜索"""
        results = []
        try:
            url = "https://api.qichacha.com/EnterpriseSearch/Search"
            headers = {
                "Token": self.qichacha_key,
                "Content-Type": "application/json"
            }

            for keyword in scope_keywords[:2]:
                params = {
                    "keyWord": f"{area}{keyword}",
                    "pageIndex": 1,
                    "pageSize": 10,
                }

                resp = requests.get(url, headers=headers, params=params, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if data.get("Status") != "200":
                    continue

                items = data.get("Result", {}).get("List", [])
                for item in items:
                    lead = self._parse_qichacha(item, area, customer_type)
                    if lead:
                        results.append(lead)

                time.sleep(0.5)

        except Exception as e:
            logger.debug(f"企查查搜索失败: {e}")

        return results

    def _parse_qichacha(self, item: dict, area: str, customer_type: str) -> dict:
        """解析企查查返回数据"""
        try:
            name = item.get("Name", "").strip()
            if not name:
                return None

            phone = item.get("Phone", "")
            if not phone:
                phone = DataCleaner.extract_phone(item.get("ContactInfo", ""))

            address = item.get("Address", "")
            scope = item.get("Scope", "")
            legal_person = item.get("OperName", "")

            return {
                "name": name,
                "phone": phone,
                "address": address[:300] if address else "",
                "source": "qichacha",
                "area": DataCleaner.normalize_area(area),
                "customer_type": customer_type,
                "product_interest": customer_type,
                "demand_desc": f"经营范围: {scope[:200]}" if scope else "",
                "contact_person": legal_person,
                "notes": f"法人: {legal_person}" if legal_person else "",
            }
        except Exception as e:
            logger.debug(f"解析企查查数据失败: {e}")
            return None
