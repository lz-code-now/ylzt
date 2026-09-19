@echo off
rem 御龙挂机助手 Windows 一键打包脚本(W9)
rem 用法:把整个项目目录拷到 Windows 机器,双击本文件即可
rem 产物:dist\ylzt\(整个目录复制到目标机器即用)

chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================
echo   御龙挂机助手 - Windows 打包
echo ============================================

rem ---- 1. Python 检查 ----
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python,请安装 Python 3.11+ 并勾选 "Add to PATH"
    echo        下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('py -3 --version') do set PYVER=%%i
echo [1/5] Python OK: %PYVER%

rem ---- 2. 虚拟环境 ----
if not exist .venv (
    echo [2/5] 创建虚拟环境 .venv ...
    py -3 -m venv .venv
    if errorlevel 1 ( echo [错误] venv 创建失败 & pause & exit /b 1 )
) else (
    echo [2/5] 复用已有虚拟环境 .venv
)

rem ---- 3. 依赖 ----
echo [3/5] 安装依赖(含 Windows 运行时 + PyInstaller)...
.venv\Scripts\python -m pip install -e ".[windows,dev]" pyinstaller -q
if errorlevel 1 (
    echo [错误] 依赖安装失败,检查网络后重试
    pause
    exit /b 1
)

rem ---- 4. 测试 ----
echo [4/5] 运行全量测试...
.venv\Scripts\python -m pytest -q
if errorlevel 1 (
    echo [错误] 测试未通过,取消打包
    pause
    exit /b 1
)

rem ---- 5. 打包 ----
echo [5/5] PyInstaller 打包...
.venv\Scripts\python scripts\build.py --no-tests
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成: dist\ylzt\
echo   整个 dist\ylzt 目录复制到目标机器即用
echo   使用说明见 dist\ylzt\使用说明.txt
echo ============================================
pause
