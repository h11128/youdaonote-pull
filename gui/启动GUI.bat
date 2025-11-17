@echo off
chcp 65001 >nul
title 有道云笔记GUI管理工具

echo.
echo ========================================
echo    有道云笔记GUI管理工具
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动GUI界面...
python start_gui.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查：
    echo 1. Python是否已安装
    echo 2. cookies.json文件是否存在
    echo 3. 网络连接是否正常
    echo.
    pause
)
