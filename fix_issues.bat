@echo off
echo ========================================
echo 数字人系统问题修复脚本
echo ========================================
echo.

echo [1/4] 安装缺失的依赖包...
echo.
pip install openai-whisper pydub soundfile numpy opencv-python websockets requests python-dotenv tenacity
echo.

echo [2/4] 检查 FFmpeg...
echo FFmpeg 是视频生成必需的工具
echo.
echo 请按以下步骤安装 FFmpeg:
echo.
echo Windows (使用 winget):
echo   winget install ffmpeg
echo.
echo 或者从官网下载: https://ffmpeg.org/download.html
echo 下载后解压到任意目录,并添加到系统PATH环境变量
echo.
echo 安装完成后,运行: ffmpeg -version 测试是否成功
echo.

echo [3/4] 下载 Whisper 模型...
echo 首次使用会自动下载模型(约1GB),请耐心等待
echo.

echo [4/4] 检查配置文件...
if not exist "config\settings.yaml" (
    echo 配置文件不存在,创建默认配置...
    copy config\settings.yaml.example config\settings.yaml 2>nul
)
echo.

echo ========================================
echo 修复完成!
echo ========================================
echo.
echo 接下来请执行以下操作:
echo 1. 安装 FFmpeg (参考上面的说明)
echo 2. 启动服务: python main.py
echo 3. 访问: http://localhost:8000
echo.
pause
