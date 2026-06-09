# -*- coding: utf-8 -*-
"""
邮件发送模块
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from loguru import logger

from config import settings
from crm.models import db, Lead
from crm.database import record_message


class EmailSender:
    """邮件发送器"""

    def __init__(self):
        self.enabled = settings.EMAIL_ENABLED
        self.daily_limit = settings.DAILY_EMAIL_LIMIT
        self.today_sent = 0

    def send_to_lead(self, lead: Lead, template_name: str = "初次触达") -> bool:
        """给线索发送邮件"""
        if not lead.email:
            return False

        if not self.enabled:
            logger.info(f"[邮件-模拟] 发送给 {lead.email}: {template_name}")
            record_message(
                lead_id=lead.id,
                channel="email",
                direction="out",
                content=f"[模拟邮件] {template_name}",
                template_name=template_name,
                status="sent",
            )
            return True

        if self.today_sent >= self.daily_limit:
            logger.warning(f"今日邮件发送已达上限 ({self.daily_limit})")
            return False

        try:
            subject = settings.EMAIL_SUBJECT_TEMPLATES.get(
                template_name, "膜结构车棚/遮阳棚专业服务"
            ).format(company=settings.BUSINESS_NAME)

            body = self._render_body(template_name, lead)
            success = self._send_email(lead.email, subject, body)

            if success:
                self.today_sent += 1
                record_message(
                    lead_id=lead.id,
                    channel="email",
                    direction="out",
                    content=body[:500],
                    template_name=template_name,
                    status="sent",
                )
                lead.status = "contacted"
                lead.contact_count += 1
                lead.last_contact_at = datetime.now()
                db.session.commit()
                logger.info(f"[邮件] 已发送给 {lead.email}")
                return True
            return False
        except Exception as e:
            logger.error(f"邮件发送失败 [{lead.email}]: {e}")
            return False

    def _render_body(self, template_name: str, lead: Lead) -> str:
        """渲染邮件正文"""
        return f"""
<html>
<body style="font-family: Microsoft YaHei; font-size: 14px; color: #333;">
<h2>{settings.BUSINESS_NAME}</h2>
<p>尊敬的{lead.contact_person or lead.name}，您好！</p>
<p>我们是{settings.BUSINESS_NAME}，专业承接以下工程：</p>
<ul>
<li>膜结构车棚 / 停车棚</li>
<li>电动遮阳棚 / 推拉棚</li>
<li>钢结构雨棚 / 阳光棚</li>
<li>充电桩车棚 / 光伏车棚</li>
</ul>
<p><strong>我们的优势：</strong></p>
<ul>
<li>免费上门测量 + 设计出图</li>
<li>质保10年，终身维护</li>
<li>厂家直供，价格实惠</li>
</ul>
<p>如有需求，欢迎随时联系我们：</p>
<p>电话：<strong>{settings.BUSINESS_PHONE}</strong></p>
<p>微信：<strong>{settings.BUSINESS_WECHAT}</strong></p>
<br/>
<p>此致</p>
<p>{settings.BUSINESS_NAME}</p>
</body>
</html>
"""

    def _send_email(self, to_addr: str, subject: str, body: str) -> bool:
        """发送邮件"""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.SMTP_USER}>"
            msg["To"] = to_addr
            msg["Subject"] = Header(subject, "utf-8")
            msg.attach(MIMEText(body, "html", "utf-8"))

            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [to_addr], msg.as_string())
            return True
        except Exception as e:
            logger.error(f"SMTP发送失败: {e}")
            return False
