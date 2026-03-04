@echo off
chcp 65001 >nul
echo ========================================
echo   数字人交互系统 - 启动脚本
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [信息] 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo [信息] 安装依赖...
pip install -r requirements.txt -q

REM 检查Ollama
echo [信息] 检查Ollama服务...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [警告] Ollama服务未启动
    echo 请确保已安装并启动Ollama: https://ollama.ai
    echo 安装模型: ollama pull qwen2.5:7b
    echo.
)

REM 创建必要目录
if not exist "outputs" mkdir outputs
if not exist "outputs\audio" mkdir outputs\audio
if not exist "outputs\images" mkdir outputs\images
if not exist "outputs\videos" mkdir outputs\videos
if not exist "outputs\avatars" mkdir outputs\avatars
if not exist "logs" mkdir logs

echo.
echo [信息] 启动服务...
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.

python main.py

pause