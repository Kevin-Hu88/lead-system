# -*- coding: utf-8 -*-
"""Scoring engine - calculate and update lead scores

2026-06-08: 增加地点类型检测，强化百度地图冷数据降级
"""
from datetime import datetime, timedelta
from loguru import logger
from config.scoring import (
    calc_total_score, SLEEP_DAYS,
    _detect_location_type, _has_any_demand_signal,
    LOCATION_TYPE_KEYWORDS,
    STRONG_SIGNAL_KEYWORDS, STRONG_SIGNAL_BONUS,
    MEDIUM_SIGNAL_KEYWORDS, MEDIUM_SIGNAL_BONUS,
    COLD_SOURCE_LIST,
    AUTO_CATEGORY_RULES,
)
from crm.models import db, Lead


def score_lead(lead):
    """Score a single lead, update level fields, and auto-categorize."""
    data = {
        "source": lead.source or "",
        "product_interest": lead.product_interest or "",
        "area": lead.area or "",
        "customer_type": lead.customer_type or "",
        "demand_desc": lead.demand_desc or "",
        "phone": lead.phone or "",
        "email": lead.email or "",
        "wechat": lead.wechat or "",
        "notes": lead.notes or "",
    }
    total, ss, ks, as_, cs, level = calc_total_score(data)
    lead.total_score = total
    lead.source_score = ss
    lead.keyword_score = ks
    lead.area_score = as_
    lead.corp_score = cs
    lead.lead_level = level
    lead.score = total

    # Auto-categorization based on keywords
    # 2026-06-08: 地点类型无需求信号时不自动分类
    is_location = _detect_location_type(lead.customer_type or "", lead.demand_desc or "", lead.source or "")
    has_signal = _has_any_demand_signal(
        lead.demand_desc or "", lead.notes or "", lead.product_interest or ""
    )

    if not is_location or has_signal:
        text = f"{lead.product_interest or ''} {lead.demand_desc or ''} {lead.customer_type or ''}".lower()
        for kw, (primary, secondary) in AUTO_CATEGORY_RULES.items():
            if kw in text:
                lead.business_category = primary
                break

    # === 数据质量评估 ===
    lead = _assess_data_quality(lead)

    return lead


def _assess_data_quality(lead):
    """评估线索数据质量，自动调整等级。

    2026-06-08 重构逻辑：
    1. 检测是否为地点类型（工业园/停车场等）
    2. 地点类型 + 百度地图 + 无需求信号 → 强制 C 级，封顶 12 分
    3. 地点类型 + 其他来源 + 无需求信号 → 轻度降级
    4. 有需求信号的地点类型按正常流程评分
    """
    source = lead.source or ""
    customer_type = lead.customer_type or ""
    demand_desc = lead.demand_desc or ""
    notes_text = lead.notes or ""
    product = lead.product_interest or ""
    text = f"{demand_desc} {notes_text} {product} {customer_type}"

    is_location = _detect_location_type(customer_type, demand_desc, source)
    has_signal = _has_any_demand_signal(demand_desc, notes_text, product)

    # 1) 强信号检测：有明确需求描述 → 加分
    has_strong_signal = False
    for kw in STRONG_SIGNAL_KEYWORDS:
        if kw in text:
            has_strong_signal = True
            lead.total_score = min(100, lead.total_score + STRONG_SIGNAL_BONUS)
            lead.keyword_score = min(60, lead.keyword_score + STRONG_SIGNAL_BONUS)
            break

    # 2) 中等信号检测：行业相关 → 加分
    if not has_strong_signal:
        for kw in MEDIUM_SIGNAL_KEYWORDS:
            if kw in text:
                lead.total_score = min(100, lead.total_score + MEDIUM_SIGNAL_BONUS)
                lead.keyword_score = min(60, lead.keyword_score + MEDIUM_SIGNAL_BONUS)
                break

    # 3) 地点类型降级处理
    if is_location and not has_signal:
        if source in COLD_SOURCE_LIST:
            # 百度地图 + 地点类型 + 无任何信号 → 强制 C 级，封顶 12 分
            lead.lead_level = "C"
            lead.total_score = min(lead.total_score, 12)
            note_tag = "[地点冷数据]"
            note_detail = _location_type_note(customer_type, demand_desc)
            if note_tag not in (lead.notes or ""):
                lead.notes = (lead.notes or "") + f"\n{note_tag} {note_detail}"
        else:
            # 其他来源 + 地点类型 + 无信号 → 轻度降级，封顶 25 分
            lead.total_score = min(lead.total_score, 25)
            note_tag = "[地点低优先]"
            if note_tag not in (lead.notes or ""):
                lead.notes = (lead.notes or "") + f"\n{note_tag} 地点类型无需求信号，降为低优先级"

    # 4) 冷数据降级：百度地图来源且无任何需求信号
    #    但实体类型+有电话的不降级
    elif source in COLD_SOURCE_LIST and not has_strong_signal:
        from config.scoring import ENTITY_TYPE_LIST
        is_entity_with_phone = (
            customer_type in ENTITY_TYPE_LIST
            and lead.phone
        )
        if not is_entity_with_phone and not any(kw in text for kw in MEDIUM_SIGNAL_KEYWORDS):
            lead.lead_level = "C"
            lead.total_score = min(lead.total_score, 20)
            if not lead.notes:
                lead.notes = ""
            if "[冷数据]" not in lead.notes:
                lead.notes += "\n[冷数据] 百度地图POI，无需求信号，自动降级为C级"

    # 5) 重新根据总分定级（覆盖上面的强制 C）
    if has_strong_signal and lead.total_score >= 70:
        lead.lead_level = "S"
    elif lead.total_score >= 70:
        lead.lead_level = "S"
    elif lead.total_score >= 50:
        lead.lead_level = "A"
    elif lead.total_score >= 30:
        lead.lead_level = "B"
    else:
        lead.lead_level = "C"

    lead.score = lead.total_score

    # S 级线索即时通知
    if lead.lead_level == "S" and lead.phone:
        try:
            from auto_outreach.notifications import notify_s_level_lead
            notify_s_level_lead(lead)
        except Exception as e:
            logger.debug(f"[通知] S级通知失败: {e}")

    return lead


def _location_type_note(customer_type: str, demand_desc: str) -> str:
    """生成地点类型降级说明"""
    detected = []
    text = f"{customer_type} {demand_desc}"
    for kw in LOCATION_TYPE_KEYWORDS:
        if kw in text:
            detected.append(kw)
    type_str = "/".join(detected[:3]) if detected else customer_type
    return f"百度地图POI为地点类型({type_str})，非决策主体，无需求信号，自动降级为C级"


def score_all_leads(app):
    """Batch score all leads."""
    with app.app_context():
        leads = Lead.query.filter(Lead.is_opt_out == False).all()
        count = 0
        for lead in leads:
            score_lead(lead)
            count += 1
        db.session.commit()
        logger.info(f"Scored {count} leads")
        # Stats
        s = Lead.query.filter_by(lead_level="S").count()
        a = Lead.query.filter_by(lead_level="A").count()
        b = Lead.query.filter_by(lead_level="B").count()
        c = Lead.query.filter_by(lead_level="C").count()
        logger.info(f"  S={s}  A={a}  B={b}  C={c}")
        return {"total": count, "S": s, "A": a, "B": b, "C": c}


def mark_sleep_leads(app):
    """Mark leads as sleeping if no follow-up for SLEEP_DAYS."""
    with app.app_context():
        cutoff = datetime.now() - timedelta(days=SLEEP_DAYS)
        leads = Lead.query.filter(
            Lead.sleep_status == 0,
            Lead.is_opt_out == False,
            Lead.status.notin_(["closed_won", "closed_lost"]),
        ).all()
        count = 0
        for lead in leads:
            last = lead.last_contact_at or lead.created_at
            if last and last < cutoff:
                lead.sleep_status = 1
                count += 1
        db.session.commit()
        logger.info(f"Marked {count} leads as sleeping")
        return count


def opt_out_lead(phone: str):
    """Mark a phone number as opted out."""
    leads = Lead.query.filter_by(phone=phone).all()
    for lead in leads:
        lead.is_opt_out = True
        lead.opt_out_at = datetime.now()
        lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%m-%d')}] 客户退订"
    db.session.commit()
    return len(leads)


