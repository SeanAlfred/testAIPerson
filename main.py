#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数字人交互系统 - 启动入口
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载 .env 文件中的环境变量
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"已加载环境变量: {env_path}")

from loguru import logger
import yaml
import uvicorn


def setup_logging(config: dict):
    """配置日志"""
    log_config = config.get("system", {})
    log_level = log_config.get("log_level", "INFO")

    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True
    )

    # 添加文件输出
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "digital_human_{time:YYYY-MM-DD}.log",
        level=log_level,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        enqueue=True
    )


def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config/settings.yaml")

    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return get_default_config()

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        "system": {
            "name": "数字人交互系统",
            "version": "1.0.0",
            "debug": True,
            "log_level": "INFO"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "cors_origins": ["*"]
        },
        "llm": {
            "provider": "ollama",
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "qwen2.5:7b",
                "timeout": 60
            }
        },
        "tts": {
            "provider": "edge-tts",
            "edge_tts": {
                "voice": "zh-CN-XiaoxiaoNeural",
                "rate": "+0%",
                "volume": "+0%"
            }
        },
        "image": {
            "provider": "siliconflow",
            "siliconflow": {
                "api_key": "",
                "model": "stabilityai/stable-diffusion-xl-base-1.0"
            }
        },
        "video": {
            "provider": "sadtalker"
        },
        "digital_human": {
            "default_avatar": {
                "name": "小美",
                "description": "专业的AI助手，亲切友好",
                "style": "professional"
            }
        },
        "conversation": {
            "max_history": 20,
            "system_prompt": "你是一个专业的AI数字人助手，名叫{name}。你的特点是：{description}请用简洁、友好、专业的方式回答用户的问题。"
        },
        "output": {
            "audio_dir": "outputs/audio",
            "image_dir": "outputs/images",
            "video_dir": "outputs/videos",
            "temp_dir": "outputs/temp"
        }
    }


def create_directories(config: dict):
    """创建必要的目录"""
    output_config = config.get("output", {})
    for dir_key in ["audio_dir", "image_dir", "video_dir", "temp_dir"]:
        dir_path = Path(output_config.get(dir_key, f"outputs/{dir_key.replace('_dir', '')}"))
        dir_path.mkdir(parents=True, exist_ok=True)

    # 创建其他必要目录
    Path("outputs/avatars").mkdir(parents=True, exist_ok=True)
    Path("outputs/sessions").mkdir(parents=True, exist_ok=True)


def check_dependencies():
    """检查依赖"""
    logger.info("检查依赖...")

    # (包名, 导入名)
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("httpx", "httpx"),
        ("edge-tts", "edge_tts"),
        ("pyyaml", "yaml"),
        ("loguru", "loguru"),
        ("pillow", "PIL"),
        ("ollama", "ollama"),
        ("aiofiles", "aiofiles"),
    ]

    missing = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        logger.error(f"缺少依赖包: {', '.join(missing)}")
        logger.info(f"请运行: pip install {' '.join(missing)}")
        return False

    return True


def check_services(config: dict):
    """检查服务状态"""
    logger.info("检查服务...")

    # 检查Ollama
    llm_config = config.get("llm", {})
    if llm_config.get("provider") == "ollama":
        import httpx
        try:
            base_url = llm_config.get("ollama", {}).get("base_url", "http://localhost:11434")
            response = httpx.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                logger.info(f"Ollama服务正常，可用模型: {[m['name'] for m in models]}")
            else:
                logger.warning("Ollama服务响应异常")
        except Exception as e:
            logger.warning(f"无法连接Ollama服务: {e}")
            logger.info("请确保Ollama已启动: ollama serve")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数字人交互系统")
    parser.add_argument("-c", "--config", default="config/settings.yaml", help="配置文件路径")
    parser.add_argument("--host", default=None, help="服务器地址")
    parser.add_argument("--port", type=int, default=None, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载")
    parser.add_argument("--check", action="store_true", help="仅检查依赖和服务")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 配置日志
    setup_logging(config)

    logger.info(f"启动 {config.get('system', {}).get('name', '数字人交互系统')} v{config.get('system', {}).get('version', '1.0.0')}")

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 创建目录
    create_directories(config)

    # 检查服务
    check_services(config)

    if args.check:
        logger.info("检查完成")
        return

    # 获取服务器配置
    server_config = config.get("server", {})
    host = args.host or server_config.get("host", "0.0.0.0")
    port = args.port or server_config.get("port", 8000)

    logger.info(f"启动服务器: http://{host}:{port}")
    logger.info(f"API文档: http://{host}:{port}/docs")
    logger.info(f"前端界面: http://{host}:{port}/")

    # 启动服务器
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()