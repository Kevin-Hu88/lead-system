# -*- coding: utf-8 -*-
"""Harvester scheduler - all harvesters with timeout and parallel execution"""
import time
import random
import threading
from datetime import datetime
from loguru import logger
from crm.models import db, TaskLog

# 单个采集器超时时间（秒）
HARVESTER_TIMEOUT = 180  # 3分钟


def _run_single_harvester(name, module_path, class_name, app):
    """执行单个采集器"""
    try:
        with app.app_context():
            module = __import__(module_path, fromlist=[class_name])
            harvester_cls = getattr(module, class_name)
            harvester = harvester_cls()
            count = harvester.harvest()
            return name, count, None
    except Exception as e:
        return name, 0, str(e)


def _run_with_timeout(name, module_path, class_name, app, timeout=HARVESTER_TIMEOUT):
    """带超时的采集器执行"""
    result = [None, None, None]  # [name, count, error]

    def _worker():
        result[0], result[1], result[2] = _run_single_harvester(name, module_path, class_name, app)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        logger.warning(f"{name} 超时({timeout}秒)，跳过")
        return name, 0, f"超时({timeout}秒)"

    if result[2]:
        raise Exception(result[2])

    return result[0], result[1], None


def run_harvesters(app):
    with app.app_context():
        log = TaskLog(task_name="线索采集", status="running")
        db.session.add(log)
        db.session.commit()
        total_found = 0
        total_errors = 0
        details = []

        # 分组采集
        groups = [
            ("高价值", [
                ("招标平台", "lead_harvester.bid_harvester", "BidHarvester"),
                ("政府公开数据", "lead_harvester.gov_data_harvester", "GovDataHarvester"),
                ("建筑工程平台", "lead_harvester.hbcic_harvester", "HbciCHarvester"),
                ("商品房项目", "lead_harvester.spfxm_harvester", "SpfxmHarvester"),
                ("住建局公告", "lead_harvester.housing_bureau_harvester", "HousingBureauHarvester"),
                ("项目平台", "lead_harvester.project_harvester", "ProjectHarvester"),
            ]),
            ("企业信息", [
                ("企业信息", "lead_harvester.enterprise_harvester", "EnterpriseHarvester"),
                ("天眼查/企查查", "lead_harvester.tianyancha_harvester", "TianyanchaHarvester"),
                ("行业垂直平台", "lead_harvester.industry_harvester", "IndustryHarvester"),
            ]),
            ("补充", [
                ("在建工程", "lead_harvester.construction_harvester", "ConstructionHarvester"),
                ("搜索引擎", "lead_harvester.search_harvester", "SearchHarvester"),
                ("分类信息", "lead_harvester.classified_harvester", "ClassifiedHarvester"),
                ("论坛问答", "lead_harvester.forum_harvester", "ForumHarvester"),
            ]),
            ("百度地图", [
                ("百度地图", "lead_harvester.map_harvester", "MapHarvester"),
            ]),
        ]

        for group_name, harvesters in groups:
            logger.info(f"=== 开始采集: {group_name}组 ({len(harvesters)}个采集器) ===")

            for name, module_path, class_name in harvesters:
                try:
                    logger.info(f"开始采集: {name}")
                    result_name, count, error = _run_with_timeout(name, module_path, class_name, app)
                    if error:
                        details.append(f"{result_name}: {error}")
                        total_errors += 1
                    else:
                        total_found += count
                        details.append(f"{result_name}: {count}条线索")
                        if count > 0:
                            logger.info(f"{result_name} 采集完成: {count}条线索")
                except Exception as e:
                    details.append(f"{name}: 失败({str(e)[:50]})")
                    total_errors += 1
                    logger.error(f"{name} 采集失败: {e}")

        log.status = "success" if total_errors == 0 else "partial"
        log.leads_found = total_found
        log.errors = total_errors
        log.detail = "\n".join(details)
        log.finished_at = datetime.now()
        db.session.commit()
        logger.info(f"采集完成: 共{total_found}条线索, {total_errors}个错误")
        return total_found
