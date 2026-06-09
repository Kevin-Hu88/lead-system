@echo off
chcp 65001 >nul
echo ================================
echo   数字营销系统 - 一键安装
echo ================================

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 创建虚拟环境
if not exist "venv" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

:: 激活并安装依赖
echo [2/3] 安装依赖...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: 初始化数据库
echo [3/3] 初始化数据库...
python -c "from dashboard.app import app; from crm.database import init_db; init_db(app)"

echo.
echo ================================
echo   安装完成！
echo   运行: run.bat
echo ================================
pause
