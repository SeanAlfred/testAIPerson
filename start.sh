#!/bin/bash

echo "========================================"
echo "  数字人交互系统 - 启动脚本"
echo "========================================"
echo

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python 3.10+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "[信息] 安装依赖..."
pip install -r requirements.txt -q

# 检查Ollama
echo "[信息] 检查Ollama服务..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "[警告] Ollama服务未启动"
    echo "请确保已安装并启动Ollama: https://ollama.ai"
    echo "安装模型: ollama pull qwen2.5:7b"
    echo
fi

# 创建必要目录
mkdir -p outputs/{audio,images,videos,avatars}
mkdir -p logs

echo
echo "[信息] 启动服务..."
echo "访问地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo

python main.py "$@"