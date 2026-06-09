# -*- coding: utf-8 -*-
"""
Douyin Scraper v3 - 自动搜索膜结构关键词，抓取评论区意向用户
避开反爬：使用独立Chrome配置，模拟真实用户行为
"""
import sys, io, time, re, os, json, random
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dashboard.app import app
from crm.models import db, Lead
from crm.scoring import score_lead

# 搜索关键词
SEARCH_KEYWORDS = [
    "膜结构车棚",
    "停车棚安装",
    "遮阳棚定制",
    "充电桩车棚",
    "雨棚安装",
]

# 意向信号词
INTEREST_KEYWORDS = [
    "怎么联系", "联系方式", "电话", "微信", "私信",
    "多少钱", "价格", "报价", "贵不贵",
    "在哪", "地址", "哪里", "哪个城市",
    "想", "需要", "求", "找", "要",
    "安装", "定制", "定做", "做",
    "推荐", "有吗", "可以吗",
]

def main():
    # 使用独立的Chrome配置，避免与用户浏览器冲突
    profile_dir = "C:\\temp\\douyin_scraper_profile"
    os.makedirs(profile_dir, exist_ok=True)
    
    opts = Options()
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-extensions")
    
    # 隐藏自动化特征
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    all_comments = []
    
    try:
        # 打开抖音
        print("打开抖音...")
        driver.get("https://www.douyin.com")
        time.sleep(5)
        
        # 检查登录状态
        body = driver.find_element(By.TAG_NAME, "body").text
        if "登录" in body[:800] or "扫码" in body[:800]:
            print("\n" + "=" * 50)
            print("请在浏览器窗口中扫码登录抖音")
            print("登录后脚本会自动继续（最多等3分钟）")
            print("=" * 50 + "\n")
            
            logged_in = False
            for i in range(36):
                time.sleep(5)
                try:
                    body2 = driver.find_element(By.TAG_NAME, "body").text
                    if "登录" not in body2[:800] and "扫码" not in body2[:800]:
                        logged_in = True
                        print("登录成功！")
                        break
                    if i % 6 == 0:
                        print("等待登录... (%d秒)" % (i * 5))
                except:
                    pass
            
            if not logged_in:
                print("登录超时")
                driver.quit()
                return
        
        # 搜索每个关键词
        for keyword in SEARCH_KEYWORDS:
            print("\n" + "=" * 40)
            print("搜索: %s" % keyword)
            
            try:
                # 进入搜索页
                search_url = "https://www.douyin.com/search/%s?type=video" % keyword
                driver.get(search_url)
                time.sleep(5)
                
                # 等待视频列表加载
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "a"))
                    )
                except:
                    print("  页面加载超时")
                    continue
                
                # 模拟滚动加载更多
                for _ in range(3):
                    driver.execute_script("window.scrollBy(0, 800);")
                    time.sleep(1)
                
                # 收集视频链接
                links = driver.find_elements(By.TAG_NAME, "a")
                video_urls = []
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "/video/" in href and href not in video_urls:
                        video_urls.append(href)
                
                print("  找到 %d 个视频" % len(video_urls))
                
                # 处理前5个视频
                for vid_idx, video_url in enumerate(video_urls[:5]):
                    try:
                        # 随机延迟，模拟人类行为
                        time.sleep(random.uniform(2, 4))
                        
                        # 打开视频
                        driver.get(video_url)
                        time.sleep(4)
                        
                        # 滚动加载评论
                        for _ in range(5):
                            driver.execute_script("window.scrollBy(0, 500);")
                            time.sleep(1)
                        
                        # 获取页面源码（比text更完整）
                        page_source = driver.page_source
                        
                        # 也获取文本
                        page_text = driver.find_element(By.TAG_NAME, "body").text
                        
                        # 提取评论
                        comments = extract_comments_from_text(page_text, keyword)
                        
                        if comments:
                            all_comments.extend(comments)
                            print("  视频%d: 找到 %d 条意向评论" % (vid_idx + 1, len(comments)))
                            for c in comments[:3]:
                                print("    [%s] %s" % (c["username"][:10], c["comment"][:40]))
                        else:
                            print("  视频%d: 无意向评论" % (vid_idx + 1))
                    
                    except Exception as e:
                        print("  视频%d 失败: %s" % (vid_idx + 1, str(e)[:30]))
                    
                    # 返回搜索页
                    driver.get(search_url)
                    time.sleep(3)
            
            except Exception as e:
                print("  搜索失败: %s" % str(e)[:30])
            
            time.sleep(random.uniform(3, 5))
        
        # 保存结果
        if all_comments:
            # 去重
            unique_comments = deduplicate_comments(all_comments)
            print("\n" + "=" * 40)
            print("共找到 %d 条意向评论（去重后 %d 条）" % (len(all_comments), len(unique_comments)))
            
            # 保存到数据库
            saved = save_douyin_leads(unique_comments)
            print("保存 %d 条线索到数据库" % saved)
            
            # 打印结果
            print("\n=== 意向用户列表 ===")
            for c in unique_comments[:20]:
                print("[%s] %s: %s" % (c["keyword"][:10], c["username"][:15], c["comment"][:50]))
        else:
            print("\n未找到意向评论")
    
    finally:
        driver.quit()

def extract_comments_from_text(page_text, keyword):
    """从页面文本中提取评论"""
    comments = []
    lines = page_text.split("\n")
    
    # 抖音评论区的文本格式通常是：
    # 用户名
    # 评论内容
    # 点赞数
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 检查是否包含意向关键词
        if any(kw in line for kw in INTEREST_KEYWORDS):
            # 获取用户名（通常是前一行）
            username = lines[i-1].strip() if i > 0 else "未知用户"
            
            # 过滤掉太短或太长的内容
            if 5 < len(line) < 200:
                # 过滤掉明显不是评论的内容
                skip_keywords = ["登录", "注册", "关注", "点赞", "分享", "举报", "首页", "搜索"]
                if not any(kw in line for kw in skip_keywords):
                    comments.append({
                        "username": username[:30],
                        "comment": line[:200],
                        "keyword": keyword,
                    })
        
        i += 1
    
    return comments

def deduplicate_comments(comments):
    """去重"""
    seen = set()
    unique = []
    for c in comments:
        key = c["username"] + c["comment"][:20]
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique

def save_douyin_leads(comments):
    """保存到数据库"""
    with app.app_context():
        saved = 0
        for item in comments:
            try:
                # 检查是否已存在
                existing = Lead.query.filter(
                    Lead.notes.contains(item["comment"][:30])
                ).first()
                if existing:
                    continue
                
                lead = Lead(
                    name="抖音-%s" % item["username"][:20],
                    source="抖音",
                    phone="",
                    demand_desc="[抖音意向] %s" % item["comment"][:200],
                    notes="搜索词: %s\n用户: %s\n评论: %s" % (
                        item["keyword"], item["username"], item["comment"]
                    ),
                    customer_type="问答咨询",
                    area="未知",
                )
                db.session.add(lead)
                saved += 1
            except:
                continue
        
        db.session.commit()
        
        # 评分
        for lead in Lead.query.filter_by(source="抖音", total_score=0).all():
            score_lead(lead)
        db.session.commit()
        
        return saved

if __name__ == "__main__":
    main()
