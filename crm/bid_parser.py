# -*- coding: utf-8 -*-
"""Bid notice parser - extract structured info from bidding pages."""
import re
import requests
from bs4 import BeautifulSoup
from loguru import logger


def parse_bid_page(url: str) -> dict:
    result = {
        "url": url, "project_name": "", "budget": "", "budget_num": 0,
        "purchaser": "", "purchaser_contact": "", "purchaser_address": "",
        "agency": "", "bid_deadline": "", "open_time": "", "doc_period": "",
        "location": "", "requirements": "", "raw_text": "", "error": "",
    }
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html", "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        content_el = soup.select_one(".vF_detail_content, .vT_detail_main, .content, .article, .main-content, #content, .detail")
        if not content_el:
            content_el = soup.select_one("body")
        text = content_el.get_text(separator="\n", strip=True)
        result["raw_text"] = text[:3000]

        result["project_name"] = _extract(text, [
            r"项目名称[：:]\s*(.+?)(?:\n|$)",
            r"采购项目[：:]\s*(.+?)(?:\n|$)",
            r"招标项目[：:]\s*(.+?)(?:\n|$)",
        ])
        budget_text = _extract(text, [
            r"预算金额[：:]\s*(.+?)(?:\n|$)",
            r"采购预算[：:]\s*(.+?)(?:\n|$)",
            r"合同.*?估算.*?([\d,.]+\s*(?:万?元)?)",
            r"控制价[：:]\s*(.+?)(?:\n|$)",
        ])
        result["budget"] = budget_text
        result["budget_num"] = _parse_budget(budget_text)

        result["purchaser"] = _extract(text, [
            r"采购人[：:]\s*(.+?)(?:\n|$)",
            r"招标人[：:]\s*(.+?)(?:\n|$)",
            r"建设单位[：:]\s*(.+?)(?:\n|$)",
        ])
        result["purchaser_contact"] = _extract(text, [
            r"联系方式[：:]\s*(.+?)(?:\n|$)",
            r"联系电话[：:]\s*(.+?)(?:\n|$)",
            r"电话[：:]\s*(\d[\d\-]+\d)",
        ])
        result["purchaser_address"] = _extract(text, [r"地址[：:]\s*(.+?)(?:\n|$)"])
        result["agency"] = _extract(text, [
            r"代理机构[：:]\s*(.+?)(?:\n|$)",
            r"招标代理[：:]\s*(.+?)(?:\n|$)",
        ])
        result["bid_deadline"] = _extract(text, [
            r"(?:投标|递交|响应|报价).*?截止.*?(?:时间|日期)[：:]\s*(.+?)(?:\n|$)",
            r"(?:投标|递交).*?截止[：:]\s*(.+?)(?:\n|$)",
        ])
        result["open_time"] = _extract(text, [
            r"^\s*开标时间[：:]\s*(.+?)(?:\n|$)",
            r"^\s*开启时间[：:]\s*(.+?)(?:\n|$)",
            r"^\s*评审时间[：:]\s*(.+?)(?:\n|$)",
        ], multiline=True)
        result["doc_period"] = _extract(text, [
            r"(?:获取|下载).*?招标文件.*?(?:时间|期限)[：:]\s*(.+?)(?:\n|$)",
        ])
        result["location"] = _extract(text, [
            r"项目.*?地(?:点|址)[：:]\s*(.+?)(?:\n|$)",
            r"实施地点[：:]\s*(.+?)(?:\n|$)",
        ])
        reqs = []
        for pat, label in [
            (r"资质要求[：:]\s*(.+?)(?:\n\n|\n(?=[\u4e00-\u9fa5]{2,}[：:]))", "\u8d44\u8d28\u8981\u6c42"),
            (r"投标人资格[：:]\s*(.+?)(?:\n\n|\n(?=[\u4e00-\u9fa5]{2,}[：:]))", "\u8d44\u683c\u8981\u6c42"),
            (r"工期[：:]\s*(.+?)(?:\n|$)", "\u5de5\u671f"),
            (r"交货期[：:]\s*(.+?)(?:\n|$)", "\u4ea4\u8d27\u671f"),
            (r"保修期[：:]\s*(.+?)(?:\n|$)", "\u4fdd\u4fee\u671f"),
            (r"付款方式[：:]\s*(.+?)(?:\n\n|\n(?=[\u4e00-\u9fa5]{2,}[：:]))", "\u4ed8\u6b3e\u65b9\u5f0f"),
        ]:
            m = re.search(pat, text)
            if m:
                val = m.group(1).strip()[:200]
                if val:
                    reqs.append(f"{label}: {val}")
        result["requirements"] = "\n".join(reqs)
        phones = re.findall(r"1[3-9]\d{9}", text)
        landlines = re.findall(r"0\d{2,3}[-]?\d{7,8}", text)
        all_phones = list(set(phones + landlines))
        if all_phones and not result["purchaser_contact"]:
            result["purchaser_contact"] = ", ".join(all_phones[:3])
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Bid parse failed: {e}")
    return result


def _parse_budget(text: str) -> float:
    """Parse budget text into a number in 万元."""
    if not text:
        return 0
    m = re.search(r"([\d,.]+)\s*万", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except:
            pass
    m = re.search(r"([\d,.]+)\s*元", text)
    if m:
        try:
            return float(m.group(1).replace(",", "")) / 10000
        except:
            pass
    m = re.search(r"([\d,.]+)", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except:
            pass
    return 0


def _extract(text, patterns, multiline=False):
    flags = re.MULTILINE if multiline else 0
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            val = re.sub(r"\s+", " ", m.group(1).strip())[:200]
            if val and len(val) > 1:
                return val
    return ""


def format_bid_info(info):
    lines = []
    for key, label in [
        ("project_name", "\u9879\u76ee"), ("budget", "\u9884\u7b97"),
        ("purchaser", "\u91c7\u8d2d\u4eba"), ("purchaser_contact", "\u8054\u7cfb\u65b9\u5f0f"),
        ("purchaser_address", "\u5730\u5740"), ("agency", "\u4ee3\u7406\u673a\u6784"),
        ("bid_deadline", "\u6295\u6807\u622a\u6b62"), ("open_time", "\u5f00\u6807\u65f6\u95f4"),
        ("doc_period", "\u6587\u4ef6\u83b7\u53d6"), ("location", "\u5b9e\u65bd\u5730\u70b9"),
    ]:
        if info.get(key):
            lines.append(f"{label}: {info[key]}")
    if info.get("requirements"):
        lines.append(f"\u786c\u6027\u6761\u4ef6:\n{info['requirements']}")
    return "\n".join(lines)
