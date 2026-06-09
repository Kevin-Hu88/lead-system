#!/bin/bash
# 获客系统 - Oracle Cloud 部署脚本
# 在服务器上运行此脚本即可完成部署

set -e

echo "=============================="
echo "  获客系统 - 自动部署"
echo "=============================="

# 1. 更新系统
echo "[1/6] 更新系统..."
sudo apt update && sudo apt upgrade -y

# 2. 安装依赖
echo "[2/6] 安装 Python 和依赖..."
sudo apt install -y python3 python3-pip python3-venv ffmpeg

# 3. 创建部署目录
echo "[3/6] 创建部署目录..."
sudo mkdir -p /opt/lead-system
sudo chown $USER:$USER /opt/lead-system

# 4. 创建虚拟环境
echo "[4/6] 创建虚拟环境..."
cd /opt/lead-system
python3 -m venv venv
source venv/bin/activate

# 5. 安装 Python 包
echo "[5/6] 安装 Python 依赖..."
pip install --upgrade pip
pip install flask flask-cors flask-sqlalchemy apscheduler loguru requests beautifulsoup4 lxml openpyxl psutil Pillow xlsxwriter

# 安装 Playwright
pip install playwright
playwright install chromium
playwright install-deps chromium

# 6. 创建 systemd 服务
echo "[6/6] 配置开机自启..."
sudo tee /etc/systemd/system/lead-system.service > /dev/null <<EOF
[Unit]
Description=Lead Generation System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/lead-system
ExecStart=/opt/lead-system/venv/bin/python main.py --port 5000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable lead-system

echo ""
echo "=============================="
echo "  部署脚本准备完成！"
echo "=============================="
echo ""
echo "接下来："
echo "1. 把项目文件上传到 /opt/lead-system/"
echo "2. 运行: sudo systemctl start lead-system"
echo "3. 访问: http://服务器IP:5000"