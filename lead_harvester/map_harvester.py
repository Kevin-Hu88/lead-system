# -*- coding: utf-8 -*-
"""
百度地图Place API采集器 - 通过官方POI接口搜索潜在客户

工作原理：
  不搜"车棚"（那是竞争对手），而是搜"小区""工厂""停车场"等目标场所，
  这些场所是最可能需要安装车棚/遮阳棚的客户。

API文档：https://lbsyun.baidu.com/index.php?title=webapi/guide/webservice-placeapi

前置条件：
  1. 去 https://lbsyun.baidu.com/ 注册账号
  2. 控制台 -> 创建应用 -> 服务端(SN校验方式不用选) -> 获取AK
  3. 在 config/settings.py 中填写 BAIDU_MAP_AK
"""
import re
import time
import random
import requests
from loguru import logger

from config import settings
from crm.models import db, Lead
from lead_harvester.data_cleaner import DataCleaner


class MapHarvester:
    """百度地图POI采集器"""

    def __init__(self):
        self.ak = settings.BAIDU_MAP_AK
        self.api_url = "https://api.map.baidu.com/place/v2/search"
        self.areas = settings.TARGET_AREAS
        self.quota_exceeded = False  # API配额超限标志
        # 使用配置中的目标客户类型
        self.targets = getattr(settings, 'MAP_SEARCH_TARGETS', [
            ("\u5c0f\u533a", "\u7269\u4e1a"),
            ("\u5de5\u4e1a\u56ed", "\u5de5\u5382"),
            ("\u505c\u8f66\u573a", "\u505c\u8f66\u573a"),
            ("4S\u5e97", "4S\u5e97"),
            ("\u5b66\u6821", "\u5b66\u6821"),
            ("\u533b\u9662", "\u533b\u9662"),
        ])

    @staticmethod
    def normalize_area(area: str) -> str:
        """Clean area names: strip noise, fix encoding, normalize city suffix."""
        import re as _re
        if not area:
            return area
        a = area.strip()
        # Remove trailing non-CJK noise (numbers, dashes, question marks)
        a = _re.sub(r'[\d\?\-\u2014\u2013\s]+$', '', a)
        # Remove trailing city suffix for consistency
        city_suffixes = ['武汉市', '咸宁市', '宜昌市',
                         '十堰市', '孝感市', '荆州市',
                         '黄冈市', '襄阳市']
        for cs in city_suffixes:
            if a == cs:
                a = a[:-1]
        # Fix known typos
        typo_map = {'武汉硣口': '武汉硚口'}
        a = typo_map.get(a, a)
        if not a or a == '?':
            return ''
        return a

    def harvest(self) -> int:
        """执行采集，返回新发现的线索数"""
        if not self.ak:
            logger.warning("\u767e\u5ea6\u5730\u56feAK\u672a\u914d\u7f6e\uff0c\u8df3\u8fc7\u5730\u56fe\u91c7\u96c6\u3002\u8bf7\u5728 config/settings.py \u4e2d\u586b\u5199 BAIDU_MAP_AK")
            return 0

        total = 0
        for area in self.areas:
            # 每个区域开始前检查配额
            if self.quota_exceeded:
                logger.info(f"百度API配额已超限，跳过剩余区域")
                break
            for keyword, customer_type in self.targets:
                # 每个关键词前检查配额
                if self.quota_exceeded:
                    break
                try:
                    leads = self._search_poi(area, keyword, customer_type)
                    count = self._save_leads(leads)
                    total += count
                    if count > 0:
                        logger.info(f"[{area}] {keyword}: \u53d1\u73b0 {count} \u4e2a{customer_type}\u7c7b\u5ba2\u6237")
                    time.sleep(random.uniform(
                        settings.REQUEST_DELAY_MIN,
                        settings.REQUEST_DELAY_MAX
                    ))
                except Exception as e:
                    logger.error(f"\u5730\u56fe\u91c7\u96c6\u5931\u8d25 [{area}/{keyword}]: {e}")
        return total

    def _search_poi(self, area: str, keyword: str, customer_type: str) -> list:
        """
        调用百度地图Place API v2.0 检索POI

        API: GET https://api.map.baidu.com/place/v2/search
        参数:
          query   - 搜索关键词
          region  - 区域（城市名或区域名）
          ak      - API密钥
          output  - json
          scope   - 1=基本, 2=详细（含电话等）
          page_size - 每页条数(最大20)
          page_num  - 页码(从0开始)
        """
        # 如果已检测到配额超限，直接返回空
        if self.quota_exceeded:
            return []

        results = []
        max_pages = getattr(settings, 'MAX_PAGES_PER_SOURCE', 3)

        for page in range(max_pages):
            try:
                params = {
                    "query": keyword,
                    "region": area,
                    "ak": self.ak,
                    "output": "json",
                    "scope": 2,  # 详细信息，包含电话号码
                    "page_size": 20,
                    "page_num": page,
                }

                resp = requests.get(self.api_url, params=params, timeout=15)
                data = resp.json()

                # 检查API返回状态
                status = data.get("status", -1)
                if status != 0:
                    msg = data.get("message", "\u672a\u77e5\u9519\u8bef")
                    logger.error(f"\u767e\u5ea6API\u9519\u8bef [{area}/{keyword}]: status={status}, {msg}")
                    break

                pois = data.get("results", [])
                if not pois:
                    break  # \u6ca1\u6709\u66f4\u591a\u7ed3\u679c

                for poi in pois:
                    lead = self._parse_poi(poi, area, keyword, customer_type)
                    if lead:
                        results.append(lead)

                # 如果返回不足20条，说明没有下一页了
                if len(pois) < 20:
                    break

                time.sleep(0.5)  # 翻页间隔

            except requests.exceptions.RequestException as e:
                logger.error(f"API\u8bf7\u6c42\u5931\u8d25 [{area}/{keyword}] page={page}: {e}")
                break

        return results

    def _parse_poi(self, poi: dict, area: str, keyword: str, customer_type: str) -> dict:
        """解析百度地图POI结果"""
        try:
            name = poi.get("name", "").strip()
            if not name:
                return None

            address = poi.get("address", "").strip()
            # scope=2 时会返回 telephone 字段
            phone_raw = poi.get("telephone", "").strip()

            # 提取有效电话号码（手机号或座机号）
            phone = self._extract_phone(phone_raw)

            # 获取坐标
            location = poi.get("location", {})
            lat = location.get("lat", "")
            lng = location.get("lng", "")

            # 获取详细信息
            detail_info = poi.get("detail_info", {})
            tag = detail_info.get("tag", "")
            overall_rating = detail_info.get("overall_rating", "")
            cost = detail_info.get("cost", "")

            # 尝试从详情中再找一次电话
            if not phone:
                detail_phone = detail_info.get("telephone", "")
                phone = self._extract_phone(detail_phone)

            return {
                "name": name[:100],
                "phone": phone,
                "address": address[:300],
                "source": "baidu_map",
                "area": self.normalize_area(area),
                "customer_type": customer_type,
                "product_interest": keyword,
                "demand_desc": f"POI\u7c7b\u578b: {tag}" if tag else "",
            }
        except Exception as e:
            logger.debug(f"\u89e3\u6790POI\u5931\u8d25: {e}")
            return None

    @staticmethod
    def _clean_poi_tag(tag: str) -> str:
        """Clean garbled POI tags from Baidu API."""
        if not tag:
            return ""
        parts = tag.split(";")
        meaningful = [p.strip() for p in parts if len(p.strip()) >= 2]
        if meaningful:
            return meaningful[-1]
        cleaned = re.sub(r'^[^\u4e00-\u9fff]+', '', tag).strip()
        return cleaned if len(cleaned) >= 2 else tag

    def _extract_phone(self, text: str) -> str:
        """从文本中提取有效电话号码"""
        if not text:
            return ""
        # 手机号
        mobile = re.search(r"1[3-9]\d{9}", text)
        if mobile:
            return mobile.group()
        # 座机号 (区号-号码)
        landline = re.search(r"0\d{2,3}[-]?\d{7,8}", text)
        if landline:
            return landline.group()
        return ""

    def _save_leads(self, leads: list) -> int:
        """保存线索到数据库，自动去重"""
        saved = 0
        for data in leads:
            try:
                # 基于电话去重
                if data.get("phone"):
                    existing = Lead.query.filter_by(phone=data["phone"]).first()
                    if existing:
                        continue
                # 基于名称去重
                if data.get("name"):
                    existing = Lead.query.filter_by(name=data["name"]).first()
                    if existing:
                        continue
                lead = Lead(**data)
                db.session.add(lead)
                saved += 1
            except Exception as e:
                logger.debug(f"\u4fdd\u5b58\u7ebf\u7d22\u5931\u8d25: {e}")
        if saved > 0:
            db.session.commit()
        return saved
