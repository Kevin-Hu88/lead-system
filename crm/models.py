# -*- coding: utf-8 -*-
"""Database models - upgraded with scoring, levels, compliance"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    # Basic info
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(50))
    phone = db.Column(db.String(20), index=True)
    email = db.Column(db.String(100))
    wechat = db.Column(db.String(100))
    address = db.Column(db.String(300))

    # Source and classification
    source = db.Column(db.String(50), nullable=False)
    source_url = db.Column(db.String(500))
    customer_type = db.Column(db.String(50))
    area = db.Column(db.String(100))
    product_interest = db.Column(db.String(200))
    business_category = db.Column(db.String(50), default="膜结构", index=True,
                                  comment="主营业务分类: 膜结构/玻璃遮阳棚/光伏车棚")

    # Status
    status = db.Column(db.String(20), default="new", index=True)
    score = db.Column(db.Integer, default=0)
    priority = db.Column(db.String(10), default="normal")

    # === NEW: Scoring & Level fields ===
    lead_level = db.Column(db.String(10), default="C", index=True,
                           comment="S/A/B/C lead level")
    total_score = db.Column(db.Integer, default=0, index=True,
                            comment="Calculated total score 0-100")
    source_score = db.Column(db.Integer, default=0, comment="Score from channel")
    keyword_score = db.Column(db.Integer, default=0, comment="Score from keyword intent")
    area_score = db.Column(db.Integer, default=0, comment="Score from geographic area")
    corp_score = db.Column(db.Integer, default=0, comment="Score from business type/size")

    # === NEW: Compliance fields ===
    is_opt_out = db.Column(db.Boolean, default=False, index=True,
                           comment="Unsubscribed, never contact again")
    opt_out_at = db.Column(db.DateTime, comment="When they unsubscribed")

    # === NEW: Bid project fields ===
    bid_budget = db.Column(db.Float, default=0, comment="项目金额(万元)")
    bid_budget_text = db.Column(db.String(100), comment="金额原文")
    bid_deadline = db.Column(db.String(100), comment="投标截止时间")
    bid_open_time = db.Column(db.String(100), comment="开标时间")
    bid_purchaser = db.Column(db.String(200), comment="采购人")
    bid_agency = db.Column(db.String(200), comment="代理机构")

    # === NEW: Sleep mechanism ===
    sleep_status = db.Column(db.Integer, default=0, index=True,
                             comment="0=active, 1=sleeping (no follow-up 90 days)")

    # Demand details
    demand_desc = db.Column(db.Text)
    estimated_area = db.Column(db.Float)
    budget_range = db.Column(db.String(50))
    urgency = db.Column(db.String(20))

    # Tracking
    contact_count = db.Column(db.Integer, default=0)
    last_contact_at = db.Column(db.DateTime)
    next_follow_up = db.Column(db.DateTime)
    assigned_to = db.Column(db.String(50))
    notes = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    exported_at = db.Column(db.DateTime, comment="Last export time")
    phone_score = db.Column(db.Integer, default=0, comment="电话质量评分 0-100")
    phone_status = db.Column(db.String(20), default="unknown", comment="号码状态: active/inactive/unknown")

    messages = db.relationship("Message", backref="lead", lazy="dynamic",
                               order_by="Message.created_at.desc()")

    STATUS_LABELS = {
        "new": "新线索", "contacted": "已联系", "interested": "有意向",
        "quoting": "报价中", "closed_won": "已成交", "closed_lost": "已流失",
    }
    LEVEL_LABELS = {"S": "S高意向", "A": "A中等", "B": "B一般", "C": "C低"}

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def level_label(self):
        return self.LEVEL_LABELS.get(self.lead_level, self.lead_level)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "contact_person": self.contact_person,
            "phone": self.phone, "email": self.email, "wechat": self.wechat,
            "address": self.address, "source": self.source, "customer_type": self.customer_type,
            "area": self.area, "product_interest": self.product_interest,
            "status": self.status, "status_label": self.status_label,
            "score": self.score, "priority": self.priority,
            "lead_level": self.lead_level, "level_label": self.level_label,
            "total_score": self.total_score,
            "source_score": self.source_score, "keyword_score": self.keyword_score,
            "area_score": self.area_score, "corp_score": self.corp_score,
            "is_opt_out": self.is_opt_out, "sleep_status": self.sleep_status,
            "demand_desc": self.demand_desc, "estimated_area": self.estimated_area,
            "contact_count": self.contact_count,
            "last_contact_at": self.last_contact_at.strftime("%Y-%m-%d %H:%M") if self.last_contact_at else None,
            "next_follow_up": self.next_follow_up.strftime("%Y-%m-%d %H:%M") if self.next_follow_up else None,
            "assigned_to": self.assigned_to, "notes": self.notes,
            "bid_budget": self.bid_budget,
            "bid_budget_text": self.bid_budget_text,
            "bid_deadline": self.bid_deadline,
            "bid_open_time": self.bid_open_time,
            "bid_purchaser": self.bid_purchaser,
            "bid_agency": self.bid_agency,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
            "exported_at": self.exported_at.strftime("%Y-%m-%d %H:%M") if self.exported_at else None,
            "phone_score": self.phone_score,
            "phone_status": self.phone_status,
        }


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    channel = db.Column(db.String(20), nullable=False)
    direction = db.Column(db.String(10), default="out")
    content = db.Column(db.Text, nullable=False)
    template_name = db.Column(db.String(50))
    status = db.Column(db.String(20), default="pending")
    error_msg = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "lead_id": self.lead_id, "channel": self.channel,
            "direction": self.direction, "content": self.content,
            "status": self.status, "error_msg": self.error_msg,
            "bid_budget": self.bid_budget,
            "bid_budget_text": self.bid_budget_text,
            "bid_deadline": self.bid_deadline,
            "bid_open_time": self.bid_open_time,
            "bid_purchaser": self.bid_purchaser,
            "bid_agency": self.bid_agency,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class TaskLog(db.Model):
    __tablename__ = "task_logs"
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="running")
    detail = db.Column(db.Text)
    leads_found = db.Column(db.Integer, default=0)
    messages_sent = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.now)
    finished_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id, "task_name": self.task_name, "status": self.status,
            "detail": self.detail, "leads_found": self.leads_found,
            "messages_sent": self.messages_sent, "errors": self.errors,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M") if self.started_at else None,
            "finished_at": self.finished_at.strftime("%Y-%m-%d %H:%M") if self.finished_at else None,
        }
