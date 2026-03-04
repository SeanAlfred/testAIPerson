# 模型文件目录

此目录用于存放本地模型文件（如果需要）：

## 目录结构

```
models/
├── checkpoints/     # Stable Diffusion 模型
├── lora/           # LoRA 权重
├── ipadapter/      # IP-Adapter 模型
├── controlnet/     # ControlNet 模型
├── sadtalker/      # SadTalker 模型
└── tts/            # TTS 模型
```

## 模型下载

### Stable Diffusion
```bash
# SDXL
wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# SD 1.5
wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
```

### SadTalker
```bash
git clone https://github.com/OpenTalker/SadTalker
cd SadTalker
# 下载模型文件...
```

## 注意

- 大多数模型文件较大（1-6GB），请确保有足够磁盘空间
- 使用云端API时无需下载本地模型