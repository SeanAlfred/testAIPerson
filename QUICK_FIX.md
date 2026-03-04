# 快速问题修复指南

## 问题 1: 语音识别失败

### 原因
未安装 Whisper 或 FFmpeg

### 解决方案

**方法一：安装本地 Whisper（推荐，免费）**

```bash
# 进入项目目录
cd E:/AI/testAIPerson

# 激活虚拟环境
./venv/Scripts/activate

# 安装 Whisper
pip install openai-whisper

# 安装 FFmpeg（Whisper 需要）
# Windows:
winget install ffmpeg
```

**首次使用会自动下载模型：**
- tiny: 约 75MB（最快，精度低）
- base: 约 150MB（推荐平衡）
- small: 约 500MB
- medium: 约 1.5GB
- large: 约 3GB（最准，最慢）

**方法二：使用 OpenAI Whisper API（更快）**

1. 注册 OpenAI：https://platform.openai.com
2. 获取 API Key
3. 编辑 `config/settings.yaml`：

```yaml
stt:
  provider: "whisper"
  whisper:
    model: "base"
    language: "zh"
    use_api: true  # 改为 true
    api_key: ""    # 留空则从环境变量读取
```

4. 在 `.env` 文件中配置：
```
OPENAI_API_KEY=sk-your-api-key
```

---

## 问题 2: 视频生成失败

### 原因
未安装 FFmpeg 或未配置视频生成 API

### 解决方案

**方法一：安装 FFmpeg（基础方案）**

Windows 安装方法：

**使用 winget（推荐）：**
```bash
winget install ffmpeg
```

**手动安装：**
1. 访问：https://www.gyan.dev/ffmpeg/builds/
2. 下载 `ffmpeg-release-essentials.zip`
3. 解压到 `C:\ffmpeg`
4. 添加 `C:\ffmpeg\bin` 到系统 PATH 环境变量
5. 重启命令行窗口

**验证安装：**
```bash
ffmpeg -version
```

**方法二：使用 D-ID API（专业数字人）**

D-ID 是专业的数字人视频生成服务：

1. **注册账号**
   - 访问：https://www.d-id.com
   - 点击 "Get Started" 或 "Sign Up"
   - 填写邮箱注册
   - 免费试用有 **5分钟视频额度**

2. **获取 API Key**
   - 登录后进入 Dashboard
   - 点击左侧 "API Keys"
   - 复制 API Key

3. **配置系统**

   编辑 `.env` 文件：
   ```
   D_ID_API_KEY=your-d-id-api-key
   ```

   编辑 `config/settings.yaml`：
   ```yaml
   video:
     provider: "d-id"  # 改为 d-id
   ```

**方法三：使用 HeyGen API**

HeyGen 是另一个优秀的数字人服务：

1. **注册账号**
   - 访问：https://www.heygen.com
   - 点击 "Get Started Free"
   - 填写邮箱注册
   - 免费试用有 **1个积分**

2. **获取 API Key**
   - 登录后进入 Settings
   - 点击 "API Key"
   - 生成并复制 API Key

3. **配置系统**

   编辑 `.env` 文件：
   ```
   HEYGEN_API_KEY=your-heygen-api-key
   ```

   编辑 `config/settings.yaml`：
   ```yaml
   video:
     provider: "heygen"  # 改为 heygen
   ```

---

## 问题 3: 404 错误 - 对话不响应

### 原因
服务未正确启动或端口被占用

### 解决方案

**1. 启动服务**
```bash
python main.py
```

**2. 检查服务是否运行**
打开浏览器访问:
- http://localhost:8000/api/health
- 应该看到: `{"status": "healthy", ...}`

**3. 如果端口被占用**
```bash
# 查找占用进程
netstat -ano | findstr :8000

# 或使用其他端口启动
python main.py --port 8080
```

**4. 检查 Ollama 是否运行**
```bash
# 启动 Ollama
ollama serve

# 检查模型是否已下载
ollama list

# 如果没有模型,下载一个
ollama pull qwen2.5:7b
```

---

## 问题 4: 图像生成失败

### 原因
未配置图像生成 API Key

### 解决方案

**使用 SiliconFlow（推荐，国内访问快）**

1. **注册账号**
   - 访问：https://cloud.siliconflow.cn
   - 注册账号

2. **获取 API Key**
   - 登录后进入控制台
   - 点击 "API Keys"
   - 创建并复制 API Key

3. **配置系统**

   编辑 `.env` 文件：
   ```
   SILICONFLOW_API_KEY=your-api-key
   ```

   编辑 `config/settings.yaml`：
   ```yaml
   image:
     provider: "siliconflow"
     siliconflow:
       api_key: ""  # 留空则从环境变量读取
   ```

---

## 快速安装脚本

运行项目根目录下的 `install_deps.bat`：

```bash
./install_deps.bat
```

这会自动安装所有 Python 依赖。

---

## 完整安装流程

### 1. 安装 Python 依赖
```bash
cd E:/AI/testAIPerson
./venv/Scripts/activate
pip install -r requirements.txt
pip install openai-whisper
```

### 2. 安装 FFmpeg
```bash
winget install ffmpeg
```

### 3. 启动 Ollama
```bash
ollama serve
ollama pull qwen2.5:7b
```

### 4. 配置 API Key（可选）
复制 `.env.example` 为 `.env`，填入需要的 API Key

### 5. 启动服务
```bash
python main.py
```

### 6. 访问应用
打开浏览器：http://localhost:8000

---

## 服务对比

| 服务 | 免费额度 | 价格 | 推荐度 |
|------|----------|------|--------|
| 本地 Whisper | 无限 | 免费 | ⭐⭐⭐⭐⭐ |
| OpenAI Whisper API | $5 新用户 | $0.006/分钟 | ⭐⭐⭐⭐ |
| D-ID | 5分钟 | $0.12/分钟 | ⭐⭐⭐⭐ |
| HeyGen | 1积分 | $29/月起 | ⭐⭐⭐ |
| SiliconFlow | 14元 | 按量付费 | ⭐⭐⭐⭐ |

---

## 常见问题

### Q1: 提示 "Ollama 连接失败"
**A:** 确保 Ollama 服务正在运行
```bash
ollama serve
```

### Q2: 提示 "API Key 未配置"
**A:** 这是正常的，系统会使用占位图。如需生成真实图像：
1. 注册 SiliconFlow: https://cloud.siliconflow.cn
2. 获取 API Key
3. 配置 `.env` 文件

### Q3: 浏览器提示麦克风权限
**A:** 点击"允许"即可。如果被拒绝：
- Chrome: 地址栏左侧点击锁图标 → 网站设置 → 麦克风 → 允许
- Firefox: 地址栏左侧点击信息图标 → 权限 → 使用麦克风 → 允许

### Q4: 语音识别很慢
**A:**
- 本地 Whisper 首次使用需要下载模型
- 可以使用更小的模型 (tiny 或 base)
- 或者配置使用 OpenAI API

### Q5: 视频生成失败
**A:**
- 确保安装了 FFmpeg
- 或者配置使用云端服务 (D-ID, HeyGen)

---

## 性能优化建议

### 1. 使用更小的 Whisper 模型
```yaml
stt:
  whisper:
    model: "tiny"  # 或 "base"
```

### 2. 使用 OpenAI Whisper API（更快）
```yaml
stt:
  whisper:
    use_api: true
    api_key: "your-key"
```

### 3. 禁用视频生成（提高速度）
前端取消勾选 "生成视频" 选项

### 4. 使用更快的 LLM 模型
```yaml
llm:
  ollama:
    model: "qwen2.5:3b"  # 更小的模型,速度更快
```

---

## 测试清单

- [ ] 服务成功启动 (无报错)
- [ ] 访问 http://localhost:8000 能看到界面
- [ ] 访问 http://localhost:8000/api/health 返回正常
- [ ] Ollama 服务运行正常
- [ ] 文字对话功能正常
- [ ] 语音合成功能正常
- [ ] 语音识别功能正常 (已安装 Whisper)
- [ ] 视频生成功能正常 (已安装 FFmpeg)
- [ ] 形象生成功能正常 (已配置 API Key)

---

## 获取帮助

如果问题仍未解决:

1. 查看日志文件: `logs/digital_human_*.log`
2. 检查控制台输出
3. 查看 API 文档: http://localhost:8000/docs
4. 提交 Issue 并附上错误日志