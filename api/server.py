# -*- coding: utf-8 -*-
"""FastAPI 服务器 - 数字人交互系统API"""

import os
import sys
import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import uuid

# 设置 Windows 控制台 UTF-8 编码
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
from loguru import logger
import yaml
import aiofiles
import httpx

from core import DigitalHuman
from core.text_to_video import TextToVideoGenerator
from core.scheduler_agent import SchedulerAgent, IntentType
from core.task_planner_agent import TaskPlannerAgent, TaskType
from utils.text2video import LocalVideoGenerator
from utils.animatediff_generator import AnimateDiffGenerator
from utils.document_generator import document_generator


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
    call_mode: Optional[str] = None  # ollamaAPI, zeroToken, deepseekAPI
    zero_token_platform: Optional[str] = None  # deepseek, claude, doubao
    model: Optional[str] = None  # Ollama 模型名称
    deepseek_model: Optional[str] = None  # DeepSeek 模型名称
    enable_search: bool = True  # 是否启用联网搜索


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


class TextToVideoRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    image_size: str = "1280x720"
    seed: Optional[int] = None
    timeout: int = 300
    provider: str = "siliconflow"  # "siliconflow", "local", "animatediff"


class ImageToVideoRequest(BaseModel):
    prompt: str
    image_url: Optional[str] = None
    negative_prompt: str = ""
    image_size: str = "1280x720"
    seed: Optional[int] = None
    timeout: int = 300


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
# 文本到视频生成器（SiliconFlow API）
text_to_video: Optional[TextToVideoGenerator] = None
# 本地视频生成器（SVD）
local_video_generator: Optional[LocalVideoGenerator] = None
# AnimateDiff生成器（低显存GPU）
animatediff_generator: Optional[AnimateDiffGenerator] = None
# 调度智能体
scheduler_agent: Optional[SchedulerAgent] = None
# 任务规划智能体
task_planner_agent: Optional[TaskPlannerAgent] = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global digital_human, text_to_video, local_video_generator, animatediff_generator, scheduler_agent, task_planner_agent
    logger.info("正在初始化数字人系统...")

    digital_human = DigitalHuman(config)
    await digital_human.initialize()

    # 初始化SiliconFlow文本到视频生成器
    t2v_config = config.get("text_to_video", {}).get("siliconflow", {})
    text_to_video = TextToVideoGenerator(t2v_config)

    # 初始化本地视频生成器（延迟加载模型）
    local_video_generator = LocalVideoGenerator()

    # 初始化AnimateDiff生成器（延迟加载模型，适合低显存GPU）
    animatediff_generator = AnimateDiffGenerator()

    # 初始化调度智能体
    scheduler_agent = SchedulerAgent(digital_human.llm)
    logger.info("调度智能体初始化完成")

    # 初始化任务规划智能体
    task_planner_agent = TaskPlannerAgent(digital_human.llm)
    logger.info("任务规划智能体初始化完成")

    # 为文档生成器设置图像生成器
    if digital_human and digital_human.image_gen:
        document_generator.set_image_generator(digital_human.image_gen)
        logger.info("文档生成器已启用图像生成功能")

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




# ==================== ZeroToken管理 (本地客户端) ====================

# 支持的平台列表
ZEROTOKEN_PLATFORMS = {
    'deepseek': {
        'name': 'DeepSeek',
        'models': ['deepseek-chat', 'deepseek-reasoner'],
        'login_url': 'https://chat.deepseek.com',
    },
    'doubao': {
        'name': '豆包',
        'models': ['doubao-seed-2.0', 'doubao-pro'],
        'login_url': 'https://www.doubao.com',
    },
    'claude': {
        'name': 'Claude',
        'models': ['claude-sonnet-4-6'],
        'login_url': 'https://claude.ai',
    },
    'kimi': {
        'name': 'Kimi',
        'models': ['moonshot-v1-8k'],
        'login_url': 'https://kimi.moonshot.cn',
    },
}


@app.get("/api/zerotoken/platforms")
async def list_platforms():
    """列出支持的ZeroToken平台"""
    from core.zero_token_base import CredentialManager
    
    cred_manager = CredentialManager()
    saved_platforms = cred_manager.list_platforms()
    
    platforms = []
    for pid, pinfo in ZEROTOKEN_PLATFORMS.items():
        platforms.append({
            "id": pid,
            "name": pinfo["name"],
            "models": pinfo["models"],
            "login_url": pinfo["login_url"],
            "has_credentials": pid in saved_platforms
        })
    
    return {
        "platforms": platforms,
        "saved_platforms": saved_platforms
    }


@app.get("/api/zerotoken/credentials/{platform}")
async def get_credential_status(platform: str):
    """获取平台凭证状态"""
    from core.zero_token_base import CredentialManager
    
    if platform not in ZEROTOKEN_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")
    
    cred_manager = CredentialManager()
    credentials = cred_manager.load_credentials(platform)
    
    return {
        "platform": platform,
        "has_credentials": credentials is not None,
        "login_url": ZEROTOKEN_PLATFORMS[platform]["login_url"]
    }


@app.post("/api/zerotoken/credentials/{platform}")
async def set_credential(platform: str, credentials: dict):
    """设置平台凭证"""
    from core.zero_token_base import CredentialManager, WebCredentials
    
    if platform not in ZEROTOKEN_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")
    
    try:
        cred_manager = CredentialManager()
        
        # 构建凭证对象
        cred = WebCredentials(
            cookie=credentials.get("cookie", ""),
            bearer=credentials.get("bearer"),
            user_agent=credentials.get("user_agent"),
            sessionid=credentials.get("sessionid"),
            ttwid=credentials.get("ttwid"),
            device_id=credentials.get("device_id"),
            ms_token=credentials.get("ms_token"),
        )
        
        cred_manager.save_credentials(platform, cred)
        
        # 重新初始化客户端
        if digital_human and digital_human.llm:
            digital_human.llm.zero_token_platform = platform
            digital_human.llm._init_zero_token()
        
        return {"success": True, "message": f"{platform} 凭证已保存"}
    except Exception as e:
        logger.error(f"保存凭证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/zerotoken/credentials/{platform}")
async def delete_credential(platform: str):
    """删除平台凭证"""
    from core.zero_token_base import CredentialManager
    
    if platform not in ZEROTOKEN_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")
    
    try:
        cred_manager = CredentialManager()
        cred_manager.delete_credentials(platform)
        return {"success": True, "message": f"{platform} 凭证已删除"}
    except Exception as e:
        logger.error(f"删除凭证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/test")
async def test_chat_connection(request: dict):
    """测试 ZeroToken 凭证是否有效"""
    platform = request.get("zero_token_platform", "deepseek")
    
    if platform not in ZEROTOKEN_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"不支持的平台: {platform}")
    
    try:
        from core.zero_token_base import CredentialManager
        from core.llm_client import LLMClient
        
        cred_manager = CredentialManager()
        credentials = cred_manager.load_credentials(platform)
        
        if not credentials or not credentials.cookie:
            return {
                "success": False,
                "error": f"请先配置 {platform} 的凭证"
            }
        
        # 创建临时客户端测试连接
        llm = LLMClient(config.get("llm", {}))
        llm.call_mode = 'zeroToken'  # 设置调用模式
        llm.zero_token_platform = platform
        llm._init_zero_token()
        
        if not llm._zero_token_client:
            return {
                "success": False,
                "error": "客户端初始化失败，请检查凭证格式"
            }
        
        # 发送测试消息
        test_message = "请回复'测试成功'"
        response_text = await llm.generate(test_message, stream=False)
        
        if response_text:
            return {
                "success": True,
                "message": "连接成功",
                "response_preview": response_text[:100] + "..." if len(response_text) > 100 else response_text
            }
        else:
            return {
                "success": False,
                "error": "未收到响应，请检查凭证是否有效"
            }
            
    except Exception as e:
        logger.error(f"测试凭证失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 对话接口 ====================

@app.get("/api/ollama/models")
async def get_ollama_models():
    """获取 Ollama 可用模型列表"""
    try:
        ollama_config = config.get("llm", {}).get("ollama", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/api/tags", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_list = [{"name": m["name"], "size": m.get("size", 0), "modified": m.get("modified_at", "")} for m in models]
                return {
                    "success": True,
                    "models": model_list,
                    "count": len(model_list)
                }
            else:
                return {
                    "success": False,
                    "error": f"Ollama服务返回: {response.status_code}",
                    "models": []
                }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": "无法连接到Ollama服务，请确保Ollama正在运行",
            "models": []
        }
    except Exception as e:
        logger.error(f"获取Ollama模型失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "models": []
        }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    与数字人对话

    - text: 用户输入文本
    - generate_audio: 是否生成语音响应
    - generate_video: 是否生成视频响应
    - call_mode: 调用模式 (ollamaAPI/zeroToken)
    - zero_token_platform: ZeroToken平台 (deepseek/claude/doubao)
    - model: Ollama 模型名称
    - enable_search: 是否启用联网搜索
    """
    if not digital_human:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        # 动态切换调用模式
        if request.call_mode:
            digital_human.llm.call_mode = request.call_mode
            
            if request.call_mode == "zeroToken" and request.zero_token_platform:
                digital_human.llm.zero_token_platform = request.zero_token_platform
                logger.info(f"切换到ZeroToken模式，平台: {request.zero_token_platform}")
            elif request.call_mode == "ollamaAPI" and request.model:
                # 切换到指定的 Ollama 模型
                digital_human.llm.model = request.model
                logger.info(f"切换到Ollama模型: {request.model}")
            elif request.call_mode == "deepseekAPI":
                # DeepSeek API 模式
                if request.deepseek_model:
                    digital_human.llm.deepseek_model = request.deepseek_model
                logger.info(f"切换到DeepSeek API模式，模型: {digital_human.llm.deepseek_model}")
        
        result = await digital_human.chat(
            user_input=request.text,
            generate_audio=request.generate_audio,
            generate_video=request.generate_video,
            stream=False,
            enable_search=request.enable_search
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


# ==================== 意图识别与调度 ====================

class IntentDetectRequest(BaseModel):
    text: str
    context: Optional[List[Dict]] = None


class IntentConfirmRequest(BaseModel):
    text: str
    intent: str
    params: Dict
    confirmed: bool


@app.post("/api/intent/detect")
async def detect_intent(request: IntentDetectRequest):
    """
    检测用户输入的意图
    
    Returns:
        - intent: 意图类型 (chat/video/web/document)
        - confidence: 置信度
        - params: 提取的参数
        - needs_confirmation: 是否需要确认
        - confirmation_message: 确认提示消息
    """
    if not scheduler_agent:
        raise HTTPException(status_code=503, detail="调度智能体未初始化")
    
    try:
        intent_result = await scheduler_agent.detect_intent(request.text, request.context)
        
        return {
            "success": True,
            "data": {
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "params": intent_result.params,
                "needs_confirmation": intent_result.needs_confirmation,
                "confirmation_message": intent_result.confirmation_message
            }
        }
    except Exception as e:
        logger.error(f"意图识别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intent/execute")
async def execute_intent(request: IntentConfirmRequest):
    """
    执行意图对应的能力
    
    Args:
        - text: 原始用户输入
        - intent: 意图类型
        - params: 执行参数
        - confirmed: 用户是否确认
    """
    if not scheduler_agent:
        raise HTTPException(status_code=503, detail="调度智能体未初始化")
    
    if not request.confirmed:
        return {
            "success": False,
            "message": "用户取消操作"
        }
    
    try:
        # 映射意图类型
        intent_map = {
            "video": IntentType.VIDEO,
            "web": IntentType.WEB,
            "document": IntentType.DOCUMENT,
            "image": IntentType.IMAGE
        }
        
        intent = intent_map.get(request.intent, IntentType.CHAT)
        
        # 使用调度智能体的 execute_capability 方法
        result = await scheduler_agent.execute_capability(intent, request.params)
        
        # 格式化结果消息
        formatted_message = scheduler_agent.format_execution_result(result, intent)
        
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "formatted_message": formatted_message
        }
    except Exception as e:
        logger.error(f"意图执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intent/execute/stream")
async def execute_intent_stream(request: IntentConfirmRequest):
    """
    执行意图对应的能力（流式返回进度）
    
    使用 Server-Sent Events (SSE) 实时返回执行进度
    
    Args:
        - text: 原始用户输入
        - intent: 意图类型
        - params: 执行参数
        - confirmed: 用户是否确认
    """
    async def event_generator():
        progress_queue = asyncio.Queue()
        
        async def progress_callback(status: str, message: str, progress: int):
            """进度回调函数"""
            logger.info(f"[SSE] Progress callback: {status} - {message} ({progress}%)")
            await progress_queue.put({
                "type": "progress",
                "status": status,
                "message": message,
                "progress": progress
            })
        
        # 发送初始状态
        logger.info("[SSE] Sending start event")
        yield f"data: {json.dumps({'type': 'start', 'message': '开始执行任务...'}, ensure_ascii=False)}\n\n"
        
        if not scheduler_agent:
            yield f"data: {json.dumps({'type': 'error', 'message': '调度智能体未初始化'}, ensure_ascii=False)}\n\n"
            return
        
        if not request.confirmed:
            yield f"data: {json.dumps({'type': 'error', 'message': '用户取消操作'}, ensure_ascii=False)}\n\n"
            return
        
        try:
            # 映射意图类型
            intent_map = {
                "video": IntentType.VIDEO,
                "web": IntentType.WEB,
                "document": IntentType.DOCUMENT,
                "image": IntentType.IMAGE
            }
            
            intent = intent_map.get(request.intent, IntentType.CHAT)
            
            # 创建执行任务
            async def execute_with_progress():
                # 使用调度智能体的 execute_capability 方法（带进度回调）
                result = await scheduler_agent.execute_capability(
                    intent, 
                    request.params,
                    progress_callback=progress_callback
                )
                return result
            
            # 启动执行任务
            execute_task = asyncio.create_task(execute_with_progress())
            
            # 同时处理进度更新和执行结果
            while not execute_task.done():
                # 检查队列是否有数据
                if not progress_queue.empty():
                    progress_data = await progress_queue.get()
                    logger.info(f"[SSE] Sending progress event: {progress_data['message']}")
                    yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
                else:
                    # 短暂等待，避免 CPU 占用过高
                    await asyncio.sleep(0.05)
            
            # 处理剩余的进度更新
            while not progress_queue.empty():
                progress_data = await progress_queue.get()
                logger.info(f"[SSE] Sending remaining progress event: {progress_data['message']}")
                yield f"data: {json.dumps(progress_data, ensure_ascii=False)}\n\n"
            
            # 获取执行结果
            result = execute_task.result()
            
            # 格式化结果消息
            formatted_message = scheduler_agent.format_execution_result(result, intent)
            
            # 发送完成事件
            yield f"data: {json.dumps({
                'type': 'complete',
                'success': result.success,
                'message': result.message,
                'data': result.data,
                'formatted_message': formatted_message
            }, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"意图执行失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )




# ==================== 任务规划 ====================

class TaskPlanRequest(BaseModel):
    text: str
    execute: bool = False  # 是否立即执行


class TaskExecuteRequest(BaseModel):
    plan_id: str
    tasks: List[Dict]


@app.post("/api/task/plan")
async def plan_task(request: TaskPlanRequest):
    """
    规划任务
    
    Returns:
        - plan_id: 计划ID
        - tasks: 子任务列表
        - execution_mode: 执行模式
        - display_text: 格式化的计划文本
    """
    if not task_planner_agent:
        raise HTTPException(status_code=503, detail="任务规划智能体未初始化")
    
    try:
        # 规划任务
        plan = await task_planner_agent.plan_task(request.text)
        
        # 格式化显示
        display_text = task_planner_agent.format_plan_for_display(plan)
        
        # 序列化任务
        tasks_data = []
        for task in plan.sub_tasks:
            tasks_data.append({
                "id": task.id,
                "type": task.task_type.value,
                "description": task.description,
                "params": task.params,
                "dependencies": task.dependencies,
                "status": task.status
            })
        
        # 如果要求立即执行
        if request.execute:
            result = await task_planner_agent.execute_plan(
                plan,
                executor_callbacks=_get_task_executors()
            )
            return {
                "success": True,
                "data": {
                    "plan_id": str(uuid.uuid4()),
                    "tasks": tasks_data,
                    "execution_mode": plan.execution_mode.value,
                    "display_text": display_text,
                    "execution_result": result
                }
            }
        
        return {
            "success": True,
            "data": {
                "plan_id": str(uuid.uuid4()),
                "tasks": tasks_data,
                "execution_mode": plan.execution_mode.value,
                "display_text": display_text
            }
        }
    except Exception as e:
        logger.error(f"任务规划失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/task/execute")
async def execute_task_plan(request: TaskExecuteRequest):
    """
    执行任务计划
    """
    if not task_planner_agent:
        raise HTTPException(status_code=503, detail="任务规划智能体未初始化")
    
    try:
        # 重建任务计划
        from core.task_planner_agent import SubTask, TaskPlan, TaskType, ExecutionMode
        
        sub_tasks = []
        for task_data in request.tasks:
            task_type = TaskType(task_data.get("type", "custom"))
            sub_tasks.append(SubTask(
                id=task_data.get("id"),
                task_type=task_type,
                description=task_data.get("description", ""),
                params=task_data.get("params", {}),
                dependencies=task_data.get("dependencies", [])
            ))
        
        plan = TaskPlan(
            original_request="",
            sub_tasks=sub_tasks,
            execution_mode=ExecutionMode.SEQUENTIAL
        )
        
        # 执行
        result = await task_planner_agent.execute_plan(
            plan,
            executor_callbacks=_get_task_executors()
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"任务执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_task_executors():
    """获取任务执行器"""
    return {
        TaskType.SEARCH_WEB: _execute_search_web,
        TaskType.OPEN_BROWSER: _execute_open_browser,
        TaskType.NAVIGATE_URL: _execute_navigate_url,
        TaskType.INPUT_TEXT: _execute_input_text,
        TaskType.CLICK_ELEMENT: _execute_click_element,
        TaskType.EXTRACT_CONTENT: _execute_extract_content,
        TaskType.SUMMARIZE: _execute_summarize,
        TaskType.WAIT: _execute_wait,
        TaskType.CHAT: _execute_chat
    }


async def _execute_search_web(params: Dict) -> Dict:
    """执行网页搜索"""
    query = params.get("text", params.get("query", ""))
    
    # 使用现有的web_search模块
    if digital_human and digital_human.web_search:
        try:
            results = digital_human.web_search.search(query)
            return {
                "status": "success",
                "query": query,
                "results": results[:5] if results else [],
                "count": len(results) if results else 0
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    return {"status": "mock", "message": "网页搜索功能模拟", "query": query}


async def _execute_open_browser(params: Dict) -> Dict:
    """打开浏览器"""
    # 这里可以集成Playwright或Selenium
    return {
        "status": "success",
        "message": "浏览器已打开（模拟）",
        "browser_id": str(uuid.uuid4())
    }


async def _execute_navigate_url(params: Dict) -> Dict:
    """导航到URL"""
    url = params.get("url", "")
    return {
        "status": "success",
        "message": f"已导航到 {url}（模拟）",
        "url": url
    }


async def _execute_input_text(params: Dict) -> Dict:
    """输入文本"""
    text = params.get("text", "")
    selector = params.get("selector", "")
    return {
        "status": "success",
        "message": f"已在 {selector} 输入文本（模拟）",
        "text": text
    }


async def _execute_click_element(params: Dict) -> Dict:
    """点击元素"""
    selector = params.get("selector", "")
    return {
        "status": "success",
        "message": f"已点击 {selector}（模拟）"
    }


async def _execute_extract_content(params: Dict) -> Dict:
    """提取内容"""
    selector = params.get("selector", "")
    return {
        "status": "success",
        "message": "内容已提取（模拟）",
        "content": "这是提取的示例内容..."
    }


async def _execute_summarize(params: Dict) -> Dict:
    """总结内容"""
    prev_results = {k: v for k, v in params.items() if k.startswith("_prev_result_")}
    
    # 合并前置结果
    content = ""
    search_results = []
    
    for key, result in prev_results.items():
        if isinstance(result, dict):
            # 处理搜索结果
            if result.get("results"):
                search_results = result.get("results", [])
                for item in search_results:
                    if isinstance(item, dict):
                        content += f"- {item.get('title', '')}: {item.get('snippet', item.get('desc', ''))}\n"
                    else:
                        content += str(item) + "\n"
            else:
                content += str(result.get("content", ""))
    
    # 也检查直接传入的内容
    direct_content = params.get("_prev_results_content", "")
    if direct_content:
        content = direct_content if not content else content + "\n" + direct_content
    
    if content and digital_human:
        # 使用正确的异步调用和参数
        summary = await digital_human.llm.generate(
            prompt=f"""请根据以下搜索结果，整理并总结关键信息：

{content[:3000]}

请用简洁的中文总结要点："""
        )
        return {
            "status": "success",
            "summary": summary,
            "original_length": len(content),
            "source_count": len(search_results)
        }
    
    return {
        "status": "success",
        "message": "没有找到需要总结的内容",
        "summary": "抱歉，未能获取到相关内容进行总结。请尝试重新搜索或提供更多信息。"
    }


async def _execute_wait(params: Dict) -> Dict:
    """等待"""
    seconds = params.get("seconds", 1)
    await asyncio.sleep(seconds)
    return {
        "status": "success",
        "message": f"已等待 {seconds} 秒"
    }


async def _execute_chat(params: Dict) -> Dict:
    """普通对话"""
    query = params.get("query", "")
    
    if digital_human:
        result = await digital_human.chat(user_input=query, generate_audio=False)
        return {
            "status": "success",
            "response": result.get("text", "")
        }
    
    return {
        "status": "success",
        "message": "对话响应（模拟）",
        "response": "这是模拟的对话响应"
    }


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
                # 动态切换调用模式
                call_mode = message.get("call_mode")
                zero_token_platform = message.get("zero_token_platform")
                ollama_model = message.get("model")  # Ollama 模型参数
                deepseek_model = message.get("deepseek_model")  # DeepSeek 模型参数
                enable_search = message.get("enable_search", True)  # 是否启用联网搜索
                
                if call_mode:
                    digital_human.llm.call_mode = call_mode
                    if call_mode == "zeroToken" and zero_token_platform:
                        digital_human.llm.zero_token_platform = zero_token_platform
                        zero_token_model = message.get("zero_token_model")
                        if zero_token_model:
                            digital_human.llm.zero_token_model = zero_token_model
                        logger.info(f"WebSocket切换到ZeroToken模式，平台: {zero_token_platform}, 模型: {digital_human.llm.zero_token_model or '默认'}")
                    elif call_mode == "ollamaAPI" and ollama_model:
                        # 切换到指定的 Ollama 模型
                        digital_human.llm.model = ollama_model
                        logger.info(f"WebSocket切换到Ollama模型: {ollama_model}")
                    elif call_mode == "deepseekAPI":
                        # DeepSeek API 模式
                        if deepseek_model:
                            digital_human.llm.deepseek_model = deepseek_model
                        logger.info(f"WebSocket切换到DeepSeek API模式，模型: {digital_human.llm.deepseek_model}")
                
                # 流式生成回复
                full_response = ""
                try:
                    async for chunk in digital_human.chat_stream(
                        message.get("text", ""),
                        enable_search=enable_search
                    ):
                        full_response += chunk
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk
                        })
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"流式生成失败: {error_msg}")
                    
                    # 检查是否是凭证未配置错误
                    if "凭证" in error_msg or "credentials" in error_msg.lower():
                        await websocket.send_json({
                            "type": "error",
                            "error": "credentials_not_configured",
                            "message": f"请先配置 {digital_human.llm.zero_token_platform} 平台的凭证",
                            "login_url": digital_human.llm.get_login_url() if hasattr(digital_human.llm, 'get_login_url') else None
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "error": "generation_error",
                            "message": error_msg
                        })
                    continue

                # 生成语音
                audio_url = None
                try:
                    if digital_human.tts and message.get("generate_audio", True):
                        voice = digital_human.current_avatar.voice if digital_human.current_avatar else None
                        audio_path = await digital_human.tts.synthesize(
                            text=full_response,
                            voice=voice
                        )
                        audio_url = _path_to_url(audio_path)
                        logger.info(f"语音合成完成，URL: {audio_url}")
                except Exception as e:
                    logger.error(f"语音合成失败: {e}")

                # 发送完成信号（包含音频URL）
                response = {
                    "type": "complete",
                    "content": full_response
                }
                if audio_url:
                    response["audio_url"] = audio_url
                
                await websocket.send_json(response)

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


# ==================== 文本到视频生成 ====================

@app.post("/api/video/text-to-video")
async def text_to_video_generate(request: TextToVideoRequest):
    """
    根据文本提示生成视频
    
    - prompt: 视频描述文本（建议详细描述动作、外貌、镜头角度、环境细节）
    - negative_prompt: 负面提示词
    - image_size: 视频分辨率 (1280x720, 720x1280, 960x960)
    - seed: 随机种子
    - timeout: 超时时间（秒）
    - provider: 生成源 ("siliconflow", "local", "animatediff")
    """
    provider = request.provider.lower()
    
    # 解析分辨率
    width, height = 512, 512
    if "x" in request.image_size:
        parts = request.image_size.lower().split("x")
        width, height = int(parts[0]), int(parts[1])
    
    if provider == "animatediff":
        # 使用AnimateDiff生成（适合低显存GPU）
        if not animatediff_generator:
            raise HTTPException(status_code=503, detail="AnimateDiff服务未初始化")
        
        try:
            video_path = await animatediff_generator.generate_from_text(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                num_frames=16,
                width=min(width, 512),
                height=min(height, 512),
                seed=request.seed
            )

            return {
                "success": True,
                "data": {
                    "video_path": video_path,
                    "video_url": _path_to_url(video_path),
                    "provider": "animatediff"
                }
            }
        except Exception as e:
            logger.error(f"AnimateDiff生成失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    elif provider == "local":
        # 使用本地SVD模型生成
        if not local_video_generator:
            raise HTTPException(status_code=503, detail="本地视频生成服务未初始化")
        
        try:
            video_path = await local_video_generator.generate_from_text(
                prompt=request.prompt,
                width=width,
                height=height,
                seed=request.seed
            )

            return {
                "success": True,
                "data": {
                    "video_path": video_path,
                    "video_url": _path_to_url(video_path),
                    "provider": "local"
                }
            }
        except Exception as e:
            logger.error(f"本地视频生成失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        # 使用SiliconFlow API生成
        if not text_to_video:
            raise HTTPException(status_code=503, detail="SiliconFlow视频生成服务未初始化")

        try:
            video_path = await text_to_video.generate_from_text(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                image_size=request.image_size,
                seed=request.seed,
                timeout=request.timeout
            )

            return {
                "success": True,
                "data": {
                    "video_path": video_path,
                    "video_url": _path_to_url(video_path),
                    "provider": "siliconflow"
                }
            }
        except Exception as e:
            logger.error(f"SiliconFlow视频生成失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/video/image-to-video")
async def image_to_video_generate(request: ImageToVideoRequest):
    """
    根据图片和文本提示生成视频
    
    - prompt: 视频描述文本
    - image_url: 图片URL（可选，如果没有则需上传图片）
    - negative_prompt: 负面提示词
    - image_size: 视频分辨率
    - seed: 随机种子
    - timeout: 超时时间（秒）
    """
    if not text_to_video:
        raise HTTPException(status_code=503, detail="文本到视频服务未初始化")

    try:
        # 如果提供了图片URL，先下载图片
        if request.image_url:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(request.image_url)
                response.raise_for_status()
                
                # 保存临时图片
                temp_dir = Path("outputs/temp")
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_image = temp_dir / f"temp_{uuid.uuid4().hex}.png"
                
                with open(temp_image, "wb") as f:
                    f.write(response.content)
                
                image_path = str(temp_image)
        else:
            raise HTTPException(status_code=400, detail="请提供图片URL或上传图片")

        video_path = await text_to_video.generate_from_image(
            prompt=request.prompt,
            image_path=image_path,
            negative_prompt=request.negative_prompt,
            image_size=request.image_size,
            seed=request.seed,
            timeout=request.timeout
        )

        return {
            "success": True,
            "data": {
                "video_path": video_path,
                "video_url": _path_to_url(video_path)
            }
        }
    except Exception as e:
        logger.error(f"图生视频失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/video/image-to-video/upload")
async def image_to_video_upload(
    file: UploadFile = File(...),
    prompt: str = "",
    negative_prompt: str = "",
    image_size: str = "1280x720"
):
    """
    上传图片并生成视频
    """
    if not text_to_video:
        raise HTTPException(status_code=503, detail="文本到视频服务未初始化")

    try:
        # 保存上传的图片
        temp_dir = Path("outputs/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        file_ext = Path(file.filename).suffix or ".png"
        temp_image = temp_dir / f"upload_{uuid.uuid4().hex}{file_ext}"
        
        async with aiofiles.open(temp_image, "wb") as f:
            content = await file.read()
            await f.write(content)

        video_path = await text_to_video.generate_from_image(
            prompt=prompt,
            image_path=str(temp_image),
            negative_prompt=negative_prompt,
            image_size=image_size
        )

        return {
            "success": True,
            "data": {
                "video_path": video_path,
                "video_url": _path_to_url(video_path)
            }
        }
    except Exception as e:
        logger.error(f"图生视频失败: {e}")
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


# ==================== Fara 网络操作代理 ====================

class FaraTaskRequest(BaseModel):
    """Fara 任务请求"""
    task: str
    context: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


@app.get("/api/fara/tasks")
async def get_fara_tasks():
    """获取预定义的网络操作任务列表"""
    try:
        from utils.fara_agent import get_fara_agent
        agent = get_fara_agent()
        tasks = agent.get_predefined_tasks()
        return {
            "success": True,
            "data": {"tasks": tasks}
        }
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/fara/execute")
async def execute_fara_task(request: FaraTaskRequest):
    """执行网络操作任务"""
    try:
        from utils.fara_agent import execute_web_task
        
        result = await execute_web_task(
            task=request.task,
            context=request.context
        )
        
        return {
            "success": result.get("success", False),
            "data": {
                "response": result.get("response", ""),
                "actions": result.get("actions", []),
                "task": result.get("task", request.task),
                "fallback_used": result.get("fallback_used", False),
                "note": result.get("note", "")
            },
            "error": result.get("error")
        }
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/fara/status")
async def get_fara_status():
    """获取 Fara 模型状态"""
    try:
        from utils.fara_agent import get_fara_agent
        agent = get_fara_agent()
        
        return {
            "success": True,
            "data": {
                "initialized": agent._initialized,
                "model_path": "E:\\AI\\models\\fara",
                "available": os.path.exists("E:\\AI\\models\\fara")
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ==================== 文档生成 ====================

class DocumentGenerateRequest(BaseModel):
    """文档生成请求"""
    prompt: str  # 提示词
    doc_type: str  # 文档类型: word/excel/ppt/pdf/txt/md
    title: Optional[str] = None  # 文档标题
    filename: Optional[str] = None  # 文件名（不含扩展名）


@app.get("/api/document/types")
async def get_document_types():
    """获取支持的文档类型"""
    return {
        "success": True,
        "data": document_generator.get_supported_types()
    }


@app.post("/api/document/generate")
async def generate_document(request: DocumentGenerateRequest):
    """
    生成文档

    根据提示词生成指定格式的文档
    """
    try:
        # 首先使用 LLM 根据提示词生成内容
        if not digital_human:
            raise HTTPException(status_code=503, detail="系统未初始化")

        # 构建文档生成提示
        doc_type_names = {
            "word": "Word文档",
            "excel": "Excel表格（内容会按行分割，逗号或制表符分隔列）",
            "ppt": "PPT演示文稿",
            "pdf": "PDF文档",
            "txt": "纯文本文件",
            "md": "Markdown文档"
        }

        # PPT 专用提示词（参考 NotebookLM Slide Decks）
        if request.doc_type == "ppt":
            system_prompt = f"""你是一个专业的PPT演示文稿设计专家，参考 NotebookLM Slide Decks 的设计理念。

当前任务：生成一份专业级的演示文稿
文档标题：{request.title or '演示文稿'}

请按以下 JSON 格式输出，确保生成专业、精美的幻灯片：

```json
{{
  "title": "演示文稿主标题",
  "slides": [
    {{
      "type": "title",
      "title": "封面标题",
      "subtitle": "副标题/日期/演讲者"
    }},
    {{
      "type": "toc",
      "title": "目录",
      "items": ["第一部分标题", "第二部分标题", "第三部分标题"]
    }},
    {{
      "type": "content",
      "title": "幻灯片标题",
      "points": ["要点1", "要点2", "要点3", "要点4"]
    }},
    {{
      "type": "two_column",
      "title": "对比/并列内容标题",
      "left": ["左侧要点1", "左侧要点2"],
      "right": ["右侧要点1", "右侧要点2"]
    }},
    {{
      "type": "image",
      "title": "图文混排标题",
      "image_prompt": "配图描述（如：数据图表、流程图、示意图）",
      "points": ["要点1", "要点2"]
    }},
    {{
      "type": "summary",
      "title": "总结",
      "points": ["核心要点1", "核心要点2", "感谢观看"]
    }}
  ]
}}
```

设计原则：
1. **结构清晰**：标题页 → 目录 → 内容页 → 总结页
2. **内容精炼**：每页不超过 4-6 个要点
3. **逻辑连贯**：各页面之间有清晰的逻辑关系
4. **视觉丰富**：适当使用 two_column 和 image 类型增加变化
5. **重点突出**：关键信息放在内容页，总结页提炼核心

请根据用户需求生成完整的 JSON 结构内容。"""
        else:
            system_prompt = f"""你是一个专业的文档生成助手。用户会提供文档需求，请生成完整的文档内容。

当前要生成的文档类型：{doc_type_names.get(request.doc_type, request.doc_type)}
文档标题：{request.title or '未命名文档'}

请根据用户的需求生成专业、完整的文档内容。
- 如果是Excel，请用逗号或制表符分隔各列
- 内容要详细、专业、格式清晰
"""

        # 调用 LLM 生成内容
        content = await digital_human.llm.generate(
            prompt=request.prompt,
            system_prompt=system_prompt,
            stream=False
        )

        # 生成文档
        result = await document_generator.generate(
            content=content,
            doc_type=request.doc_type,
            filename=request.filename,
            title=request.title
        )

        if result["success"]:
            # 转换路径为 URL
            file_path = result["file_path"]
            file_url = _path_to_url(file_path)

            return {
                "success": True,
                "data": {
                    "file_path": file_path,
                    "file_url": file_url,
                    "file_name": result["file_name"],
                    "doc_type": result["doc_type"],
                    "doc_name": result["doc_name"],
                    "content": content
                }
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "文档生成失败"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 页面代理 ====================

PROXY_TARGET_URL = "https://www.baidu.com"
PROXY_BASE_URL = "https://www.baidu.com"


@app.get("/proxy/page")
async def proxy_page():
    """代理目标页面，移除 X-Frame-Options 头"""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(PROXY_TARGET_URL)

            # 获取原始内容
            content = response.text

            # 注入 base 标签修复相对路径
            base_tag = f'<base href="{PROXY_BASE_URL}/">'
            if '<head' in content:
                content = content.replace('<head', f'<head>\n        {base_tag}', 1)
            elif '<html' in content:
                content = content.replace('<html', f'<html>\n    <head>{base_tag}</head>', 1)
            else:
                content = f'<head>{base_tag}</head>' + content

            # 创建 HTML 响应，移除阻止 iframe 的头
            html_response = HTMLResponse(
                content=content,
                status_code=response.status_code,
                headers={
                    "Content-Type": response.headers.get("Content-Type", "text/html"),
                    "Cache-Control": "no-cache",
                }
            )
            return html_response
    except Exception as e:
        logger.error(f"代理页面失败: {e}")
        return HTMLResponse(
            content=f"<html><body><h1>加载失败</h1><p>无法加载目标页面: {str(e)}</p></body></html>",
            status_code=500
        )


@app.api_route("/proxy/resource/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_resource(path: str):
    """代理静态资源请求"""
    try:
        target_url = f"{PROXY_BASE_URL}/{path}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if "?" in target_url or len(path) > 100:
                # 如果路径看起来像是完整 URL 的一部分，尝试从 query 获取
                pass

            response = await client.get(target_url)

            # 移除可能阻止缓存的头
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in excluded_headers
            }

            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("Content-Type", "application/octet-stream"),
                headers=headers
            )
    except Exception as e:
        logger.error(f"代理资源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8000)

    uvicorn.run(app, host=host, port=port)