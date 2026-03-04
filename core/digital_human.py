# -*- coding: utf-8 -*-
"""数字人核心类 - 整合所有组件"""

import os
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from pathlib import Path
from loguru import logger
from dataclasses import dataclass, field
from datetime import datetime

from .llm_client import LLMClient
from .tts_engine import TTSEngine
from .stt_engine import STTEngine
from .image_generator import ImageGenerator
from .video_generator import VideoGenerator
from .web_search import WebSearchEngine, format_search_results


@dataclass
class Avatar:
    """数字人形象"""
    id: str
    name: str
    image_path: str
    description: str = ""
    style: str = "professional"
    gender: str = "female"
    voice: str = "zh-CN-XiaoxiaoNeural"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Message:
    """对话消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    audio_path: Optional[str] = None
    video_path: Optional[str] = None


class DigitalHuman:
    """数字人主类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # 初始化各组件
        self.llm = LLMClient(config.get("llm", {}))
        self.tts = TTSEngine(config.get("tts", {}))
        self.stt = STTEngine(config.get("stt", {}))
        self.image_gen = ImageGenerator(config.get("image", {}))
        self.video_gen = VideoGenerator(config.get("video", {}))
        self.web_search = WebSearchEngine(config.get("web_search", {}))

        # 数字人配置
        self.dh_config = config.get("digital_human", {})
        self.default_avatar_config = self.dh_config.get("default_avatar", {})

        # 对话配置
        self.conv_config = config.get("conversation", {})
        self.max_history = self.conv_config.get("max_history", 20)

        # 输出目录
        self.output_dir = Path(config.get("output", {}).get("video_dir", "outputs/videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 当前状态
        self.current_avatar: Optional[Avatar] = None
        self.conversation_history: List[Dict[str, str]] = []

        # 数字人形象缓存
        self.avatars: Dict[str, Avatar] = {}

        logger.info("数字人系统初始化完成")

    async def initialize(self) -> bool:
        """初始化系统，检查各组件状态"""
        logger.info("检查系统组件状态...")

        # 检查LLM
        llm_ok = await self.llm.check_health()
        logger.info(f"LLM服务: {'OK' if llm_ok else 'FAIL'}")

        # 检查TTS (Edge-TTS无需检查)
        logger.info("TTS服务: OK (Edge-TTS)")

        # 检查STT
        stt_ok = await self.stt.check_health()
        logger.info(f"语音识别: {'OK' if stt_ok else 'FAIL'}")

        # 检查图像生成
        image_ok = await self.image_gen.check_health()
        logger.info(f"图像生成: {'OK' if image_ok else '使用占位图'}")

        # 检查视频生成
        video_ok = await self.video_gen.check_health()
        logger.info(f"视频生成: {'OK' if video_ok else '使用简单合成'}")

        # 检查网络搜索
        search_ok = await self.web_search.check_health()
        logger.info(f"网络搜索: {'OK' if search_ok else 'FAIL'}")

        # 加载默认数字人
        await self.load_default_avatar()

        return True

    async def load_default_avatar(self) -> Avatar:
        """加载或创建默认数字人形象"""
        avatar_dir = Path("outputs/avatars")
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已有默认形象
        default_path = avatar_dir / "default_avatar.png"
        if default_path.exists():
            self.current_avatar = Avatar(
                id="default",
                name=self.default_avatar_config.get("name", "小美"),
                image_path=str(default_path),
                description=self.default_avatar_config.get("description", ""),
                style=self.default_avatar_config.get("style", "professional")
            )
            logger.info(f"加载默认数字人形象: {self.current_avatar.name}")
            return self.current_avatar

        # 创建默认形象
        return await self.create_avatar(
            name=self.default_avatar_config.get("name", "小美"),
            description=self.default_avatar_config.get("description", "专业的AI助手，亲切友好"),
            style=self.default_avatar_config.get("style", "professional"),
            save_as_default=True
        )

    async def create_avatar(
        self,
        name: str,
        description: str = "",
        style: str = "professional",
        gender: str = "female",
        age: str = "young",
        expression: str = "smile",
        pose: str = "front",
        background: str = "clean",
        voice: str = "zh-CN-XiaoxiaoNeural",
        reference_image: Optional[str] = None,
        save_as_default: bool = False
    ) -> Avatar:
        """
        创建新的数字人形象

        Args:
            name: 数字人名称
            description: 形象描述
            style: 风格 (professional, casual, anime, realistic, cartoon, artistic)
            gender: 性别
            age: 年龄 (young, middle, senior)
            expression: 表情 (smile, serious, friendly, confident, neutral)
            pose: 姿势 (front, slight_angle, profile)
            background: 背景 (clean, office, outdoor, abstract)
            voice: 声音
            reference_image: 参考图片路径
            save_as_default: 是否设为默认

        Returns:
            创建的Avatar对象
        """
        avatar_id = str(uuid.uuid4())[:8]
        avatar_dir = Path("outputs/avatars")
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # 生成图像
        if reference_image and os.path.exists(reference_image):
            # 使用参考图像
            image_path = str(avatar_dir / f"{avatar_id}.png")
            import shutil
            shutil.copy(reference_image, image_path)
        else:
            # AI生成图像
            output_path = str(avatar_dir / f"{avatar_id}.png")
            image_path = await self.image_gen.generate_avatar(
                description=description,
                style=style,
                gender=gender,
                age=age,
                expression=expression,
                pose=pose,
                background=background,
                output_file=output_path
            )

        # 创建Avatar对象
        avatar = Avatar(
            id=avatar_id,
            name=name,
            image_path=image_path,
            description=description,
            style=style,
            gender=gender,
            voice=voice
        )

        # 缓存
        self.avatars[avatar_id] = avatar

        # 设为默认
        if save_as_default:
            import shutil
            shutil.copy(image_path, avatar_dir / "default_avatar.png")
            self.current_avatar = avatar

        logger.info(f"创建数字人形象: {name} ({avatar_id})")
        return avatar

    def set_avatar(self, avatar_id: str) -> bool:
        """设置当前使用的数字人形象"""
        if avatar_id in self.avatars:
            self.current_avatar = self.avatars[avatar_id]
            logger.info(f"切换数字人形象: {self.current_avatar.name}")
            return True
        return False

    def _needs_web_search(self, user_input: str) -> bool:
        """判断是否需要联网搜索"""
        # 搜索触发关键词
        search_keywords = [
            "最新", "今天", "现在", "当前", "最近", "新闻", "天气",
            "实时", "最新消息", "发生了什么", "有什么新闻",
            "查询", "搜索", "查找", "帮我查", "上网查",
            "股价", "汇率", "行情", "比分", "直播",
            "什么是", "怎么看待", "如何评价", "有什么变化"
        ]

        # 问题模式
        question_patterns = [
            r".*最新.*",
            r".*今天.*天气.*",
            r".*现在.*情况.*",
            r".*最近.*新闻.*",
            r".*当前.*",
            r".*帮我(搜索|查|找).*",
            r".*(搜索|查一下|查查).*"
        ]

        import re
        user_input_lower = user_input.lower()

        # 检查关键词
        for keyword in search_keywords:
            if keyword in user_input_lower:
                return True

        # 检查问题模式
        for pattern in question_patterns:
            if re.match(pattern, user_input_lower):
                return True

        return False

    def _extract_search_query(self, user_input: str) -> str:
        """从用户输入中提取搜索关键词"""
        import re

        # 移除常见的无关词
        stop_words = ["帮我", "请", "查一下", "查查", "搜索", "查找", "告诉我", "我想知道", "我想了解"]
        query = user_input
        for word in stop_words:
            query = query.replace(word, "")

        # 提取引号中的内容
        match = re.search(r'[""「」『』](.+?)[""「」『』]', query)
        if match:
            return match.group(1)

        return query.strip()

    async def chat(
        self,
        user_input: str,
        generate_audio: bool = True,
        generate_video: bool = False,
        stream: bool = True,
        enable_search: bool = True
    ) -> Dict[str, Any]:
        """
        与数字人对话

        Args:
            user_input: 用户输入
            generate_audio: 是否生成语音
            generate_video: 是否生成视频
            stream: 是否流式输出
            enable_search: 是否启用联网搜索

        Returns:
            包含回复、音频路径、视频路径的字典
        """
        result = {
            "text": "",
            "audio_path": None,
            "video_path": None,
            "search_used": False,
            "search_results": None
        }

        # 构建系统提示
        system_prompt = self.conv_config.get("system_prompt", "").format(
            name=self.current_avatar.name if self.current_avatar else "AI助手",
            description=self.current_avatar.description if self.current_avatar else ""
        )

        # 添加联网能力说明
        system_prompt += "\n\n你拥有联网搜索能力，可以获取实时信息。当用户询问最新消息、天气、新闻等需要实时信息的问题时，系统会自动为你提供搜索结果。"

        # 检查是否需要联网搜索
        search_context = ""
        if enable_search and self._needs_web_search(user_input):
            search_query = self._extract_search_query(user_input)
            logger.info(f"触发联网搜索: {search_query}")

            search_result = await self.web_search.search(search_query, max_results=3, extract_content=True)

            if search_result["success"] and search_result["results"]:
                search_context = format_search_results(search_result)
                system_prompt += f"\n\n以下是相关的网络搜索结果，请根据这些信息回答用户问题：\n\n{search_context}"
                result["search_used"] = True
                result["search_results"] = search_result["results"]
                logger.info(f"搜索完成，获取 {len(search_result['results'])} 条结果")
            else:
                logger.warning(f"搜索失败或无结果: {search_result.get('error', '无结果')}")

        # 添加用户消息到历史
        self.conversation_history.append({"role": "user", "content": user_input})

        # 限制历史长度
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2:]

        # 生成回复
        try:
            if stream:
                # 流式生成
                response_text = ""
                async for chunk in await self.llm.generate(
                    prompt=user_input,
                    system_prompt=system_prompt,
                    history=self.conversation_history[:-1],
                    stream=True
                ):
                    response_text += chunk
                    # 可以在这里实现流式回调

                result["text"] = response_text
            else:
                # 非流式生成
                result["text"] = await self.llm.generate(
                    prompt=user_input,
                    system_prompt=system_prompt,
                    history=self.conversation_history[:-1],
                    stream=False
                )

            # 添加助手回复到历史
            self.conversation_history.append({"role": "assistant", "content": result["text"]})

            # 生成语音
            if generate_audio:
                voice = self.current_avatar.voice if self.current_avatar else None
                result["audio_path"] = await self.tts.synthesize(
                    text=result["text"],
                    voice=voice
                )

            # 生成视频
            if generate_video and self.current_avatar:
                result["video_path"] = await self.video_gen.generate_with_text(
                    image_path=self.current_avatar.image_path,
                    text=result["text"],
                    tts_engine=self.tts
                )

        except Exception as e:
            logger.error(f"对话生成失败: {e}")
            raise

        return result

    async def chat_stream(
        self,
        user_input: str
    ) -> AsyncGenerator[str, None]:
        """
        流式对话生成

        Args:
            user_input: 用户输入

        Yields:
            文本片段
        """
        # 构建系统提示
        system_prompt = self.conv_config.get("system_prompt", "").format(
            name=self.current_avatar.name if self.current_avatar else "AI助手",
            description=self.current_avatar.description if self.current_avatar else ""
        )

        # 添加用户消息到历史
        self.conversation_history.append({"role": "user", "content": user_input})

        # 流式生成
        full_response = ""
        async for chunk in await self.llm.generate(
            prompt=user_input,
            system_prompt=system_prompt,
            history=self.conversation_history[:-1],
            stream=True
        ):
            full_response += chunk
            yield chunk

        # 添加完整回复到历史
        self.conversation_history.append({"role": "assistant", "content": full_response})

    async def transcribe_audio(
        self,
        audio_file: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        语音识别

        Args:
            audio_file: 音频文件路径
            language: 语言代码

        Returns:
            识别结果字典
        """
        logger.info(f"开始语音识别: {audio_file}")

        result = await self.stt.transcribe(audio_file, language)

        logger.info(f"语音识别完成: {result['text']}")

        return result

    async def chat_with_audio(
        self,
        audio_file: str,
        language: Optional[str] = None,
        generate_audio: bool = True,
        generate_video: bool = False
    ) -> Dict[str, Any]:
        """
        通过语音进行对话 (语音识别 + 对话 + 语音合成)

        Args:
            audio_file: 音频文件路径
            language: 语言代码
            generate_audio: 是否生成语音响应
            generate_video: 是否生成视频响应

        Returns:
            包含识别文本、回复、音频、视频的字典
        """
        # 1. 语音识别
        stt_result = await self.transcribe_audio(audio_file, language)
        user_text = stt_result["text"]

        # 2. 对话
        chat_result = await self.chat(
            user_input=user_text,
            generate_audio=generate_audio,
            generate_video=generate_video,
            stream=False
        )

        # 3. 返回完整结果
        return {
            "recognized_text": user_text,
            "stt_result": stt_result,
            "response": chat_result
        }

    async def generate_response_video(
        self,
        text: str,
        avatar_id: Optional[str] = None
    ) -> str:
        """
        为指定文本生成数字人视频

        Args:
            text: 要说的文本
            avatar_id: 使用的数字人ID，默认使用当前

        Returns:
            视频文件路径
        """
        avatar = self.avatars.get(avatar_id) or self.current_avatar
        if not avatar:
            raise ValueError("没有可用的数字人形象")

        return await self.video_gen.generate_with_text(
            image_path=avatar.image_path,
            text=text,
            tts_engine=self.tts
        )

    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        logger.info("对话历史已清除")

    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.conversation_history[-limit:]

    def save_session(self, file_path: str):
        """保存当前会话"""
        session_data = {
            "avatar": self.current_avatar.__dict__ if self.current_avatar else None,
            "history": self.conversation_history
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        logger.info(f"会话已保存: {file_path}")

    def load_session(self, file_path: str):
        """加载会话"""
        with open(file_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        if session_data.get("avatar"):
            self.current_avatar = Avatar(**session_data["avatar"])

        self.conversation_history = session_data.get("history", [])
        logger.info(f"会话已加载: {file_path}")

    async def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        llm_ok = await self.llm.check_health()
        stt_ok = await self.stt.check_health()
        image_ok = await self.image_gen.check_health()
        video_ok = await self.video_gen.check_health()

        return {
            "status": "running",
            "components": {
                "llm": {
                    "provider": self.llm.provider,
                    "healthy": llm_ok
                },
                "tts": {
                    "provider": self.tts.provider,
                    "healthy": True
                },
                "stt": {
                    "provider": self.stt.provider,
                    "healthy": stt_ok
                },
                "image": {
                    "provider": self.image_gen.provider,
                    "healthy": image_ok
                },
                "video": {
                    "provider": self.video_gen.provider,
                    "healthy": video_ok
                }
            },
            "current_avatar": {
                "id": self.current_avatar.id if self.current_avatar else None,
                "name": self.current_avatar.name if self.current_avatar else None
            },
            "history_count": len(self.conversation_history)
        }