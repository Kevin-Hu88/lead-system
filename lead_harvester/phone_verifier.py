# -*- coding: utf-8 -*-
"""
电话号码验证与联系人补充模块

功能：
1. 手机号格式验证（更严格）
2. 号码状态检测（空号/停机/在网）
3. 联系人姓名补充（从企业信息中提取）
4. 拨打前质量评分
"""
import re
import time
import requests
from loguru import logger
from config import settings
from crm.models import db, Lead


class PhoneVerifier:
    """电话号码验证器"""

    # 有效手机号段（2024年最新）
    VALID_MOBILE_PREFIXES = [
        '130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
        '145', '146', '147', '148', '149',
        '150', '151', '152', '153', '155', '156', '157', '158', '159',
        '162', '165', '166', '167',
        '170', '171', '172', '173', '175', '176', '177', '178',
        '180', '181', '182', '183', '184', '185', '186', '187', '188', '189',
        '190', '191', '192', '193', '195', '196', '197', '198', '199',
    ]

    # 虚拟运营商号段（可能不是真实用户）
    VIRTUAL_PREFIXES = ['170', '171', '162', '165', '167']

    # 常见无效号码模式
    INVALID_PATTERNS = [
        r'^1[3-9]\d{9}$',  # 标准格式
    ]

    # 号码状态检测API（需要配置）
    # 推荐服务：
    # 1. 阿里云号码检测：https://help.aliyun.com/document_detail/139611.html
    # 2. 腾讯云号码检测：https://cloud.tencent.com/document/product/665
    # 3. 聚合数据：https://www.juhe.cn/docs/api/id/104

    @staticmethod
    def validate_phone_format(phone: str) -> dict:
        """验证手机号格式，返回详细信息"""
        if not phone:
            return {"valid": False, "reason": "empty", "score": 0}

        phone = phone.strip().replace("-", "").replace(" ", "")

        # 手机号验证
        if re.match(r'^1[3-9]\d{9}$', phone):
            prefix = phone[:3]
            is_virtual = prefix in PhoneVerifier.VIRTUAL_PREFIXES
            return {
                "valid": True,
                "type": "mobile",
                "prefix": prefix,
                "is_virtual": is_virtual,
                "score": 60 if is_virtual else 80,
            }

        # 座机号验证
        if re.match(r'^0\d{2,3}[-]?\d{7,8}$', phone):
            return {
                "valid": True,
                "type": "landline",
                "score": 40,  # 座机通常是前台/总机
            }

        # 400电话
        if re.match(r'^400[-]?\d{3}[-]?\d{4}$', phone):
            return {
                "valid": True,
                "type": "400",
                "score": 20,  # 400电话是客服热线
            }

        return {"valid": False, "reason": "invalid_format", "score": 0}

    @staticmethod
    def check_phone_status(phone: str) -> dict:
        """
        检测号码状态（空号/停机/在网）

        需要配置API Key：
        - settings.PHONE_CHECK_API_KEY
        - settings.PHONE_CHECK_API_URL

        返回：
        - status: active/inactive/unknown
        - carrier: 运营商
        - province: 归属省份
        - city: 归属城市
        """
        # 默认返回unknown（需要配置API才能检测）
        result = {
            "status": "unknown",
            "carrier": "",
            "province": "",
            "city": "",
        }

        api_key = getattr(settings, 'PHONE_CHECK_API_KEY', '')
        api_url = getattr(settings, 'PHONE_CHECK_API_URL', '')

        if not api_key or not api_url:
            return result

        try:
            resp = requests.get(api_url, params={
                "phone": phone,
                "key": api_key,
            }, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                # 根据不同API调整解析逻辑
                result["status"] = data.get("status", "unknown")
                result["carrier"] = data.get("carrier", "")
                result["province"] = data.get("province", "")
                result["city"] = data.get("city", "")
        except Exception as e:
            logger.debug(f"Phone check failed: {e}")

        return result

    @staticmethod
    def calculate_phone_score(phone: str, contact_person: str = None, source: str = "") -> int:
        """
        计算电话质量评分（0-100）

        评分维度：
        - 格式验证：20分
        - 号码类型：30分
        - 号码状态：30分
        - 联系人信息：20分
        """
        score = 0

        # 1. 格式验证（20分）
        format_result = PhoneVerifier.validate_phone_format(phone)
        if not format_result["valid"]:
            return 0
        score += 20

        # 2. 号码类型（30分）
        if format_result["type"] == "mobile":
            if format_result.get("is_virtual"):
                score += 15  # 虚拟运营商扣分
            else:
                score += 30  # 正常手机号
        elif format_result["type"] == "landline":
            score += 10  # 座机通常是总机
        elif format_result["type"] == "400":
            score += 5   # 400是客服

        # 3. 号码状态（30分）
        status_result = PhoneVerifier.check_phone_status(phone)
        if status_result["status"] == "active":
            score += 30
        elif status_result["status"] == "inactive":
            return 0  # 空号/停机直接0分
        else:
            score += 15  # 未知状态

        # 4. 联系人信息（20分）
        if contact_person:
            score += 20
        elif source in ["商品房项目", "招标平台", "import"]:
            score += 10  # 这些来源通常有联系人

        return min(100, score)

    @staticmethod
    def enrich_contact_info(lead_id: int) -> bool:
        """
        补充联系人信息

        从以下来源补充：
        1. 企业名称 → 搜索法人/负责人
        2. 电话号码 → 搜索关联企业
        """
        lead = Lead.query.get(lead_id)
        if not lead:
            return False

        # 如果已经有联系人，跳过
        if lead.contact_person:
            return True

        # 尝试从企业名称搜索联系人
        if lead.name:
            contact = PhoneVerifier._search_contact_by_company(lead.name)
            if contact:
                lead.contact_person = contact
                db.session.commit()
                return True

        return False

    @staticmethod
    def _search_contact_by_company(company_name: str) -> str:
        """
        从企业名称搜索联系人

        使用免费方案：
        1. 百度搜索"企业名称 + 法人"
        2. 从搜索结果中提取姓名
        """
        try:
            # 搜索"企业名称 法人/负责人"
            queries = [
                f"{company_name} 法人",
                f"{company_name} 负责人",
                f"{company_name} 总经理",
            ]

            for query in queries[:1]:  # 只搜一次，避免频繁请求
                # 这里可以调用搜索API
                # 暂时返回None，需要配置搜索API
                pass

        except Exception as e:
            logger.debug(f"Search contact failed: {e}")

        return None

    @staticmethod
    def filter_callable_leads(min_score: int = 50) -> list:
        """
        筛选可拨打的线索

        条件：
        - 电话格式有效
        - 电话质量评分 >= min_score
        - 未退订
        - 未沉睡
        """
        leads = Lead.query.filter(
            Lead.phone.isnot(None),
            Lead.phone != '',
            Lead.is_opt_out == False,
            Lead.sleep_status == 0,
        ).all()

        callable_leads = []
        for lead in leads:
            score = PhoneVerifier.calculate_phone_score(
                lead.phone,
                lead.contact_person,
                lead.source
            )
            if score >= min_score:
                callable_leads.append({
                    "lead": lead,
                    "phone_score": score,
                    "has_contact": bool(lead.contact_person),
                })

        # 按评分排序
        callable_leads.sort(key=lambda x: x["phone_score"], reverse=True)
        return callable_leads

    @staticmethod
    def batch_verify_phones(lead_ids: list = None) -> dict:
        """
        批量验证电话号码

        返回统计信息
        """
        if lead_ids:
            leads = Lead.query.filter(Lead.id.in_(lead_ids)).all()
        else:
            leads = Lead.query.filter(
                Lead.phone.isnot(None),
                Lead.phone != '',
            ).all()

        stats = {
            "total": len(leads),
            "valid": 0,
            "invalid": 0,
            "mobile": 0,
            "landline": 0,
            "virtual": 0,
            "with_contact": 0,
            "high_quality": 0,
        }

        for lead in leads:
            format_result = PhoneVerifier.validate_phone_format(lead.phone)
            if not format_result["valid"]:
                stats["invalid"] += 1
                continue

            stats["valid"] += 1
            if format_result["type"] == "mobile":
                stats["mobile"] += 1
                if format_result.get("is_virtual"):
                    stats["virtual"] += 1
            elif format_result["type"] == "landline":
                stats["landline"] += 1

            if lead.contact_person:
                stats["with_contact"] += 1

            score = PhoneVerifier.calculate_phone_score(
                lead.phone,
                lead.contact_person,
                lead.source
            )
            if score >= 70:
                stats["high_quality"] += 1

        return stats
