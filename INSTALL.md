# 数字人交互系统 - 详细搭建指南

本文档提供完整的安装和配置步骤，适用于 Windows 和 Linux 环境。

## 目录

1. [环境准备](#1-环境准备)
2. [安装步骤](#2-安装步骤)
3. [配置详解](#3-配置详解)
4. [启动和测试](#4-启动和测试)
5. [常见问题解决](#5-常见问题解决)

---

## 1. 环境准备

### 1.1 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 / Ubuntu 18.04 | Windows 11 / Ubuntu 22.04 |
| Python | 3.10 | 3.11+ |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 2GB | 10GB+ |
| GPU | 无 | NVIDIA (用于本地图像生成) |

### 1.2 安装 Python

**Windows:**
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.10+ 安装包
3. 安装时勾选 "Add Python to PATH"

**Linux (Ubuntu):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
```

### 1.3 安装 Ollama (推荐)

Ollama 用于本地运行大语言模型。

**Windows:**
1. 访问 https://ollama.ai/download
2. 下载 Windows 版本并安装

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**下载模型:**
```bash
# 中文模型推荐
ollama pull qwen3:8b

# 其他可选模型
ollama pull llama3
ollama pull mistral
ollama pull deepseek-coder
```

### 1.4 安装 FFmpeg (视频生成需要)

**Windows:**
```bash
# 方法1: 使用 winget
winget install ffmpeg

# 方法2: 使用 choco
choco install ffmpeg

# 方法3: 手动安装
# 1. 访问 https://ffmpeg.org/download.html
# 2. 下载 Windows 构建
# 3. 解压并添加到 PATH
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

---

## 2. 安装步骤

### 2.1 获取项目

```bash
# 如果是从 Git 克隆
git clone <repository-url>
cd testAIPerson

# 或者直接进入项目目录
cd E:\AI\testAIPerson
```

### 2.2 创建虚拟环境

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2.3 安装依赖

```bash
pip install -r requirements.txt
```

如果安装较慢，可以使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.4 验证安装

```bash
python -c "import fastapi, uvicorn, edge_tts; print('依赖安装成功')"
```

---

## 3. 配置详解

### 3.1 配置文件位置

配置文件位于 `config/settings.yaml`

### 3.2 LLM 配置

#### 使用 Ollama (推荐)

```yaml
llm:
  provider: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen3:8b"  # 确保已通过 ollama pull 下载
    timeout: 60
```

#### 使用 OpenAI

```yaml
llm:
  provider: "openai"
  openai:
    api_key: "sk-xxxxxxxx"
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o-mini"
```

#### 使用国内 API (如智谱AI)

```yaml
llm:
  provider: "openai"
  openai:
    api_key: "your-zhipu-api-key"
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    model: "glm-4"
```

### 3.3 网络搜索配置

```yaml
web_search:
  enabled: true
  provider: "duckduckgo"  # 国内环境自动回退到百度
  max_results: 5
  timeout: 10
```

搜索触发条件：
- 包含关键词：最新、今天、现在、新闻、天气、搜索等
- 问题模式：什么是、怎么看待、如何评价等

### 3.4 语音合成配置

```yaml
tts:
  provider: "edge-tts"
  edge_tts:
    voice: "zh-CN-XiaoxiaoNeural"  # 女声
    rate: "+0%"   # 语速: -50% 到 +100%
    volume: "+0%" # 音量: -50% 到 +100%
```

常用声音选项：
- `zh-CN-XiaoxiaoNeural` - 晓晓 (女声，自然亲切)
- `zh-CN-YunxiNeural` - 云希 (男声，阳光活力)
- `zh-CN-YunyangNeural` - 云扬 (男声，新闻播音)

### 3.5 图像生成配置

#### SiliconFlow (国内推荐)

1. 注册账号: https://cloud.siliconflow.cn
2. 获取 API Key
3. 配置:

```yaml
image:
  provider: "siliconflow"
  siliconflow:
    api_key: "sk-xxxxxxxx"
    model: "stabilityai/stable-diffusion-xl-base-1.0"
```

#### 不配置 API Key

如果不配置 API Key，系统会生成占位图像，功能仍可正常使用。

### 3.6 视频生成配置

```yaml
video:
  provider: "sadtalker"
  sadtalker:
    api_url: ""  # 云端服务地址，留空使用本地
```

---

## 4. 启动和测试

### 4.1 启动服务

**Windows:**
```bash
# 方法1: 双击 start.bat

# 方法2: 命令行
venv\Scripts\activate
python main.py
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**命令行参数:**
```bash
python main.py --help

# 指定端口
python main.py --port 8080

# 指定配置文件
python main.py -c config/settings.yaml

# 启用热重载
python main.py --reload
```

### 4.2 访问服务

启动成功后，访问以下地址：

| 地址 | 说明 |
|------|------|
| http://localhost:8000 | 前端界面 |
| http://localhost:8000/docs | API 文档 |
| http://localhost:8000/api/health | 健康检查 |

### 4.3 测试功能

#### 测试健康状态

```bash
curl http://localhost:8000/api/health
```

#### 测试对话

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "你好", "generate_audio": false}'
```

#### 测试搜索

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python教程", "max_results": 3}'
```

#### 测试语音合成

```bash
curl -X POST http://localhost:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "测试语音合成"}'
```

---

## 5. 常见问题解决

### 5.1 端口被占用

**查找占用进程:**
```bash
# Windows
netstat -ano | findstr :8000

# Linux
lsof -i :8000
```

**终止进程:**
```bash
# Windows
taskkill /F /PID <PID>

# Linux
kill -9 <PID>
```

**或使用其他端口:**
```bash
python main.py --port 8080
```

### 5.2 Ollama 连接失败

**检查服务状态:**
```bash
# 测试 Ollama API
curl http://localhost:11434/api/tags
```

**启动 Ollama 服务:**
```bash
ollama serve
```

**Windows 服务问题:**
1. 打开服务管理器 (services.msc)
2. 找到 Ollama 服务
3. 确保服务正在运行

### 5.3 模块导入错误

```bash
# 确保在虚拟环境中
# Windows
venv\Scripts\activate

# Linux
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt
```

### 5.4 网络搜索无结果

**检查网络连接:**
```bash
# 测试网络
ping baidu.com
```

**国内环境配置:**
- 系统会自动使用百度搜索
- 确保 `web_search.enabled: true`

### 5.5 语音合成失败

Edge-TTS 需要网络连接：
- 检查防火墙设置
- 确保能访问微软服务器

### 5.6 视频生成失败

**检查 FFmpeg:**
```bash
ffmpeg -version
```

**如果未安装:**
```bash
# Windows
winget install ffmpeg

# Linux
sudo apt install ffmpeg
```

### 5.7 内存不足

如果遇到内存错误：
1. 关闭其他应用程序
2. 使用较小的模型 (如 qwen3:4b)
3. 减少 `max_history` 值

---

## 附录

### A. 完整配置示例

```yaml
# config/settings.yaml

system:
  name: "数字人交互系统"
  version: "1.1.0"
  debug: true
  log_level: "INFO"

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost"
    - "http://localhost:3000"

llm:
  provider: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen3:8b"
    timeout: 60

tts:
  provider: "edge-tts"
  edge_tts:
    voice: "zh-CN-XiaoxiaoNeural"
    rate: "+0%"
    volume: "+0%"

image:
  provider: "siliconflow"
  siliconflow:
    api_key: ""
    model: "stabilityai/stable-diffusion-xl-base-1.0"

video:
  provider: "sadtalker"

web_search:
  enabled: true
  provider: "duckduckgo"
  max_results: 5
  timeout: 10

digital_human:
  default_avatar:
    name: "小美"
    description: "专业的AI助手，亲切友好"
    style: "professional"

conversation:
  max_history: 20
  system_prompt: |
    你是一个专业的AI数字人助手，名叫{name}。
    你的特点是：{description}
    请用简洁、友好、专业的方式回答用户的问题。
```

### B. 环境变量

可选的环境变量：

```bash
# Windows
set OLLAMA_HOST=http://localhost:11434
set SILICONFLOW_API_KEY=sk-xxx

# Linux/Mac
export OLLAMA_HOST=http://localhost:11434
export SILICONFLOW_API_KEY=sk-xxx
```

### C. 日志文件

日志保存在 `logs/` 目录：
- `digital_human_YYYY-MM-DD.log`

查看日志：
```bash
# Windows
type logs\digital_human_2026-03-03.log

# Linux
cat logs/digital_human_2026-03-03.log
```

---

如有其他问题，请提交 Issue 或查看项目文档。