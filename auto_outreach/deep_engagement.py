# -*- coding: utf-8 -*-
"""
深耕对话引擎 - 多轮跟进话术与对话状态管理

实现持续对话的条件:
1. 对话阶段追踪 (初次→需求→方案→报价→成交)
2. 每个阶段有多套话术模板，避免重复
3. 自动安排下次跟进时间
4. 根据客户反应调整策略
5. 对话历史上下文注入，保证连贯性
"""
from datetime import datetime, timedelta
from loguru import logger
from crm.models import db, Lead, Message, FollowUpPlan
from crm.database import record_message


# ============================================================
# 对话阶段定义
# ============================================================
STAGES = {
    "initial":    {"name": "初次触达", "order": 0, "desc": "首次联系客户，建立认知"},
    "discovery":  {"name": "需求挖掘", "order": 1, "desc": "了解客户具体需求"},
    "case_study": {"name": "案例展示", "order": 2, "desc": "用成功案例建立信任"},
    "proposal":   {"name": "方案报价", "order": 3, "desc": "提供针对性方案和报价"},
    "push":       {"name": "跟进推动", "order": 4, "desc": "解决疑虑，推动决策"},
    "close":      {"name": "促成成交", "order": 5, "desc": "最后推动，促成签约"},
}

# 阶段推进路径
STAGE_ORDER = ["initial", "discovery", "case_study", "proposal", "push", "close"]

# 每个阶段的跟进间隔(天)
STAGE_INTERVALS = {
    "initial":    1,   # 初次触达后1天跟进
    "discovery":  2,   # 需求挖掘后2天跟进
    "case_study": 3,   # 案例展示后3天跟进
    "proposal":   2,   # 方案报价后2天跟进
    "push":       3,   # 跟进推动后3天跟进
    "close":      5,   # 促成交后5天最后跟进
}


# ============================================================
# 各阶段话术库 (每个阶段多套模板，轮换使用避免重复)
# ============================================================
SCRIPTS = {
    # ── 膜结构 ──
    "膜结构": {
        "initial": {
            "学校": [
                "您好！我们是专业膜结构工程公司，20年施工经验，近期刚为XX学校完成了操场膜结构看台项目，遮阳挡雨还抗风抗雪。了解到贵校可能有类似需求，方便发一份案例资料给您参考吗？",
                "您好，专注膜结构车棚/看台的专业厂家，本地多所学校落地完工。了解到贵校可能有相关规划，方便简单沟通一下吗？",
            ],
            "工厂": [
                "您好，我们是专业膜结构停车棚厂家，为多家工厂提供过员工停车区膜结构方案，施工快、造价低、免维护。请问贵厂目前有多少停车位需要覆盖？",
                "您好！膜结构车棚专业施工方，本地工业园区多个案例。方便了解一下贵厂区的停车需求吗？",
            ],
            "4S店": [
                "您好，我们专做4S店膜结构车棚，近期为XX品牌4S店完成了新车交付区膜结构工程，客户非常满意。请问贵店有新车展示区或停车区的遮阳需求吗？",
            ],
            "物业": [
                "您好，专业承接小区膜结构车棚/雨棚工程，近期为XX小区完成了电动车棚安装，物业反馈业主满意度很高。请问贵小区有停车棚的规划需求吗？",
            ],
            "default": [
                "您好，我们是湖北地区专业膜结构车棚厂家，拥有钢结构+膜结构双资质，近期完工多个同类项目。了解到您可能有相关需求，方便简单沟通一下吗？",
                "您好！膜结构工程专业承建商，质保10年，免费上门测量设计。方便了解一下您的具体需求吗？",
            ],
        },
        "discovery": {
            "default": [
                "上次跟您简单聊过，想进一步了解一下您的具体需求：\n1. 大概需要覆盖多少面积？\n2. 有没有设计风格偏好？\n3. 预计什么时候启动？\n这些信息方便我们为您准备更精准的方案。",
                "您好，上次沟通后我们整理了几个适合您场景的方案思路。方便了解一下您的具体使用场景和预算范围吗？这样可以更有针对性地为您设计。",
            ],
        },
        "case_study": {
            "default": [
                "根据您之前提到的需求，我们有几个非常匹配的案例：\n📐 XX项目 - 面积{area}㎡，{type}场景\n⏱ 工期{days}天完工\n💰 造价约{price}元/㎡\n需要我把详细案例和实景照片发给您看看吗？",
                "这是我们近期完成的一个同类项目：\n✅ 面积{area}㎡\n✅ 抗风等级8级\n✅ 质保10年\n✅ 客户评价: 非常满意\n有图片资料可以发给您参考，方便加微信吗？",
            ],
        },
        "proposal": {
            "default": [
                "根据您的需求，我们初步方案如下：\n🏗 结构形式: {structure}\n📐 预估面积: {area}㎡\n💰 预估造价: {price}元/㎡\n⏱ 施工周期: {days}天\n📋 含: 基础+钢结构+膜材+安装\n\n具体报价需要现场勘测后确定，方便安排免费上门测量吗？",
            ],
        },
        "push": {
            "default": [
                "您好，上次发的方案您看了吗？如果有什么疑问或者需要调整的地方，随时告诉我。我们近期档期还有空，如果尽快确认的话可以安排优先施工。",
                "您好，上次的方案资料您考虑得怎么样了？有任何问题都可以随时沟通，我们也可以安排免费上门看现场，帮助您更直观地了解方案。",
            ],
        },
        "close": {
            "default": [
                "您好，跟您确认一下上次沟通的膜结构项目。我们近期刚好有施工队在这个区域，如果现在确定的话可以尽快进场。另外质保10年，后期免维护，性价比很高。您看什么时候方便签合同开工？",
            ],
        },
    },

    # ── 玻璃遮阳棚 ──
    "玻璃遮阳棚": {
        "initial": {
            "小区": [
                "您好，我们专做小区地下车库出入口玻璃遮阳棚和雨棚，近期刚交付了XX小区的项目。玻璃雨棚既美观又实用，很多新楼盘都在配套。请问贵小区目前有这方面规划吗？",
            ],
            "医院": [
                "您好，我们为多家医院提供过连廊玻璃雨棚和门诊入口遮阳棚，材料用的是钢化夹胶玻璃，安全性和透光性都很好。请问近期有门诊楼或住院部的改造计划吗？",
            ],
            "default": [
                "您好，我们专业生产玻璃遮阳棚/雨棚，适用于商业、住宅、医院等各类场景，可定制各种造型。方便了解一下您的具体需求吗？",
                "您好！玻璃遮阳棚/雨棚专业厂家，本地多个完工案例，免费设计出图。方便沟通一下您的需求吗？",
            ],
        },
        "discovery": {
            "default": [
                "上次沟通后想进一步了解：\n1. 安装位置大概多大面积？\n2. 有没有造型偏好（平顶/弧形/斜坡）？\n3. 对透光率有什么要求？\n这些信息帮我准备更合适的方案。",
            ],
        },
        "case_study": {
            "default": [
                "给您看一个我们近期完成的玻璃雨棚项目：\n📍 地点: {location}\n📐 面积: {area}㎡\n🎨 材质: 钢化夹胶玻璃\n⏱ 工期: {days}天\n效果既通透又安全，可以发实景照片给您参考。",
            ],
        },
        "proposal": {
            "default": [
                "玻璃雨棚初步方案：\n🏗 结构: {structure}\n📐 面积: {area}㎡\n💰 造价: {price}元/㎡\n📋 含: 钢架+玻璃+安装+防水\n\n免费上门测量后可出精确报价，方便安排吗？",
            ],
        },
        "push": {
            "default": [
                "您好，方案您看了吗？有任何疑问随时沟通。我们用的是钢化夹胶玻璃，安全性通过国家检测，美观度也很高。",
            ],
        },
        "close": {
            "default": [
                "您好，上次沟通的玻璃雨棚项目，近期可以安排施工。现在确定的话工期比较充裕，可以保证质量。您看方便签合同确认吗？",
            ],
        },
    },

    # ── 光伏车棚 ──
    "光伏车棚": {
        "initial": {
            "工厂": [
                "您好，我们做的光伏车棚既能遮阳停车又能发电创收，以XX产业园为例，500个车位的光伏车棚年发电量可达XX万度。很多企业都在用这种方式降低用电成本。请问贵厂区有多少停车位？",
            ],
            "商业": [
                "您好，光伏车棚是目前商业综合体停车场的标配升级方案，既提升物业形象又能产生电费收益。我们刚为XX商业广场完成了1000平米的光伏车棚项目。请问有这方面的规划吗？",
            ],
            "default": [
                "您好，我们是湖北地区光伏车棚专业承建商，集设计、施工、并网于一体。光伏车棚一棚两用，既能遮阳停车又能发电卖电。方便了解一下您的停车区情况吗？",
            ],
        },
        "discovery": {
            "default": [
                "光伏车棚需要了解几个关键信息：\n1. 停车场大概多少车位？\n2. 场地是否朝南无遮挡？\n3. 目前电费单价大概多少？\n这些决定了发电收益和投资回报周期。",
            ],
        },
        "case_study": {
            "default": [
                "给您看一个光伏车棚的实际收益案例：\n📍 {location}\n📐 装机容量: {capacity}kW\n⚡ 年发电量: {kwh}万度\n💰 年节省电费: {saving}万元\n📅 投资回本周期: 约{years}年\n之后都是纯收益，还享25年质保。",
            ],
        },
        "proposal": {
            "default": [
                "光伏车棚初步方案：\n🏗 结构: {structure}\n📐 装机容量: {capacity}kW\n💰 总投资: {price}万元\n⚡ 预计年发电: {kwh}万度\n💰 预计年收益: {saving}万元\n📅 回本周期: 约{years}年\n\n含申请补贴服务，详细方案需现场勘测。",
            ],
        },
        "push": {
            "default": [
                "您好，光伏车棚方案您考虑得怎么样？目前国家有补贴政策，尽早安装可以享受更高补贴额度。我们也可以安排到已完工项目实地参观。",
            ],
        },
        "close": {
            "default": [
                "您好，光伏车棚项目确认一下？目前安装可以享受补贴政策，投资回报率更高。我们负责全套并网手续，您只需提供场地。什么时候方便签约开工？",
            ],
        },
    },
}

# 没有匹配业务分类时的默认话术
DEFAULT_CATEGORY = "膜结构"


# ============================================================
# 对话引擎核心函数
# ============================================================

def get_lead_context(lead: Lead) -> dict:
    """获取线索的对话上下文信息"""
    # 获取最近5条消息
    recent_msgs = Message.query.filter_by(lead_id=lead.id)\
        .order_by(Message.created_at.desc()).limit(5).all()

    # 获取当前对话计划
    plan = FollowUpPlan.query.filter_by(lead_id=lead.id, status="active")\
        .order_by(FollowUpPlan.created_at.desc()).first()

    return {
        "lead": lead,
        "recent_messages": recent_msgs,
        "current_stage": plan.current_stage if plan else "initial",
        "contact_count": lead.contact_count,
        "days_since_last_contact": (
            (datetime.now() - lead.last_contact_at).days
            if lead.last_contact_at else 999
        ),
        "plan": plan,
    }


def generate_script(lead: Lead, stage: str = None, script_index: int = 0) -> dict:
    """
    为线索生成当前阶段的话术

    Args:
        lead: 线索对象
        stage: 指定阶段，None则自动判断
        script_index: 选择第几套模板(0-based)，避免重复

    Returns:
        {
            "stage": 当前阶段,
            "stage_name": 阶段名称,
            "script": 话术内容,
            "next_stage": 下一阶段,
            "next_action": 下一步建议,
            "follow_up_days": 建议跟进天数,
        }
    """
    # 自动判断阶段
    if stage is None:
        plan = FollowUpPlan.query.filter_by(lead_id=lead.id, status="active").first()
        if plan:
            stage = plan.current_stage
        else:
            stage = _infer_stage(lead)

    # 选择话术库
    category = lead.business_category or DEFAULT_CATEGORY
    cat_scripts = SCRIPTS.get(category, SCRIPTS[DEFAULT_CATEGORY])
    stage_scripts = cat_scripts.get(stage, cat_scripts.get("initial", {}))

    # 按客户类型匹配
    ctype = lead.customer_type or ""
    matched_scripts = None
    for key in [ctype, "default"]:
        if key in stage_scripts:
            matched_scripts = stage_scripts[key]
            break

    if not matched_scripts:
        # fallback to default
        matched_scripts = stage_scripts.get("default", ["您好，请问有什么可以帮到您？"])

    # 轮换选择模板
    idx = script_index % len(matched_scripts)
    script_text = matched_scripts[idx]

    # 替换变量
    script_text = _fill_template_vars(script_text, lead)

    # 计算下一阶段
    current_idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
    next_stage = STAGE_ORDER[min(current_idx + 1, len(STAGE_ORDER) - 1)]
    next_info = STAGES.get(next_stage, {})

    return {
        "stage": stage,
        "stage_name": STAGES.get(stage, {}).get("name", stage),
        "script": script_text,
        "next_stage": next_stage,
        "next_action": next_info.get("desc", ""),
        "follow_up_days": STAGE_INTERVALS.get(stage, 3),
        "script_total": len(matched_scripts),
        "category": category,
    }


def _infer_stage(lead: Lead) -> str:
    """根据线索状态和联系历史推断当前对话阶段"""
    if lead.contact_count == 0:
        return "initial"
    if lead.contact_count == 1:
        return "discovery"
    if lead.status in ("interested",):
        return "case_study"
    if lead.status in ("quoting",):
        return "proposal"
    if lead.status in ("contacted",):
        return "push"
    return "discovery"


def _fill_template_vars(text: str, lead: Lead) -> str:
    """替换话术模板中的变量"""
    replacements = {
        "{company}": "XX膜结构工程有限公司",
        "{phone}": lead.phone or "400-XXX-XXXX",
        "{name}": lead.name or "",
        "{area}": str(int(lead.estimated_area)) if lead.estimated_area else "待确认",
        "{type}": lead.customer_type or "停车",
        "{contact}": lead.contact_person or "",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def advance_stage(lead_id: int, direction: str = "forward") -> FollowUpPlan:
    """
    推进对话阶段

    Args:
        lead_id: 线索ID
        direction: "forward"(前进) / "back"(回退)

    Returns:
        更新后的FollowUpPlan
    """
    plan = FollowUpPlan.query.filter_by(lead_id=lead_id, status="active").first()

    if not plan:
        # 创建新的对话计划
        lead = Lead.query.get(lead_id)
        if not lead:
            return None
        initial_stage = _infer_stage(lead)
        plan = FollowUpPlan(
            lead_id=lead_id,
            current_stage=initial_stage,
            script_index=0,
            total_contacts=lead.contact_count,
            status="active",
        )
        db.session.add(plan)

    current_idx = STAGE_ORDER.index(plan.current_stage) if plan.current_stage in STAGE_ORDER else 0

    if direction == "forward":
        new_idx = min(current_idx + 1, len(STAGE_ORDER) - 1)
        plan.script_index = 0  # 新阶段重置模板索引
    else:
        new_idx = max(current_idx - 1, 0)

    plan.current_stage = STAGE_ORDER[new_idx]
    plan.last_contact_at = datetime.now()
    plan.next_follow_up = datetime.now() + timedelta(days=STAGE_INTERVALS.get(plan.current_stage, 3))

    db.session.commit()
    logger.info(f"[DeepEngagement] Lead {lead_id} -> stage '{plan.current_stage}'")
    return plan


def record_and_advance(lead_id: int, content: str, channel: str = "manual",
                       advance: bool = True) -> dict:
    """
    记录消息并推进对话

    Args:
        lead_id: 线索ID
        content: 消息内容
        channel: 渠道
        advance: 是否自动推进阶段

    Returns:
        {"message": Message, "plan": FollowUpPlan, "next_script": dict}
    """
    # 记录消息
    msg = record_message(lead_id, channel, "out", content, status="sent")

    # 更新对话计划
    plan = FollowUpPlan.query.filter_by(lead_id=lead_id, status="active").first()
    if not plan:
        plan = advance_stage(lead_id, "forward")
    elif advance:
        plan.total_contacts += 1
        plan.last_contact_at = datetime.now()
        plan.script_index += 1  # 同阶段轮换模板

        # 每联系2次自动前进一个阶段
        if plan.total_contacts >= 2 and plan.current_stage != "close":
            contacts_in_stage = plan.total_contacts
            if contacts_in_stage % 2 == 0:
                plan = advance_stage(lead_id, "forward")

        plan.next_follow_up = datetime.now() + timedelta(
            days=STAGE_INTERVALS.get(plan.current_stage, 3)
        )
        db.session.commit()

    # 生成下一阶段话术
    lead = Lead.query.get(lead_id)
    next_script = generate_script(lead)

    return {
        "message": msg,
        "plan": plan,
        "next_script": next_script,
    }


def get_leads_needing_followup(limit: int = 50) -> list:
    """获取需要跟进的线索（对话计划中有到期的）"""
    now = datetime.now()
    plans = FollowUpPlan.query.filter(
        FollowUpPlan.status == "active",
        FollowUpPlan.next_follow_up <= now,
    ).order_by(FollowUpPlan.next_follow_up.asc()).limit(limit).all()

    results = []
    for plan in plans:
        lead = Lead.query.get(plan.lead_id)
        if lead and not lead.is_opt_out and lead.sleep_status == 0:
            script = generate_script(lead, plan.current_stage)
            results.append({
                "lead": lead,
                "plan": plan,
                "script": script,
                "overdue_days": (now - plan.next_follow_up).days,
            })
    return results


def get_engagement_summary() -> dict:
    """获取深耕对话整体统计"""
    total_plans = FollowUpPlan.query.filter_by(status="active").count()

    stage_counts = {}
    for stage_key, stage_info in STAGES.items():
        count = FollowUpPlan.query.filter_by(
            status="active", current_stage=stage_key
        ).count()
        stage_counts[stage_info["name"]] = count

    # 今日需要跟进的数量
    now = datetime.now()
    today_start = datetime.combine(now.date(), datetime.min.time())
    due_today = FollowUpPlan.query.filter(
        FollowUpPlan.status == "active",
        FollowUpPlan.next_follow_up <= now,
    ).count()

    overdue = FollowUpPlan.query.filter(
        FollowUpPlan.status == "active",
        FollowUpPlan.next_follow_up < today_start,
    ).count()

    return {
        "total_active_plans": total_plans,
        "stage_counts": stage_counts,
        "due_today": due_today,
        "overdue": overdue,
    }
