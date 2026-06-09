# -*- coding: utf-8 -*-
"""
短信发送模块
支持阿里云短信/腾讯云短信/模拟模式
"""
import time
import hashlib
import hmac
import base64
import json
from datetime import datetime
from loguru import logger

from config import settings
from crm.models import db, Lead, Message
from crm.database import record_message


class SMSSender:
    """短信发送器"""

    def __init__(self):
        self.enabled = settings.SMS_ENABLED
        self.daily_limit = settings.DAILY_SMS_LIMIT
        self.today_sent = 0

    def send_to_lead(self, lead: Lead, template_name: str = "初次触达") -> bool:
        """给线索发送短信"""
        if not self.enabled:
            logger.info(f"[SMS-模拟] 发送给 {lead.name} ({lead.phone}): {template_name}")
            record_message(
                lead_id=lead.id,
                channel="sms",
                direction="out",
                content=f"[模拟短信] {template_name}",
                template_name=template_name,
                status="sent",
            )
            return True

        if not lead.phone:
            logger.warning(f"线索 {lead.name} 无电话号码，跳过")
            return False

        if self.today_sent >= self.daily_limit:
            logger.warning(f"今日短信发送已达上限 ({self.daily_limit})")
            return False

        try:
            content = self._render_template(template_name, lead)
            success = self._send_sms(lead.phone, content)

            if success:
                self.today_sent += 1
                record_message(
                    lead_id=lead.id,
                    channel="sms",
                    direction="out",
                    content=content,
                    template_name=template_name,
                    status="sent",
                )
                lead.status = "contacted"
                lead.contact_count += 1
                lead.last_contact_at = datetime.now()
                db.session.commit()
                logger.info(f"[SMS] 已发送给 {lead.name} ({lead.phone})")
                return True
            else:
                record_message(
                    lead_id=lead.id,
                    channel="sms",
                    direction="out",
                    content=content,
                    template_name=template_name,
                    status="failed",
                )
                return False
        except Exception as e:
            logger.error(f"短信发送失败 [{lead.name}]: {e}")
            return False

    def _render_template(self, template_name: str, lead: Lead) -> str:
        """渲染消息模板"""
        template = settings.SMS_TEMPLATES.get(template_name, settings.SMS_TEMPLATES["初次触达"])
        return template.format(
            company=settings.BUSINESS_NAME,
            phone=settings.BUSINESS_PHONE,
            keyword=lead.product_interest or "车棚/遮阳棚",
            offer="免费测量设计",
            price="280",
            discount="20%",
            quota="50",
        )

    def _send_sms(self, phone: str, content: str) -> bool:
        """调用短信API发送（阿里云短信示例）"""
        try:
            # 阿里云短信API调用
            # 实际使用时需要安装 alibabacloud-dysmsapi
            # from alibabacloud_dysmsapi20170525.client import Client
            # 这里用模拟实现，接入时替换为真实API
            logger.info(f"[SMS-API] 发送到 {phone}: {content[:30]}...")
            return True
        except Exception as e:
            logger.error(f"SMS API调用失败: {e}")
            return False
