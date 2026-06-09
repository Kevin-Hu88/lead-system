"""
数据库操作封装
"""
from datetime import datetime, date, timedelta
from crm.models import db, Lead, Message, TaskLog


def init_db(app):
    """初始化数据库"""
    db.init_app(app)
    with app.app_context():
        db.create_all()


def add_lead(lead_data: dict) -> Lead:
    """添加新线索，自动去重（基于电话或名称+地址）"""
    # 去重检查
    if lead_data.get("phone"):
        existing = Lead.query.filter_by(phone=lead_data["phone"]).first()
        if existing:
            return existing  # 已存在，不重复添加

    if lead_data.get("name") and lead_data.get("address"):
        existing = Lead.query.filter_by(
            name=lead_data["name"], address=lead_data["address"]
        ).first()
        if existing:
            return existing

    lead = Lead(**lead_data)
    db.session.add(lead)
    db.session.commit()
    return lead


def add_leads_batch(leads_data: list) -> tuple:
    """批量添加线索，返回 (新增数, 跳过数)"""
    added = 0
    skipped = 0
    for data in leads_data:
        try:
            lead = add_lead(data)
            if lead.created_at and (datetime.now() - lead.created_at).seconds < 60:
                added += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    return added, skipped


def update_lead_status(lead_id: int, new_status: str, note: str = None):
    """更新线索状态"""
    lead = Lead.query.get(lead_id)
    if not lead:
        return None
    lead.status = new_status
    lead.updated_at = datetime.now()
    if note:
        lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%m-%d %H:%M')}] {note}"
    db.session.commit()
    return lead


def update_lead_score(lead_id: int, score_delta: int):
    """增加线索评分"""
    lead = Lead.query.get(lead_id)
    if not lead:
        return None
    lead.score = min(100, max(0, lead.score + score_delta))
    lead.updated_at = datetime.now()
    db.session.commit()
    return lead


def record_message(lead_id: int, channel: str, direction: str,
                   content: str, template_name: str = None,
                   status: str = "sent", error_msg: str = None) -> Message:
    """记录一条消息"""
    msg = Message(
        lead_id=lead_id,
        channel=channel,
        direction=direction,
        content=content,
        template_name=template_name,
        status=status,
        error_msg=error_msg,
    )
    db.session.add(msg)

    # 更新线索的联系次数
    if direction == "out":
        lead = Lead.query.get(lead_id)
        if lead:
            lead.contact_count += 1
            lead.last_contact_at = datetime.now()

    db.session.commit()
    return msg


def get_leads_for_contact(limit: int = 50) -> list:
    """获取需要自动联系的线索：新线索且未联系过的，只推高质量电话"""
    return Lead.query.filter(
        Lead.status == "new",
        Lead.phone.isnot(None),
        Lead.phone != "",
        Lead.phone_score >= 50,  # 只推中高质量电话
        Lead.is_opt_out == False,
        Lead.sleep_status == 0,
    ).order_by(Lead.phone_score.desc(), Lead.total_score.desc()).limit(limit).all()


def get_leads_for_followup() -> list:
    """获取需要跟进的线索"""
    now = datetime.now()
    return Lead.query.filter(
        Lead.next_follow_up <= now,
        Lead.status.in_(["contacted", "interested", "quoting"]),
    ).order_by(Lead.next_follow_up.asc()).limit(50).all()


def get_human_handoff_leads() -> list:
    """获取需要人工介入的高意向线索"""
    from config.settings import HUMAN_HANDOFF_SCORE
    return Lead.query.filter(
        Lead.score >= HUMAN_HANDOFF_SCORE,
        Lead.status.notin_(["closed_won", "closed_lost"]),
        Lead.assigned_to.is_(None),
    ).order_by(Lead.score.desc()).all()


def get_dashboard_stats() -> dict:
    """获取仪表盘统计数据"""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    total = Lead.query.count()
    new_today = Lead.query.filter(
        Lead.created_at >= datetime.combine(today, datetime.min.time())
    ).count()

    status_counts = {}
    for status, label in Lead.STATUS_LABELS.items():
        status_counts[label] = Lead.query.filter_by(status=status).count()

    week_leads = Lead.query.filter(
        Lead.created_at >= datetime.combine(week_ago, datetime.min.time())
    ).count()
    month_leads = Lead.query.filter(
        Lead.created_at >= datetime.combine(month_ago, datetime.min.time())
    ).count()

    week_messages = Message.query.filter(
        Message.created_at >= datetime.combine(week_ago, datetime.min.time()),
        Message.direction == "out"
    ).count()

    high_score = Lead.query.filter(
        Lead.score >= 60,
        Lead.status.notin_(["closed_won", "closed_lost"]),
    ).count()

    return {
        "total_leads": total,
        "new_today": new_today,
        "status_counts": status_counts,
        "week_leads": week_leads,
        "month_leads": month_leads,
        "week_messages": week_messages,
        "high_score_leads": high_score,
    }
