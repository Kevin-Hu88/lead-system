# -*- coding: utf-8 -*-
"""
自动触达调度器 - 统一管理所有触达渠道
"""
from datetime import datetime, timedelta
from loguru import logger

from config import settings
from crm.models import db, Lead, TaskLog
from crm.database import get_leads_for_contact, get_leads_for_followup

from auto_outreach.sms_sender import SMSSender
from auto_outreach.wechat_sender import WechatSender
from auto_outreach.email_sender import EmailSender


class OutreachManager:
    """触达管理器"""

    def __init__(self):
        self.sms = SMSSender()
        self.wechat = WechatSender()
        self.email = EmailSender()

    def run_auto_contact(self, app):
        """自动联系新线索"""
        with app.app_context():
            log = TaskLog(task_name="自动触达", status="running")
            db.session.add(log)
            db.session.commit()

            total_sent = 0
            total_errors = 0

            # 1. 联系新线索
            new_leads = get_leads_for_contact(limit=50)
            logger.info(f"发现 {len(new_leads)} 条待联系新线索")

            for lead in new_leads:
                try:
                    success = self._contact_lead(lead, "初次触达")
                    if success:
                        total_sent += 1
                    else:
                        total_errors += 1
                except Exception as e:
                    total_errors += 1
                    logger.error(f"触达失败 [{lead.name}]: {e}")

            # 2. 跟进有意向的线索
            followup_leads = get_leads_for_followup()
            logger.info(f"发现 {len(followup_leads)} 条待跟进线索")

            for lead in followup_leads:
                try:
                    success = self._contact_lead(lead, "跟进提醒")
                    if success:
                        total_sent += 1
                except Exception as e:
                    total_errors += 1
                    logger.error(f"跟进失败 [{lead.name}]: {e}")

            # 更新日志
            log.status = "success" if total_errors == 0 else "partial"
            log.messages_sent = total_sent
            log.errors = total_errors
            log.detail = f"发送{total_sent}条消息, {total_errors}个错误"
            log.finished_at = datetime.now()
            db.session.commit()

            logger.info(f"自动触达完成: 发送{total_sent}条, 错误{total_errors}条")
            return total_sent

    def _contact_lead(self, lead: Lead, template_name: str) -> bool:
        """通过最优渠道联系线索"""
        # 优先级: 短信 > 微信 > 邮件
        if lead.phone:
            return self.sms.send_to_lead(lead, template_name)
        elif lead.wechat:
            return self.wechat.send_to_lead(lead, template_name)
        elif lead.email:
            return self.email.send_to_lead(lead, template_name)
        else:
            logger.warning(f"线索 {lead.name} 无可用联系方式")
            return False

    def send_campaign(self, app, template_name: str, target_status: str = "all"):
        """群发营销活动"""
        with app.app_context():
            query = Lead.query.filter(Lead.phone.isnot(None), Lead.phone != "")
            if target_status != "all":
                query = query.filter_by(status=target_status)
            leads = query.limit(200).all()

            sent = 0
            for lead in leads:
                try:
                    if self.sms.send_to_lead(lead, template_name):
                        sent += 1
                except Exception as e:
                    logger.error(f"活动发送失败 [{lead.name}]: {e}")

            logger.info(f"活动发送完成: {sent}/{len(leads)}")
            return sent
