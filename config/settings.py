"""
系统配置 - 膜结构车棚/遮阳棚自动获客系统
"""
import os
from pathlib import Path

# ============================================================
# 基础路径
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "leads.db"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ============================================================
# Flask 配置
# ============================================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = int(os.getenv("PORT", 5000))
FLASK_DEBUG = False
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-2024")

# ============================================================
# 数据库 - 优先使用环境变量（Render PostgreSQL），否则用本地 SQLite
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Render 提供的 URL 以 postgres:// 开头，SQLAlchemy 需要 postgresql://
    SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ============================================================
# 业务信息
# ============================================================
BUSINESS_NAME = "XX膜结构工程有限公司"
BUSINESS_PHONE = "400-XXX-XXXX"
BUSINESS_WECHAT = "XXXXX"

# ============================================================
# 采集配置
# ============================================================
BAIDU_MAP_AK = os.getenv("BAIDU_MAP_AK", "")
TARGET_AREAS = ["武汉", "武汉江汉", "武汉硚口", "武汉武昌", "武汉洪山", "武汉汉南", "湖北"]
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5

# ============================================================
# 线索评分
# ============================================================
HUMAN_HANDOFF_SCORE = 80

# ============================================================
# 通知配置
# ============================================================
S_LEVEL_INSTANT_NOTIFY = True
DAILY_REPORT_HOUR = 9
DAILY_REPORT_MINUTE = 0

# 微信企业号
WECHAT_WORK_ENABLED = False
WECHAT_CORP_ID = ""
WECHAT_CORP_SECRET = ""
WECHAT_AGENT_ID = ""
DAILY_WECHAT_LIMIT = 100
WECHAT_TEMPLATES = {
    "初次触达": "您好！我们是{company}，专业承接膜结构车棚、遮阳棚工程。电话：{phone}",
}

# Telegram
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# Server酱
SERVERCHAN_KEY = ""

# ============================================================
# 邮件配置
# ============================================================
EMAIL_ENABLED = False
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = ""
SMTP_PASSWORD = ""
EMAIL_FROM_NAME = BUSINESS_NAME
DAILY_EMAIL_LIMIT = 50
EMAIL_SUBJECT_TEMPLATES = {
    "初次触达": "{company} - 膜结构车棚工程服务",
}

# ============================================================
# 短信配置
# ============================================================
SMS_ENABLED = False
SMS_API_URL = ""
SMS_API_KEY = ""
DAILY_SMS_LIMIT = 50
SMS_TEMPLATES = {
    "初次触达": "您好！我们是{company}，专业承接膜结构车棚工程。电话：{phone}",
}

# ============================================================
# 竞品数据
# ============================================================
COMPETITORS_FILE = DATA_DIR / "competitors.json"

# ============================================================
# API Keys
# ============================================================
TIAN_YAN_CHA_KEY = ""
PHONE_CHECK_API_KEY = ""
PHONE_CHECK_API_URL = ""