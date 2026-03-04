#!/bin/bash

echo "========================================"
echo "数字人系统问题修复脚本"
echo "========================================"
echo

echo "[1/4] 安装缺失的依赖包..."
echo
pip install openai-whisper pydub soundfile numpy opencv-python websockets requests python-dotenv tenacity
echo

echo "[2/4] 检查 FFmpeg..."
echo "FFmpeg 是视频生成必需的工具"
echo

# 检查 FFmpeg 是否已安装
if command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg 已安装"
    ffmpeg -version | head -n 1
else
    echo "✗ FFmpeg 未安装"
    echo
    echo "请按以下步骤安装 FFmpeg:"
    echo
    echo "Ubuntu/Debian:"
    echo "  sudo apt update"
    echo "  sudo apt install ffmpeg"
    echo
    echo "CentOS/RHEL:"
    echo "  sudo yum install epel-release"
    echo "  sudo yum install ffmpeg"
    echo
    echo "MacOS:"
    echo "  brew install ffmpeg"
    echo
fi
echo

echo "[3/4] 下载 Whisper 模型..."
echo "首次使用会自动下载模型(约1GB),请耐心等待"
echo

echo "[4/4] 检查配置文件..."
if [ ! -f "config/settings.yaml" ]; then
    echo "配置文件不存在,创建默认配置..."
    cp config/settings.yaml.example config/settings.yaml 2>/dev/null
fi
echo

echo "========================================"
echo "修复完成!"
echo "========================================"
echo
echo "接下来请执行以下操作:"
echo "1. 如果 FFmpeg 未安装,请先安装"
echo "2. 启动服务: python main.py"
echo "3. 访问: http://localhost:8000"
echo
