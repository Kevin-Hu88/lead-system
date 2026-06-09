# -*- coding: utf-8 -*-
"""
统一数据清洗模块 - 所有采集器共用

功能：
1. 电话号码提取与验证
2. 公司名称清洗（去除噪音字符）
3. 地址标准化
4. 竞品过滤
5. 噪音内容检测
6. 重复检测
"""
import re
from loguru import logger
from crm.models import db, Lead
from lead_harvester.phone_verifier import PhoneVerifier


class DataCleaner:
    """统一数据清洗器"""

    # 竞品关键词（这些是竞争对手，不是客户）
    COMPETITOR_KEYWORDS = [
        "膜结构公司", "膜结构厂家", "车棚厂家", "遮阳棚厂家", "雨棚厂家",
        "张拉膜公司", "膜结构工程公司", "车棚公司", "专业车棚", "车棚制作",
        "车棚加工", "膜结构加工厂", "雨棚制作", "遮阳棚制作", "推拉棚厂",
        "伸缩棚厂", "移动棚厂", "折叠棚厂", "钢结构公司", "钢结构厂家",
    ]

    # 噪音关键词（这些内容不是有效线索）
    NOISE_KEYWORDS = [
        # 天气/新闻/资讯
        "天气预报", "天气查询", "新闻", "资讯", "头条", "热搜",
        # 政府公告/公示/政策
        "公告公示", "公示", "政策", "法规", "条例", "办法", "规定",
        "审批", "许可", "备案公示", "招标公告公示",
        # 教育/招聘/考试
        "招聘", "考试", "报名", "招生", "录取", "调剂", "复试",
        # 网站导航/列表页
        "首页", "导航", "大全", "列表", "黄页", "目录", "索引",
        # 无关内容
        "天气", "温度", "降水", "风力", "湿度", "空气质量",
        # 论坛/问答噪音
        "求助", "请问", "谁知道", "有没有人", "推荐一下",
    ]

    # 项目相关正向关键词（必须至少匹配一个才认为是有效项目）
    PROJECT_POSITIVE_KEYWORDS = [
        "新建", "在建", "施工", "建设", "改造", "扩建", "翻新",
        "交付", "交房", "竣工", "开工", "开盘", "封顶",
        "招标", "采购", "比选", "磋商", "询价", "竞标",
        "项目", "工程", "地块", "小区", "园区", "厂区",
        "车棚", "遮阳棚", "雨棚", "膜结构", "光伏", "充电桩",
        "安装", "定制", "报价", "测量", "设计", "施工队",
    ]

    # 有效手机号正则
    MOBILE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

    # 有效座机正则（带区号）
    LANDLINE_PATTERN = re.compile(r"^0\d{2,3}[-]?\d{7,8}$")

    @staticmethod
    def extract_phone(text: str) -> str:
        """从文本中提取有效电话号码"""
        if not text:
            return ""

        # 优先提取手机号
        mobile = re.search(r"1[3-9]\d{9}", text)
        if mobile:
            phone = mobile.group()
            if DataCleaner.validate_phone(phone):
                return phone

        # 其次提取座机号
        landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
        if landline:
            phone = landline.group()
            if DataCleaner.validate_phone(phone):
                return phone

        return ""

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证电话号码是否有效"""
        if not phone:
            return False
        result = PhoneVerifier.validate_phone_format(phone)
        return result["valid"]

    @staticmethod
    def clean_company_name(name: str) -> str:
        """清洗公司名称"""
        if not name:
            return ""
        name = name.strip()
        # 去除前后特殊字符
        name = re.sub(r"^[\s\-_—–·.]+|[\s\-_—–·.]+$", "", name)
        # 去除多余空格
        name = re.sub(r"\s+", " ", name)
        # 截断过长的名称
        if len(name) > 100:
            name = name[:100]
        return name

    @staticmethod
    def clean_address(address: str) -> str:
        """清洗地址"""
        if not address:
            return ""
        address = address.strip()
        # 去除多余空格
        address = re.sub(r"\s+", " ", address)
        # 截断过长的地址
        if len(name) > 300:
            address = address[:300]
        return address

    @staticmethod
    def normalize_area(area: str) -> str:
        """标准化区域名称"""
        if not area:
            return area
        a = area.strip()
        # 去除尾部噪音（数字、破折号、问号）
        a = re.sub(r'[\d\?\-\u2014\u2013\s]+$', '', a)
        # 去除城市后缀
        city_suffixes = ['武汉市', '咸宁市', '宜昌市', '十堰市', '孝感市',
                        '荆州市', '黄冈市', '襄阳市']
        for cs in city_suffixes:
            if a == cs:
                a = a[:-1]
        # 修复已知错别字
        typo_map = {'武汉硣口': '武汉硚口'}
        a = typo_map.get(a, a)
        if not a or a == '?':
            return ''
        return a

    @staticmethod
    def is_competitor(name: str, text: str = "") -> bool:
        """检查是否为竞争对手"""
        combined = f"{name} {text}".lower()
        for kw in DataCleaner.COMPETITOR_KEYWORDS:
            if kw in combined:
                return True
        return False

    @staticmethod
    def is_noise(name: str, text: str = "") -> bool:
        """检查是否为噪音内容"""
        combined = f"{name} {text}".lower()
        for kw in DataCleaner.NOISE_KEYWORDS:
            if kw in combined:
                return True
        return False

    @staticmethod
    def has_project_keyword(text: str) -> bool:
        """检查是否包含项目相关关键词"""
        if not text:
            return False
        text = text.lower()
        for kw in DataCleaner.PROJECT_POSITIVE_KEYWORDS:
            if kw in text:
                return True
        return False

    @staticmethod
    def is_duplicate(phone: str = None, name: str = None) -> bool:
        """检查是否重复"""
        if phone:
            existing = Lead.query.filter_by(phone=phone).first()
            if existing:
                return True
        if name:
            existing = Lead.query.filter_by(name=name).first()
            if existing:
                return True
        return False

    @staticmethod
    def clean_lead_data(data: dict) -> dict:
        """清洗线索数据，返回清洗后的数据或None（如果无效）"""
        # 1. 清洗名称
        name = DataCleaner.clean_company_name(data.get("name", ""))
        if not name:
            return None
        data["name"] = name

        # 2. 提取并验证电话
        phone = data.get("phone", "")
        if phone:
            phone = DataCleaner.extract_phone(phone)
        data["phone"] = phone

        # 3. 清洗地址
        address = data.get("address", "")
        if address:
            address = DataCleaner.clean_address(address)
        data["address"] = address

        # 4. 标准化区域
        area = data.get("area", "")
        if area:
            area = DataCleaner.normalize_area(area)
        data["area"] = area

        # 5. 检查竞品
        if DataCleaner.is_competitor(name, data.get("demand_desc", "")):
            logger.debug(f"Filtered competitor: {name}")
            return None

        # 6. 检查噪音
        if DataCleaner.is_noise(name, data.get("demand_desc", "")):
            logger.debug(f"Filtered noise: {name}")
            return None

        # 7. 没有电话的线索直接过滤（除非是招标/政府数据等高价值来源）
        high_value_sources = ["招标平台", "gov_data", "tianyancha", "qichacha", "import"]
        if not phone and data.get("source") not in high_value_sources:
            logger.debug(f"Filtered no-phone lead: {name}")
            return None

        # 8. 检查重复
        if phone and DataCleaner.is_duplicate(phone=phone):
            logger.debug(f"Filtered duplicate phone: {phone}")
            return None
        if DataCleaner.is_duplicate(name=name):
            logger.debug(f"Filtered duplicate name: {name}")
            return None

        return data

    @staticmethod
    def clean_and_save(data: dict) -> bool:
        """清洗并保存单条线索，返回是否成功保存"""
        cleaned = DataCleaner.clean_lead_data(data)
        if not cleaned:
            return False

        try:
            lead = Lead(**cleaned)
            db.session.add(lead)
            db.session.flush()
            return True
        except Exception as e:
            logger.debug(f"Save failed: {e}")
            return False

    @staticmethod
    def clean_and_save_batch(leads_data: list) -> int:
        """批量清洗并保存线索，返回成功保存的数量"""
        saved = 0
        for data in leads_data:
            if DataCleaner.clean_and_save(data):
                saved += 1
        if saved > 0:
            db.session.commit()
        return saved
