# 数字人交互系统

一个完整的 AI 数字人视频生成与交互系统，支持语音合成、图像生成、视频生成、智能对话和联网搜索。

## 功能特性

- **智能对话**: 支持多种大语言模型 (Ollama, OpenAI, 智谱AI等)
- **联网搜索**: 实时获取网络信息，支持新闻、天气、知识查询
- **语音合成**: 使用 Edge-TTS 高质量中文语音合成
- **图像生成**: 支持云端 API (SiliconFlow, Replicate, Stability AI)
- **视频生成**: 支持语音驱动的数字人视频生成
- **Web 界面**: 现代化的响应式前端界面
- **API 服务**: 完整的 RESTful API 和 WebSocket 支持

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数字人交互系统                           │
├─────────────────────────────────────────────────────────────┤
│  前端 (HTML/CSS/JS)                                         │
│  ├── 对话界面                                                │
│  ├── 数字人形象显示                                          │
│  └── 设置面板                                                │
├─────────────────────────────────────────────────────────────┤
│  API 服务 (FastAPI)                                         │
│  ├── /api/chat - 对话接口（支持联网搜索）                      │
│  ├── /api/search - 网络搜索接口                               │
│  ├── /api/avatar - 形象管理                                  │
│  ├── /api/tts - 语音合成                                     │
│  └── /api/video - 视频生成                                   │
├─────────────────────────────────────────────────────────────┤
│  核心模块                                                    │
│  ├── LLMClient - 大语言模型客户端                            │
│  ├── WebSearchEngine - 网络搜索引擎                          │
│  ├── TTSEngine - 语音合成引擎                                │
│  ├── ImageGenerator - 图像生成器                             │
│  └── VideoGenerator - 视频生成器                             │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境要求

- Python 3.10+
- Windows 10/11 或 Linux
- (可选) NVIDIA GPU 用于本地图像生成
- (可选) Ollama 用于本地 LLM

### 2. 安装

**Windows:**
```bash
# 双击运行 start.bat 或手动执行：
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 3. 配置

编辑 `config/settings.yaml` 文件：

```yaml
# LLM 配置 (使用 Ollama)
llm:
  provider: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen3:8b"

# 图像生成 (配置 API Key)
image:
  provider: "siliconflow"
  siliconflow:
    api_key: "your-api-key"  # 填入您的 API Key

# 网络搜索
web_search:
  enabled: true
  provider: "duckduckgo"  # 国内环境自动回退到百度
```

### 4. 安装 Ollama 模型

```bash
# 安装 Ollama: https://ollama.ai

# 下载中文模型
ollama pull qwen3:8b

# 或其他模型
ollama pull llama3
ollama pull mistral
```

### 5. 启动服务

```bash
python main.py
```

访问:
- 前端界面: http://localhost:8000
- API 文档: http://localhost:8000/docs

## API 使用示例

### 对话接口（自动联网搜索）

```python
import requests

# 普通对话
response = requests.post(
    "http://localhost:8000/api/chat",
    json={
        "text": "你好，请介绍一下自己",
        "generate_audio": True,
        "generate_video": False
    }
)

data = response.json()
print(data["data"]["text"])  # 回复文本
print(data["data"]["audio_url"])  # 音频地址
print(data["data"]["search_used"])  # 是否使用了搜索
```

### 联网搜索示例

```python
# 会自动触发搜索的问题
questions = [
    "今天最新的科技新闻有哪些",
    "北京今天天气怎么样",
    "最新的AI发展趋势是什么"
]

for q in questions:
    response = requests.post(
        "http://localhost:8000/api/chat",
        json={"text": q, "generate_audio": False}
    )
    data = response.json()
    print(f"问题: {q}")
    print(f"搜索触发: {data['data'].get('search_used', False)}")
    print(f"回答: {data['data']['text'][:100]}...")
```

### 直接使用搜索API

```python
# 网络搜索
response = requests.post(
    "http://localhost:8000/api/search",
    json={
        "query": "Python教程",
        "max_results": 5,
        "extract_content": True
    }
)

# 天气查询
response = requests.get(
    "http://localhost:8000/api/search/weather",
    params={"city": "北京"}
)

# 新闻查询
response = requests.get(
    "http://localhost:8000/api/search/news",
    params={"topic": "科技", "max_results": 10}
)
```

### 语音合成

```python
response = requests.post(
    "http://localhost:8000/api/tts",
    json={
        "text": "这是测试语音",
        "voice": "zh-CN-XiaoxiaoNeural"
    }
)

print(response.json()["data"]["audio_url"])
```

### 创建数字人形象

```python
response = requests.post(
    "http://localhost:8000/api/avatar",
    json={
        "name": "小云",
        "description": "温柔知性的AI助手",
        "style": "professional",
        "gender": "female"
    }
)

print(response.json()["data"]["image_url"])
```

## 配置说明

### LLM 配置

支持多种大语言模型：

```yaml
# Ollama (本地推荐)
llm:
  provider: "ollama"
  ollama:
    base_url: "http://localhost:11434"
    model: "qwen3:8b"
    timeout: 60

# OpenAI (云端)
llm:
  provider: "openai"
  openai:
    api_key: "sk-xxx"
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o-mini"
```

### 网络搜索配置

```yaml
web_search:
  enabled: true
  provider: "duckduckgo"  # 搜索引擎
  max_results: 5          # 最大结果数
  timeout: 10             # 超时时间(秒)
  max_content_length: 4000  # 内容最大长度

  # 可选：Bing API
  bing_api_key: ""

  # 可选：Google API
  google_api_key: ""
  google_cx: ""

  # 信任的域名优先
  trusted_domains:
    - "wikipedia.org"
    - "baike.baidu.com"
    - "zhihu.com"
```

### 图像生成配置

```yaml
# SiliconFlow (国内推荐)
image:
  provider: "siliconflow"
  siliconflow:
    api_key: "sk-xxx"
    model: "stabilityai/stable-diffusion-xl-base-1.0"

# Replicate
image:
  provider: "replicate"
  replicate:
    api_key: "r8_xxx"

# Stability AI
image:
  provider: "stability"
  stability:
    api_key: "sk-xxx"
```

### 语音配置

Edge-TTS 可用声音：

| 声音ID | 描述 |
|--------|------|
| zh-CN-XiaoxiaoNeural | 晓晓 (女声，自然亲切) |
| zh-CN-YunxiNeural | 云希 (男声，阳光活力) |
| zh-CN-YunyangNeural | 云扬 (男声，新闻播音) |
| zh-CN-XiaoyiNeural | 晓伊 (女声，温柔甜美) |
| zh-CN-YunjianNeural | 云健 (男声，沉稳大气) |

## 项目结构

```
digital-human-system/
├── config/
│   └── settings.yaml      # 配置文件
├── core/
│   ├── __init__.py
│   ├── llm_client.py      # LLM 客户端
│   ├── web_search.py      # 网络搜索引擎
│   ├── tts_engine.py      # 语音合成
│   ├── image_generator.py # 图像生成
│   ├── video_generator.py # 视频生成
│   └── digital_human.py   # 数字人核心类
├── api/
│   └── server.py          # FastAPI 服务
├── frontend/
│   └── index.html         # Web 界面
├── outputs/
│   ├── audio/             # 音频输出
│   ├── images/            # 图像输出
│   ├── videos/            # 视频输出
│   └── avatars/           # 数字人形象
├── logs/                  # 日志文件
├── main.py                # 启动入口
├── requirements.txt       # 依赖列表
├── start.bat              # Windows 启动脚本
└── start.sh               # Linux/Mac 启动脚本
```

## API 接口文档

### 系统状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/status | 系统状态 |

### 对话接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat | 对话（自动搜索） |
| WebSocket | /ws/chat | 流式对话 |
| GET | /api/history | 获取对话历史 |
| DELETE | /api/history | 清除对话历史 |

### 搜索接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/search | 网络搜索 |
| GET | /api/search/weather | 天气查询 |
| GET | /api/search/news | 新闻查询 |
| GET | /api/search/knowledge | 知识查询 |

### 数字人形象

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/avatar | 获取当前形象 |
| POST | /api/avatar | 创建新形象 |
| POST | /api/avatar/upload | 上传自定义形象 |
| PUT | /api/avatar/{id} | 切换形象 |

### 语音合成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/tts | 文本转语音 |
| GET | /api/tts/voices | 获取声音列表 |

### 视频生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/video/generate | 生成数字人视频 |

## 常见问题

### 1. Ollama 连接失败

确保 Ollama 服务正在运行：
```bash
ollama serve
```

检查模型是否已下载：
```bash
ollama list
```

### 2. 网络搜索无结果

国内环境下，系统会自动使用百度搜索。如果仍无结果：
- 检查网络连接
- 确认 `web_search.enabled` 为 `true`

### 3. 图像生成失败

检查 API Key 是否正确配置，或使用占位图像测试。

### 4. 语音合成失败

Edge-TTS 需要网络连接，请检查网络设置。

### 5. 视频生成失败

确保已安装 FFmpeg：
```bash
# Windows
winget install ffmpeg

# Linux
sudo apt install ffmpeg

# Mac
brew install ffmpeg
```

### 6. 端口被占用

如果8000端口被占用，可以指定其他端口：
```bash
python main.py --port 8080
```

## 搜索触发关键词

当用户输入包含以下关键词时，系统会自动触发联网搜索：

- 时间相关：最新、今天、现在、当前、最近
- 信息类型：新闻、天气、消息
- 动作词：查询、搜索、查找、帮我查
- 问题模式：什么是、怎么看待、如何评价

## 扩展开发

### 添加新的 LLM 提供商

在 `core/llm_client.py` 中添加新的提供商方法。

### 添加新的搜索引擎

在 `core/web_search.py` 中添加新的搜索方法。

### 添加新的语音合成服务

在 `core/tts_engine.py` 中添加新的 TTS 引擎。

### 添加新的图像生成服务

在 `core/image_generator.py` 中添加新的生成器。

## 依赖说明

主要依赖包：
- `fastapi` - Web框架
- `uvicorn` - ASGI服务器
- `httpx` - HTTP客户端
- `edge-tts` - 语音合成
- `ollama` - Ollama客户端
- `beautifulsoup4` - 网页解析
- `pillow` - 图像处理
- `loguru` - 日志

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.1.0
- 新增联网搜索功能
- 支持百度搜索（国内环境）
- 新增天气、新闻、知识查询API
- 优化对话搜索触发逻辑

### v1.0.0
- 初始版本
- 支持智能对话、语音合成、图像生成、视频生成