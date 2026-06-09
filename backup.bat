@echo off
chcp 65001 >nul
echo ================================
echo   备份数字营销系统
echo ================================

set BACKUP_DIR=%USERPROFILE%\Desktop\数字营销备份_%date:~0,4%%date:~5,2%%date:~8,2%

echo 备份到: %BACKUP_DIR%
xcopy "%~dp0" "%BACKUP_DIR%" /E /I /H /Y /Q /EXCLUDE:%~dp0backup_exclude.txt

echo.
echo 备份完成: %BACKUP_DIR%
echo 包含: 源码 + 数据库 + 配置
echo 不含: venv、__pycache__、日志
pause
