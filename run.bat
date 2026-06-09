@echo off
chcp 65001 >nul
call venv\Scripts\activate.bat
echo 启动数字营销系统...
echo 浏览器访问: http://localhost:5000
python main.py --port 5000
