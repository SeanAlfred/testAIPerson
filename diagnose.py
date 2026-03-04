#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统诊断脚本 - 检测和修复常见问题
"""

import os
import sys
import subprocess
from pathlib import Path

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    import locale
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def check_python_version():
    """检查 Python 版本"""
    print("[OK] 检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"  [PASS] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  [FAIL] Python 版本过低: {version.major}.{version.minor}.{version.micro}")
        print("  需要 Python 3.10 或更高版本")
        return False

def check_package(package_name, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"  [PASS] {package_name}")
        return True
    except ImportError:
        print(f"  [FAIL] {package_name} (未安装)")
        return False

def check_dependencies():
    """检查所有依赖"""
    print("\n[OK] 检查依赖包...")
    
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("httpx", "httpx"),
        ("edge-tts", "edge_tts"),
        ("pyyaml", "yaml"),
        ("loguru", "loguru"),
        ("Pillow", "PIL"),
        ("ollama", "ollama"),
        ("aiofiles", "aiofiles"),
        ("openai-whisper", "whisper"),  # 语音识别
    ]
    
    missing = []
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            missing.append(package_name)
    
    return missing

def check_ffmpeg():
    """检查 FFmpeg"""
    print("\n[OK] 检查 FFmpeg...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"  [PASS] {version_line}")
            return True
        else:
            print("  [FAIL] FFmpeg 未正确安装")
            return False
    except FileNotFoundError:
        print("  [FAIL] FFmpeg 未安装")
        print("  安装方法:")
        print("    Windows: winget install ffmpeg")
        print("    Linux: sudo apt install ffmpeg")
        print("    macOS: brew install ffmpeg")
        return False
    except Exception as e:
        print(f"  [FAIL] FFmpeg 检查失败: {e}")
        return False

def check_ollama():
    """检查 Ollama 服务"""
    print("\n[OK] 检查 Ollama 服务...")
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                print(f"  [PASS] Ollama 运行中,可用模型: {[m['name'] for m in models]}")
            else:
                print("  [WARN] Ollama 运行中,但没有模型")
                print("  下载模型: ollama pull qwen2.5:7b")
            return True
        else:
            print("  [FAIL] Ollama 响应异常")
            return False
    except Exception as e:
        print(f"  [FAIL] 无法连接 Ollama: {e}")
        print("  启动方法: ollama serve")
        return False

def check_config():
    """检查配置文件"""
    print("\n[OK] 检查配置文件...")
    config_path = Path("config/settings.yaml")
    
    if not config_path.exists():
        print(f"  [FAIL] 配置文件不存在: {config_path}")
        return False
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        print("  [PASS] 配置文件存在")
        
        # 检查关键配置
        if not config.get("llm", {}).get("ollama", {}).get("model"):
            print("  [WARN] 未配置 LLM 模型")
        
        stt_config = config.get("stt", {})
        if stt_config.get("provider") == "whisper":
            if not stt_config.get("whisper", {}).get("use_api"):
                print("  [INFO] 使用本地 Whisper 模型")
            else:
                api_key = stt_config.get("whisper", {}).get("api_key")
                if api_key:
                    print("  [PASS] 配置了 OpenAI Whisper API")
                else:
                    print("  [WARN] 使用 Whisper API 但未配置 API Key")
        
        return True
    except Exception as e:
        print(f"  [FAIL] 配置文件读取失败: {e}")
        return False

def check_directories():
    """检查必要的目录"""
    print("\n[OK] 检查输出目录...")
    dirs = [
        "outputs/audio",
        "outputs/images",
        "outputs/videos",
        "outputs/avatars",
        "logs"
    ]
    
    for dir_path in dirs:
        path = Path(dir_path)
        if not path.exists():
            print(f"  [INFO] 创建目录: {dir_path}")
            path.mkdir(parents=True, exist_ok=True)
        else:
            print(f"  [PASS] {dir_path}")
    
    return True

def check_ports():
    """检查端口占用"""
    print("\n[OK] 检查端口占用...")
    
    try:
        import socket
        
        # 检查 8000 端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        
        if result == 0:
            print("  [WARN] 端口 8000 已被占用")
            print("  可能已有服务在运行,或使用其他端口:")
            print("    python main.py --port 8080")
            return False
        else:
            print("  [PASS] 端口 8000 可用")
            return True
    except Exception as e:
        print(f"  [WARN] 无法检查端口: {e}")
        return True

def main():
    """主函数"""
    print("=" * 60)
    print("数字人系统诊断工具")
    print("=" * 60)
    
    results = {
        "Python 版本": check_python_version(),
        "依赖包": len(check_dependencies()) == 0,
        "FFmpeg": check_ffmpeg(),
        "Ollama": check_ollama(),
        "配置文件": check_config(),
        "输出目录": check_directories(),
        "端口占用": check_ports(),
    }
    
    print("\n" + "=" * 60)
    print("诊断结果")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name:15s} {status}")
    
    print("\n" + "=" * 60)
    
    # 统计
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    if passed == total:
        print(f"[OK] 所有检查通过 ({passed}/{total})")
        print("\n可以启动服务:")
        print("  python main.py")
    else:
        print(f"[WARN] 存在 {total - passed} 个问题")
        print("\n请先解决上述问题后再启动服务")
        print("\n快速修复:")
        
        missing_packages = check_dependencies()
        if missing_packages:
            print(f"  pip install {' '.join(missing_packages)}")
        
        if not results.get("FFmpeg"):
            print("  # 安装 FFmpeg (参考上面的说明)")
        
        if not results.get("Ollama"):
            print("  ollama serve")
            print("  ollama pull qwen2.5:7b")
    
    print("=" * 60)

if __name__ == "__main__":
    main()

