# -*- coding: utf-8 -*-
"""
企业微信发送模块
通过企业微信API自动发送消息
"""
import json
import time
import requests
from datetime import datetime
from loguru import logger

from config import settings
from crm.models import db, Lead
from crm.database import record_message


class WechatSender:
    """企业微信消息发送器"""

    def __init__(self):
        self.enabled = settings.WECHAT_WORK_ENABLED
        self.daily_limit = settings.DAILY_WECHAT_LIMIT
        self.today_sent = 0
        self._access_token = None
        self._token_expire = 0

    def _get_access_token(self) -> str:
        """获取企业微信access_token"""
        if self._access_token and time.time() < self._token_expire:
            return self._access_token

        try:
            url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            params = {
                "corpid": settings.WECHAT_CORP_ID,
                "corpsecret": settings.WECHAT_CORP_SECRET,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                self._access_token = data["access_token"]
                self._token_expire = time.time() + data.get("expires_in", 7200) - 300
                return self._access_token
            else:
                logger.error(f"获取access_token失败: {data}")
        except Exception as e:
            logger.error(f"获取access_token异常: {e}")
        return None

    def send_to_lead(self, lead: Lead, template_name: str = "初次触达") -> bool:
        """给线索发送企业微信消息"""
        if not self.enabled:
            logger.info(f"[微信-模拟] 发送给 {lead.name}: {template_name}")
            record_message(
                lead_id=lead.id,
                channel="wechat",
                direction="out",
                content=f"[模拟微信] {template_name}",
                template_name=template_name,
                status="sent",
            )
            return True

        if self.today_sent >= self.daily_limit:
            logger.warning(f"今日微信发送已达上限 ({self.daily_limit})")
            return False

        try:
            content = self._render_template(template_name, lead)
            success = self._send_message(lead.wechat, content)

            if success:
                self.today_sent += 1
                record_message(
                    lead_id=lead.id,
                    channel="wechat",
                    direction="out",
                    content=content,
                    template_name=template_name,
                    status="sent",
                )
                lead.status = "contacted"
                lead.contact_count += 1
                lead.last_contact_at = datetime.now()
                db.session.commit()
                logger.info(f"[微信] 已发送给 {lead.name}")
                return True
            return False
        except Exception as e:
            logger.error(f"微信发送失败 [{lead.name}]: {e}")
            return False

    def _render_template(self, template_name: str, lead: Lead) -> str:
        """渲染消息模板"""
        template = settings.WECHAT_TEMPLATES.get(template_name, "")
        return template.format(
            company=settings.BUSINESS_NAME,
            phone=settings.BUSINESS_PHONE,
        )

    def _send_message(self, userid: str, content: str) -> bool:
        """通过企业微信API发送消息"""
        try:
            token = self._get_access_token()
            if not token:
                return False
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
            body = {
                "touser": userid,
                "msgtype": "text",
                "agentid": int(settings.WECHAT_AGENT_ID),
                "text": {"content": content},
            }
            resp = requests.post(url, json=body, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                return True
            else:
                logger.error(f"企业微信发送失败: {data}")
                return False
        except Exception as e:
            logger.error(f"企业微信API异常: {e}")
            return False
