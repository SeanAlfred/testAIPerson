# FFmpeg 快速安装指南

## Windows 安装方法

### 方法 1: 使用 winget (推荐)

```bash
winget install ffmpeg
```

安装完成后,**重启命令行窗口**。

### 方法 2: 使用 Chocolatey

```bash
choco install ffmpeg
```

### 方法 3: 手动安装

1. **下载 FFmpeg**
   - 访问: https://www.gyan.dev/ffmpeg/builds/
   - 下载 "ffmpeg-release-essentials.zip"

2. **解压文件**
   - 解压到 `C:\ffmpeg`
   - 确保路径为: `C:\ffmpeg\bin\ffmpeg.exe`

3. **添加到系统 PATH**
   - 右键"此电脑" → "属性" → "高级系统设置"
   - 点击"环境变量"
   - 在"系统变量"中找到 `Path`,点击"编辑"
   - 点击"新建",添加: `C:\ffmpeg\bin`
   - 点击"确定"保存

4. **重启命令行窗口**

5. **验证安装**
   ```bash
   ffmpeg -version
   ```

---

## 验证 FFmpeg 安装

运行以下命令检查:

```bash
ffmpeg -version
```

应该看到类似输出:
```
ffmpeg version 6.0 ...
configuration: --enable-gpl --enable-version3 ...
```

---

## 安装后测试

### 测试音频转换

```bash
# 测试 ffmpeg 是否可用
ffmpeg -version

# 运行诊断脚本
python diagnose.py
```

### 测试语音识别

启动服务后,在前端点击语音按钮进行测试。

---

## 常见问题

### Q1: 提示 "ffmpeg 不是内部或外部命令"

**解决方案:**
1. 确认已添加到 PATH 环境变量
2. 重启命令行窗口
3. 重启计算机

### Q2: 安装后仍提示找不到 ffmpeg

**解决方案:**
1. 检查 PATH 是否正确: `echo %PATH%`
2. 手动运行: `C:\ffmpeg\bin\ffmpeg.exe -version`
3. 确保路径没有中文或空格

### Q3: Chocolatey 未安装

**安装 Chocolatey:**
```powershell
# 以管理员身份运行 PowerShell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

---

## 为什么需要 FFmpeg?

FFmpeg 用于:
1. ✅ **音频格式转换** - WebM → WAV (语音识别需要)
2. ✅ **视频生成** - 合成数字人说话视频
3. ✅ **音视频处理** - 多媒体文件格式转换

---

## 安装完成后的步骤

1. ✅ 安装 FFmpeg
2. ✅ 重启命令行
3. ✅ 验证安装: `ffmpeg -version`
4. ✅ 运行诊断: `python diagnose.py`
5. ✅ 启动服务: `python main.py`

---

## 临时解决方案 (不推荐)

如果暂时无法安装 FFmpeg,可以:

1. **使用 OpenAI Whisper API**
   
   编辑 `config/settings.yaml`:
   ```yaml
   stt:
     whisper:
       use_api: true
       api_key: "your-openai-api-key"
   ```

2. **禁用视频生成**
   
   前端取消勾选 "生成视频" 选项

---

## 需要帮助?

如果安装过程中遇到问题,请提供:
1. 操作系统版本
2. 错误信息截图
3. `ffmpeg -version` 的输出(如果有)
