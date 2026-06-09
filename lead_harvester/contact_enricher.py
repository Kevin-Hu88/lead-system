# -*- coding: utf-8 -*-
"""
联系人信息补充模块

从多个渠道补充联系人姓名：
1. 企业名称 → 搜索法人/负责人
2. 电话号码 → 反查关联企业
3. 项目名称 → 搜索建设单位联系人
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from loguru import logger
from config import settings
from crm.models import db, Lead


class ContactEnricher:
    """联系人信息补充器"""

    # 联系人职位关键词
    POSITION_KEYWORDS = [
        "法人", "法定代表人", "负责人", "总经理", "董事长",
        "项目经理", "基建处", "总务处", "后勤部", "采购部",
        "物业管理", "开发商", "建设单位",
    ]

    @staticmethod
    def enrich_from_company_name(company_name: str) -> dict:
        """
        从企业名称搜索联系人信息

        返回：
        - contact_person: 联系人姓名
        - position: 职位
        - phone: 电话（可能不同）
        """
        if not company_name:
            return None

        result = {
            "contact_person": None,
            "position": None,
            "phone": None,
        }

        try:
            # 搜索"企业名称 + 法人"
            query = f"{company_name} 法人代表"
            search_results = ContactEnricher._search_baidu(query)

            # 从搜索结果中提取姓名
            for text in search_results:
                # 匹配"法人：张三"或"法人代表 张三"
                patterns = [
                    r'法人[：:]\s*([^\s,，。.]{2,4})',
                    r'法定代表人[：:]\s*([^\s,，。.]{2,4})',
                    r'负责人[：:]\s*([^\s,，。.]{2,4})',
                    r'总经理[：:]\s*([^\s,，。.]{2,4})',
                ]

                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        name = match.group(1).strip()
                        # 验证是否是有效姓名（2-4个中文字符）
                        if re.match(r'^[\u4e00-\u9fff]{2,4}$', name):
                            result["contact_person"] = name
                            result["position"] = "法人"
                            return result

        except Exception as e:
            logger.debug(f"Enrich contact from company name failed: {e}")

        return result

    @staticmethod
    def enrich_from_project_name(project_name: str) -> dict:
        """
        从项目名称搜索建设单位联系人

        适用于：商品房项目、在建工程等
        """
        if not project_name:
            return None

        result = {
            "contact_person": None,
            "position": None,
            "company": None,
        }

        try:
            # 搜索"项目名称 + 建设单位"
            query = f"{project_name} 建设单位 联系人"
            search_results = ContactEnricher._search_baidu(query)

            for text in search_results:
                # 匹配"建设单位：XXX公司"
                company_match = re.search(r'建设单位[：:]\s*([^\s,，。.]+公司)', text)
                if company_match:
                    result["company"] = company_match.group(1)

                # 匹配联系人
                contact_match = re.search(r'联系人[：:]\s*([^\s,，。.]{2,4})', text)
                if contact_match:
                    name = contact_match.group(1).strip()
                    if re.match(r'^[\u4e00-\u9fff]{2,4}$', name):
                        result["contact_person"] = name
                        result["position"] = "联系人"
                        return result

        except Exception as e:
            logger.debug(f"Enrich contact from project name failed: {e}")

        return result

    @staticmethod
    def enrich_from_phone(phone: str) -> dict:
        """
        从电话号码反查联系人

        使用微信/支付宝等平台的号码关联信息
        """
        if not phone:
            return None

        result = {
            "contact_person": None,
            "company": None,
        }

        # 这里可以接入号码反查API
        # 暂时返回None

        return result

    @staticmethod
    def enrich_lead(lead_id: int) -> bool:
        """
        补充单条线索的联系人信息

        按优先级尝试：
        1. 从企业名称搜索
        2. 从项目名称搜索
        3. 从电话号码反查
        """
        lead = Lead.query.get(lead_id)
        if not lead:
            return False

        # 如果已经有联系人，跳过
        if lead.contact_person:
            return True

        # 1. 从企业名称搜索
        if lead.name:
            result = ContactEnricher.enrich_from_company_name(lead.name)
            if result and result.get("contact_person"):
                lead.contact_person = result["contact_person"]
                if result.get("position"):
                    lead.notes = (lead.notes or "") + f"\n职位: {result['position']}"
                db.session.commit()
                logger.info(f"Enriched contact for {lead.name}: {result['contact_person']}")
                return True

        # 2. 从项目名称搜索（适用于商品房/在建工程）
        if lead.source in ["商品房项目", "在建工程", "gov_data"]:
            result = ContactEnricher.enrich_from_project_name(lead.name)
            if result and result.get("contact_person"):
                lead.contact_person = result["contact_person"]
                db.session.commit()
                logger.info(f"Enriched contact for project {lead.name}: {result['contact_person']}")
                return True

        return False

    @staticmethod
    def batch_enrich(limit: int = 100) -> dict:
        """
        批量补充联系人信息

        只处理没有联系人的线索
        """
        leads = Lead.query.filter(
            Lead.phone.isnot(None),
            Lead.phone != '',
            (Lead.contact_person.is_(None) | (Lead.contact_person == '')),
        ).limit(limit).all()

        stats = {
            "total": len(leads),
            "enriched": 0,
            "failed": 0,
        }

        for lead in leads:
            try:
                success = ContactEnricher.enrich_lead(lead.id)
                if success:
                    stats["enriched"] += 1
                else:
                    stats["failed"] += 1
                time.sleep(1)  # 避免请求过快
            except Exception as e:
                stats["failed"] += 1
                logger.debug(f"Enrich failed for {lead.name}: {e}")

        return stats

    @staticmethod
    def _search_baidu(query: str, max_results: int = 5) -> list:
        """
        百度搜索

        返回搜索结果文本列表
        """
        results = []
        try:
            url = f"https://www.baidu.com/s?wd={quote(query)}&rn=10"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "lxml")

            # 提取搜索结果文本
            for item in soup.select(".result, .c-container"):
                text = item.get_text(strip=True)
                if text:
                    results.append(text)
                    if len(results) >= max_results:
                        break

        except Exception as e:
            logger.debug(f"Baidu search failed: {e}")

        return results
