@echo off
chcp 65001 >nul
echo ========================================
echo   王者荣耀英雄统计网站
echo ========================================
echo.

:: 检查虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [OK] 已激活虚拟环境
) else (
    echo [INFO] 未找到虚拟环境，使用系统Python
)

echo.
echo 正在启动服务器...
echo.

python app.py

pause
