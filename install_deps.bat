@echo off
chcp 65001 > nul
echo ============================================
echo 数字人系统依赖安装脚本
echo ============================================
echo.

cd /d "%~dp0"

echo [1/4] 激活虚拟环境...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo 虚拟环境不存在，正在创建...
    python -m venv venv
    call venv\Scripts\activate.bat
)

echo.
echo [2/4] 安装 Python 依赖...
pip install -r requirements.txt

echo.
echo [3/4] 安装 Whisper（语音识别）...
pip install openai-whisper

echo.
echo [4/4] 安装 python-dotenv...
pip install python-dotenv

echo.
echo ============================================
echo 安装完成！
echo.
echo 接下来请：
echo   1. 安装 FFmpeg（视频生成必需）
echo      - Windows: winget install ffmpeg
echo      - 或手动下载: https://www.gyan.dev/ffmpeg/builds/
echo.
echo   2. 配置 API Key（可选）
echo      - 复制 .env 文件并填入您的密钥
echo.
echo   3. 启动服务
echo      - python main.py
echo ============================================
pause