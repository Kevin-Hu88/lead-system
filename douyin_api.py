# -*- coding: utf-8 -*-
"""
Douyin Scraper v5 - 用 Edge cookies 直接调用抖音 API
解密 Edge 加密 cookie，无需 win32crypt
"""
import sys, io, os, sqlite3, shutil, json, base64, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import ctypes, ctypes.wintypes

def get_edge_key():
    """获取 Edge 的加密密钥"""
    local_state_path = os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data\Local State"
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    # Remove "DPAPI" prefix
    encrypted_key = encrypted_key[5:]
    
    # Decrypt using DPAPI
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    
    blob_in = DATA_BLOB(len(encrypted_key), ctypes.create_string_buffer(encrypted_key, len(encrypted_key)))
    blob_out = DATA_BLOB()
    
    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        key = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return key
    return None

def decrypt_cookie_value(encrypted_value, key):
    """解密 cookie 值"""
    if encrypted_value[:3] == b'v10' or encrypted_value[:3] == b'v20':
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:-16]
        tag = encrypted_value[-16:]
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(nonce, encrypted_value[3:], None).decode()
        except:
            return ""
    return ""

def get_douyin_cookies():
    """提取抖音 cookies"""
    cookie_db = os.path.expanduser("~") + r"\AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies"
    temp_db = "C:\\temp\\edge_cookies.db"
    os.makedirs("C:\\temp", exist_ok=True)
    shutil.copy2(cookie_db, temp_db)
    
    key = get_edge_key()
    if not key:
        print("Failed to get encryption key")
        return {}
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%douyin%'")
    
    cookies = {}
    for name, enc_value in cursor.fetchall():
        if enc_value:
            value = decrypt_cookie_value(enc_value, key)
            if value:
                cookies[name] = value
    
    conn.close()
    os.remove(temp_db)
    return cookies

# ============================================================
# Main
# ============================================================
sys.path.insert(0, ".")
import requests

print("提取 Edge cookies...")
cookies = get_douyin_cookies()
print("找到 %d 个抖音 cookie" % len(cookies))

if not cookies:
    print("未找到有效 cookie")
    sys.exit(1)

# Key cookies
key_cookies = ["sessionid", "passport_csrf_token", "ttwid", "msToken", "odin_tt"]
print("关键 cookie 状态:")
for k in key_cookies:
    print("  %s: %s" % (k, "OK" if k in cookies else "MISSING"))

# Build session
session = requests.Session()
session.cookies.update(cookies)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.douyin.com/",
})

# ============================================================
# Search videos
# ============================================================
SEARCH_KEYWORDS = ["膜结构车棚", "停车棚安装", "遮阳棚定制", "充电桩车棚"]

INTEREST_KEYWORDS = [
    "怎么联系", "联系方式", "电话", "微信", "私信",
    "多少钱", "价格", "报价", "贵不贵",
    "在哪", "地址", "哪里",
    "想", "需要", "求", "找",
    "安装", "定制", "定做",
    "推荐", "有吗",
]

all_comments = []

for keyword in SEARCH_KEYWORDS:
    print("\n搜索: %s" % keyword)
    
    try:
        # 先访问搜索页获取 token
        session.get("https://www.douyin.com/", timeout=10)
        time.sleep(1)
        
        search_url = "https://www.douyin.com/aweme/v1/web/search/item/"
        params = {
            "keyword": keyword,
            "search_channel": "aweme_video_web",
            "sort_type": 0,
            "publish_time": 0,
            "count": 20,
            "offset": 0,
        }
        
        resp = session.get(search_url, params=params, timeout=15)
        print("Status: %d, Length: %d" % (resp.status_code, len(resp.text)))
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                videos = data.get("data", [])
                print("Found %d videos" % len(videos))
                
                for video in videos[:5]:
                    desc = video.get("desc", "")
                    aweme_id = video.get("aweme_id", "")
                    author = video.get("author", {})
                    author_name = author.get("nickname", "")
                    
                    print("  Video: %s" % desc[:40])
                    
                    if aweme_id:
                        # Get comments
                        cresp = session.get(
                            "https://www.douyin.com/aweme/v1/web/comment/list/",
                            params={"aweme_id": aweme_id, "cursor": 0, "count": 50},
                            timeout=15
                        )
                        
                        if cresp.status_code == 200:
                            cdata = cresp.json()
                            comments = cdata.get("comments", [])
                            
                            for c in comments:
                                text = c.get("text", "")
                                user = c.get("user", {})
                                username = user.get("nickname", "")
                                
                                if any(kw in text for kw in INTEREST_KEYWORDS):
                                    all_comments.append({
                                        "username": username[:30],
                                        "comment": text[:200],
                                        "keyword": keyword,
                                        "video_desc": desc[:100],
                                    })
                                    print("    [意向] %s: %s" % (username[:10], text[:40]))
                        
                        time.sleep(1)
            except json.JSONDecodeError:
                print("  Not JSON: %s" % resp.text[:100])
        else:
            print("  Error: %s" % resp.text[:100])
    
    except Exception as e:
        print("  Error: %s" % str(e)[:50])
    
    time.sleep(2)

# ============================================================
# Save results
# ============================================================
print("\n" + "=" * 50)
print("共找到 %d 条意向评论" % len(all_comments))

if all_comments:
    with open("douyin_leads.json", "w", encoding="utf-8") as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=2)
    
    from dashboard.app import app
    from crm.models import db, Lead
    from crm.scoring import score_lead
    
    with app.app_context():
        saved = 0
        for item in all_comments:
            try:
                existing = Lead.query.filter(Lead.notes.contains(item["comment"][:30])).first()
                if existing:
                    continue
                lead = Lead(
                    name="抖音-%s" % item["username"][:20],
                    source="抖音",
                    demand_desc="[抖音意向] %s" % item["comment"],
                    notes="搜索词: %s\n用户: %s\n评论: %s\n视频: %s" % (
                        item["keyword"], item["username"], item["comment"], item["video_desc"]
                    ),
                    customer_type="问答咨询",
                    area="未知",
                )
                db.session.add(lead)
                saved += 1
            except:
                continue
        db.session.commit()
        
        for lead in Lead.query.filter_by(source="抖音", total_score=0).all():
            score_lead(lead)
        db.session.commit()
        
        print("保存 %d 条线索" % saved)
else:
    print("未找到意向评论")
    print("可能原因: cookies 过期 / API 变化 / 搜索词无结果")
