# -*- coding: utf-8 -*-
import requests, re
from datetime import datetime
from loguru import logger
from config import settings


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def send_serverchan(title, content):
    key = settings.SERVERCHAN_KEY
    if not key:
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        resp = requests.post(url, data={"title": title[:100], "desp": content}, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            logger.info("[Server酱] 推送成功")
            return True
        logger.error(f"[Server酱] 推送失败: {data}")
        return False
    except Exception as e:
        logger.error(f"[Server酱] 异常: {e}")
        return False


def send_telegram(text):
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def send_notification(title, html_text):
    sent = False
    plain = _strip_html(html_text)
    if send_serverchan(title, plain):
        sent = True
    if send_telegram(html_text):
        sent = True
    if not sent:
        logger.warning("[通知] 所有渠道均未配置")
    return sent


def notify_s_level_lead(lead):
    if not settings.S_LEVEL_INSTANT_NOTIFY:
        return
    msg = (
        f"公司: {lead.name}\n"
        f"联系人: {lead.contact_person or '无'}\n"
        f"电话: {lead.phone or '无'}\n"
        f"区域: {lead.area or '未知'}\n"
        f"需求: {(lead.demand_desc or '无')[:100]}\n"
        f"评分: {lead.total_score}分\n请立即跟进！"
    )
    send_notification("S级高意向线索", msg)


def notify_harvest_complete(added, with_phone, skipped):
    msg = f"新增: {added}\n有电话: {with_phone}\n去重: {skipped}\n时间: {datetime.now().strftime('%H:%M')}"
    send_notification("采集完成", msg)


def send_daily_report():
    from crm.models import db, Lead, Message
    from dashboard.app import app
    from datetime import date

    with app.app_context():
        today = date.today()
        new_today = Lead.query.filter(
            Lead.created_at >= datetime.combine(today, datetime.min.time())
        ).count()
        s = Lead.query.filter_by(lead_level="S").count()
        a = Lead.query.filter_by(lead_level="A").count()
        b = Lead.query.filter_by(lead_level="B").count()
        c = Lead.query.filter_by(lead_level="C").count()
        total = Lead.query.count()
        s_pending = Lead.query.filter(
            Lead.lead_level == "S", Lead.status.in_(["new", "contacted"]), Lead.is_opt_out == False
        ).count()
        msg_sent = Message.query.filter(
            Message.created_at >= datetime.combine(today, datetime.min.time()), Message.direction == "out"
        ).count()
        report = (
            f"每日报告 ({today.strftime('%m-%d')})\n\n"
            f"今日新增: {new_today}\n总量: {total}\n"
            f"S:{s} A:{a} B:{b} C:{c}\n"
            f"今日触达: {msg_sent}\nS级待跟进: {s_pending}\n"
            f"S+A占比: {(s+a)/max(total,1)*100:.1f}%"
        )
        send_notification("每日报告", report)
        logger.info("[日报] 已发送")
        return report
