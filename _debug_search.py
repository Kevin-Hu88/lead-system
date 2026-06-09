# -*- coding: utf-8 -*-
"""Debug search - see raw results"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
from urllib.parse import quote
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

ua = UserAgent()
session = requests.Session()

keyword = "武汉 车棚 安装 电话"

# Test Bing
print("=== Bing ===")
try:
    url = f"https://cn.bing.com/search?q={quote(keyword)}&first=1"
    headers = {"User-Agent": ua.random}
    resp = session.get(url, headers=headers, timeout=15)
    print("Status:", resp.status_code)
    print("Content length:", len(resp.text))
    
    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.select("#b_results .b_algo")
    print("Results found:", len(items))
    
    for i, item in enumerate(items[:3]):
        title_el = item.select_one("h2 a")
        desc_el = item.select_one(".b_caption p, .b_algoSlug")
        title = title_el.get_text(strip=True) if title_el else ""
        desc = desc_el.get_text(strip=True) if desc_el else ""
        
        # Check for phone
        text = f"{title} {desc}"
        phone = re.search(r"1[3-9]\d{9}", text)
        
        print("\n  Result %d:" % (i+1))
        print("    Title:", title[:60])
        print("    Desc:", desc[:80])
        print("    Phone:", phone.group() if phone else "(none)")
except Exception as e:
    print("Error:", e)

# Test Baidu
print("\n=== Baidu ===")
try:
    url = f"https://www.baidu.com/s?wd={quote(keyword)}&rn=10"
    headers = {"User-Agent": ua.random}
    resp = session.get(url, headers=headers, timeout=15)
    print("Status:", resp.status_code)
    print("Content length:", len(resp.text))
    
    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.select(".result, .c-container")
    print("Results found:", len(items))
    
    for i, item in enumerate(items[:3]):
        title_el = item.select_one("h3 a, .t a")
        desc_el = item.select_one(".c-abstract, .c-span-last")
        title = title_el.get_text(strip=True) if title_el else ""
        desc = desc_el.get_text(strip=True) if desc_el else ""
        
        text = f"{title} {desc}"
        phone = re.search(r"1[3-9]\d{9}", text)
        
        print("\n  Result %d:" % (i+1))
        print("    Title:", title[:60])
        print("    Desc:", desc[:80])
        print("    Phone:", phone.group() if phone else "(none)")
except Exception as e:
    print("Error:", e)
