# -*- coding: utf-8 -*-
"""Tiered outreach - send messages based on lead level S/A/B/C"""
from datetime import datetime
from loguru import logger
from config import settings
from config.scoring import SMS_TEMPLATES_BY_LEVEL, SMS_SEND_WINDOWS, SMS_MAX_MONTH
from crm.models import db, Lead, Message
from crm.database import record_message
from crm.scoring import score_lead

import importlib

# Monthly counter (resets on import reload)
_monthly_sent = 0


def _in_send_window() -> bool:
    """Check if current time is within allowed send windows."""
    now = datetime.now().strftime("%H:%M")
    for start, end in SMS_SEND_WINDOWS:
        if start <= now <= end:
            return True
    return False


def _send_sms(phone: str, content: str) -> bool:
    """Call actual SMS API. Currently simulated."""
    logger.info(f"[SMS] -> {phone}: {content[:40]}...")
    return True


def auto_contact_by_level(app):
    """Main entry: contact leads based on their level."""
    global _monthly_sent
    with app.app_context():
        results = {"S_alerts": 0, "A_sent": 0, "B_sent": 0, "skipped": 0, "opt_out": 0, "C_skipped": 0}

        # C级线索统计（不自动触达）
        c_count = Lead.query.filter(
            Lead.lead_level == "C", Lead.status == "new",
            Lead.is_opt_out == False,
        ).count()
        results["C_skipped"] = c_count
        logger.info(f"C级线索 {c_count} 条，跳过自动触达（冷数据/低质量）")

        # --- S-level: NO auto SMS, just alert ---
        s_leads = Lead.query.filter(
            Lead.lead_level == "S", Lead.status == "new",
            Lead.is_opt_out == False, Lead.sleep_status == 0,
            Lead.phone.isnot(None), Lead.phone != "",
        ).all()
        for lead in s_leads:
            lead.status = "contacted"
            lead.assigned_to = None  # Unassigned = needs human
            lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%m-%d')}] S\u7ea7\u7ebf\u7d22-\u5f85\u4eba\u5de5\u8ddf\u8fdb"
            record_message(lead.id, "system", "out",
                "[S\u7ea7\u63d0\u9192] \u9ad8\u610f\u5411\u7ebf\u7d22\uff0c\u9700\u4eba\u5de5\u7acb\u5373\u8ddf\u8fdb", status="alert")
            results["S_alerts"] += 1

        # --- A-level: auto SMS + track ---
        if _in_send_window() and _monthly_sent < SMS_MAX_MONTH:
            a_leads = Lead.query.filter(
                Lead.lead_level == "A", Lead.status == "new",
                Lead.is_opt_out == False, Lead.sleep_status == 0,
                Lead.phone.isnot(None), Lead.phone != "",
            ).limit(20).all()
            tpl = SMS_TEMPLATES_BY_LEVEL.get("A", "")
            for lead in a_leads:
                content = tpl.format(
                    company=settings.BUSINESS_NAME,
                    phone=settings.BUSINESS_PHONE,
                    keyword=lead.product_interest or "\u8f66\u68da/\u906e\u9633\u68da",
                )
                success = _send_sms(lead.phone, content)
                if success:
                    _monthly_sent += 1
                    lead.status = "contacted"
                    lead.contact_count += 1
                    lead.last_contact_at = datetime.now()
                    record_message(lead.id, "sms", "out", content, template_name="A\u7ea7\u89e6\u8fbe", status="sent")
                    results["A_sent"] += 1

        # --- B-level only: C级为冷数据/低质量，不自动触达，节省成本 ---
        if _in_send_window() and _monthly_sent < SMS_MAX_MONTH:
            b_leads = Lead.query.filter(
                Lead.lead_level == "B", Lead.status == "new",
                Lead.is_opt_out == False, Lead.sleep_status == 0,
                Lead.phone.isnot(None), Lead.phone != "",
            ).limit(30).all()
            tpl = SMS_TEMPLATES_BY_LEVEL.get("B", "")
            for lead in b_leads:
                content = tpl.format(
                    company=settings.BUSINESS_NAME,
                    phone=settings.BUSINESS_PHONE,
                )
                success = _send_sms(lead.phone, content)
                if success:
                    _monthly_sent += 1
                    lead.status = "contacted"
                    lead.contact_count += 1
                    lead.last_contact_at = datetime.now()
                    record_message(lead.id, "sms", "out", content, template_name="B\u7ea7\u89e6\u8fbe", status="sent")
                    results["B_sent"] += 1

        db.session.commit()

        # Handle opt-outs (check for T replies)
        optouts = Lead.query.filter(Lead.is_opt_out == True, Lead.opt_out_at.is_(None)).count()
        results["opt_out"] = optouts

        logger.info(f"\u5206\u7ea7\u89e6\u8fbe\u5b8c\u6210: S\u63d0\u9192={results['S_alerts']}, A\u53d1\u9001={results['A_sent']}, B\u53d1\u9001={results['B_sent']}, C\u8df3\u8fc7={results['C_skipped']}, \u6708\u5df2\u53d1={_monthly_sent}")
        return results
