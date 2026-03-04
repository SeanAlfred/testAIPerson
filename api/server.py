# -*- coding: utf-8 -*-
"""FastAPI 服务器 - 数字人交互系统API"""

import os
import json
import asyncio
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from loguru import logger
import yaml
import aiofiles

from core import DigitalHuman


def _path_to_url(file_path: str) -> str:
    """将文件路径转换为URL路径"""
    path = Path(file_path)
    # 查找outputs目录后的相对路径
    parts = path.parts
    if "outputs" in parts:
        idx = parts.index("outputs")
        return "/outputs/" + "/".join(parts[idx+1:])
    return f"/outputs/{path.name}"


# 请求模型
class ChatRequest(BaseModel):
    text: str
    generate_audio: bool = True
    generate_video: bool = True


class CreateAvatarRequest(BaseModel):
    name: str
    description: str = ""
    style: str = "professional"
    gender: str = "female"
    age: str = "young"
    expression: str = "smile"
    pose: str = "front"
    background: str = "clean"
    voice: str = "zh-CN-XiaoxiaoNeural"


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    rate: Optional[str] = None


class STTRequest(BaseModel):
    language: Optional[str] = None
    prompt: Optional[str] = None


# 加载配置
def load_config():
    config_path = Path("config/settings.yaml")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


# 初始化FastAPI
app = FastAPI(
    title="数字人交互系统 API",
    description="AI数字人视频生成与交互系统",
    version="1.0.0"
)

# CORS配置
config = load_config()
cors_origins = config.get("server", {}).get("cors_origins", ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# 前端静态文件
frontend_dir = Path("frontend")
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 全局数字人实例
digital_human: Optional[DigitalHuman] = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global digital_human
    logger.info("正在初始化数字人系统...")

    digital_human = DigitalHuman(config)
    await digital_human.initialize()

    logger.info("数字人系统初始化完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("数字人系统正在关闭...")


# ==================== 页面路由 ====================

@app.get("/")
async def index():
    """主页"""
    frontend_path = Path("frontend/index.html")
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "数字人交互系统 API", "docs": "/docs"}


# ==================== 系统状态 ====================

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")
    return await digital_human.get_status()


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== 对话接口 ====================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    与数字人对话

    - text: 用户输入文本
    - generate_audio: 是否生成语音响应
    - generate_video: 是否生成视频响应
    """
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        result = await digital_human.chat(
            user_input=request.text,
            generate_audio=request.generate_audio,
            generate_video=request.generate_video,
            stream=False
        )

        # 转换路径为URL
        if result.get("audio_path"):
            result["audio_url"] = _path_to_url(result["audio_path"])
        if result.get("video_path"):
            result["video_url"] = _path_to_url(result["video_path"])

        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 流式对话"""
    await websocket.accept()
    logger.info("WebSocket连接建立")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "chat":
                # 流式生成回复
                full_response = ""
                async for chunk in digital_human.chat_stream(message.get("text", "")):
                    full_response += chunk
                    await websocket.send_json({
                        "type": "chunk",
                        "content": chunk
                    })

                # 发送完成信号
                await websocket.send_json({
                    "type": "complete",
                    "content": full_response
                })

            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket连接断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        await websocket.close()


@app.get("/api/history")
async def get_history(limit: int = 10):
    """获取对话历史"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")
    return {"history": digital_human.get_history(limit)}


@app.delete("/api/history")
async def clear_history():
    """清除对话历史"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")
    digital_human.clear_history()
    return {"success": True, "message": "对话历史已清除"}


# ==================== 数字人形象管理 ====================

@app.get("/api/avatar")
async def get_current_avatar():
    """获取当前数字人形象"""
    if not digital_human or not digital_human.current_avatar:
        raise HTTPException(status_code=404, detail="未设置数字人形象")

    avatar = digital_human.current_avatar
    return {
        "id": avatar.id,
        "name": avatar.name,
        "description": avatar.description,
        "style": avatar.style,
        "gender": avatar.gender,
        "voice": avatar.voice,
        "image_url": _path_to_url(avatar.image_path)
    }


@app.post("/api/avatar")
async def create_avatar(request: CreateAvatarRequest):
    """创建新的数字人形象"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        avatar = await digital_human.create_avatar(
            name=request.name,
            description=request.description,
            style=request.style,
            gender=request.gender,
            age=request.age,
            expression=request.expression,
            pose=request.pose,
            background=request.background,
            voice=request.voice
        )

        return {
            "success": True,
            "data": {
                "id": avatar.id,
                "name": avatar.name,
                "image_url": _path_to_url(avatar.image_path)
            }
        }
    except Exception as e:
        logger.error(f"创建数字人形象失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/avatar/upload")
async def upload_avatar(
    file: UploadFile = File(...),
    name: str = "自定义形象",
    description: str = ""
):
    """上传自定义数字人形象"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        # 保存上传的文件
        avatar_dir = Path("outputs/avatars")
        avatar_dir.mkdir(parents=True, exist_ok=True)

        file_ext = Path(file.filename).suffix or ".png"
        file_path = avatar_dir / f"{uuid.uuid4().hex}{file_ext}"

        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 创建数字人形象
        avatar = await digital_human.create_avatar(
            name=name,
            description=description,
            reference_image=str(file_path)
        )

        return {
            "success": True,
            "data": {
                "id": avatar.id,
                "name": avatar.name,
                "image_url": _path_to_url(avatar.image_path)
            }
        }
    except Exception as e:
        logger.error(f"上传形象失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/avatar/{avatar_id}")
async def set_avatar(avatar_id: str):
    """切换数字人形象"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    if digital_human.set_avatar(avatar_id):
        return {"success": True, "message": f"已切换到形象: {avatar_id}"}
    else:
        raise HTTPException(status_code=404, detail=f"找不到形象: {avatar_id}")


# ==================== 语音合成 ====================

@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """文本转语音"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        audio_path = await digital_human.tts.synthesize(
            text=request.text,
            voice=request.voice,
            rate=request.rate
        )

        return {
            "success": True,
            "data": {
                "audio_path": audio_path,
                "audio_url": _path_to_url(audio_path)
            }
        }
    except Exception as e:
        logger.error(f"语音合成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tts/voices")
async def get_tts_voices(language: Optional[str] = None):
    """获取可用的语音列表"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    voices = await digital_human.tts.get_voices(language)
    return {"voices": voices}


# ==================== 语音识别 ====================

@app.post("/api/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    language: Optional[str] = None
):
    """
    语音识别 (上传音频文件)

    支持格式: wav, mp3, m4a, webm 等
    """
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        # 保存上传的音频文件
        audio_dir = Path("outputs/audio")
        audio_dir.mkdir(parents=True, exist_ok=True)

        file_ext = Path(file.filename).suffix or ".wav"
        audio_path = audio_dir / f"stt_{uuid.uuid4().hex}{file_ext}"

        async with aiofiles.open(audio_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 语音识别
        result = await digital_human.transcribe_audio(
            audio_file=str(audio_path),
            language=language
        )

        return {
            "success": True,
            "data": {
                "text": result["text"],
                "language": result["language"],
                "confidence": result["confidence"],
                "duration": result["duration"]
            }
        }
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/audio")
async def chat_with_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    generate_audio: bool = True,
    generate_video: bool = False
):
    """
    通过语音进行对话 (语音识别 + 对话 + 语音合成)

    上传音频文件,系统自动识别并回复
    """
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        # 保存上传的音频文件
        audio_dir = Path("outputs/audio")
        audio_dir.mkdir(parents=True, exist_ok=True)

        file_ext = Path(file.filename).suffix or ".wav"
        audio_path = audio_dir / f"chat_audio_{uuid.uuid4().hex}{file_ext}"

        async with aiofiles.open(audio_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 语音对话
        result = await digital_human.chat_with_audio(
            audio_file=str(audio_path),
            language=language,
            generate_audio=generate_audio,
            generate_video=generate_video
        )

        # 转换路径为URL
        response_data = result["response"]
        if response_data.get("audio_path"):
            response_data["audio_url"] = _path_to_url(response_data["audio_path"])
        if response_data.get("video_path"):
            response_data["video_url"] = _path_to_url(response_data["video_path"])

        return {
            "success": True,
            "data": {
                "recognized_text": result["recognized_text"],
                "stt_result": result["stt_result"],
                "response": response_data
            }
        }
    except Exception as e:
        logger.error(f"语音对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stt/languages")
async def get_stt_languages():
    """获取语音识别支持的语言列表"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    languages = await digital_human.stt.get_supported_languages()
    return {"languages": languages}


# ==================== 视频生成 ====================

@app.post("/api/video/generate")
async def generate_video(text: str, avatar_id: Optional[str] = None):
    """生成数字人说话视频"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        video_path = await digital_human.generate_response_video(text, avatar_id)

        return {
            "success": True,
            "data": {
                "video_path": video_path,
                "video_url": _path_to_url(video_path)
            }
        }
    except Exception as e:
        logger.error(f"视频生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 会话管理 ====================

@app.post("/api/session/save")
async def save_session():
    """保存当前会话"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    session_dir = Path("outputs/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)

    file_path = session_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    digital_human.save_session(str(file_path))

    return {"success": True, "file": str(file_path)}


@app.post("/api/session/load")
async def load_session(file: UploadFile = File(...)):
    """加载会话"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        content = await file.read()
        session_data = json.loads(content)

        session_dir = Path("outputs/sessions")
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / file.filename

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        digital_human.load_session(str(file_path))

        return {"success": True, "message": "会话已加载"}
    except Exception as e:
        logger.error(f"加载会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 工具接口 ====================

@app.get("/api/llm/models")
async def get_llm_models():
    """获取可用的LLM模型列表"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    models = await digital_human.llm.list_models()
    return {"models": models}


# ==================== 网络搜索接口 ====================

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5
    extract_content: Optional[bool] = True


@app.post("/api/search")
async def web_search(request: SearchRequest):
    """
    网络搜索接口

    - query: 搜索关键词
    - max_results: 最大结果数
    - extract_content: 是否提取网页内容
    """
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        result = await digital_human.web_search.search(
            query=request.query,
            max_results=request.max_results,
            extract_content=request.extract_content
        )
        return result
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/weather")
async def get_weather(city: str):
    """获取天气信息"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        result = await digital_human.web_search.get_weather(city)
        return result
    except Exception as e:
        logger.error(f"获取天气失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/news")
async def get_news(topic: Optional[str] = "", max_results: Optional[int] = 5):
    """获取新闻"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        result = await digital_human.web_search.get_news(
            topic=topic,
            max_results=max_results
        )
        return result
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/knowledge")
async def get_knowledge(question: str):
    """获取知识点"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        result = await digital_human.web_search.get_knowledge(question)
        return result
    except Exception as e:
        logger.error(f"获取知识失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    status = await digital_human.get_status()

    # 添加搜索服务状态
    search_ok = await digital_human.web_search.check_health()
    status["components"]["web_search"] = {
        "provider": digital_human.web_search.search_provider,
        "healthy": search_ok
    }

    return status


if __name__ == "__main__":
    import uvicorn

    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8000)

    uvicorn.run(app, host=host, port=port)