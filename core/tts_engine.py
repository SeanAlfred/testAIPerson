# -*- coding: utf-8 -*-
"""语音合成引擎 - 支持 Edge-TTS"""

import asyncio
import os
from typing import Dict, Any, Optional
from pathlib import Path
import edge_tts
from loguru import logger
import aiofiles


class TTSEngine:
    """语音合成引擎"""

    # Edge-TTS 可用声音列表
    EDGE_VOICES = {
        # 中文声音
        "zh-CN-XiaoxiaoNeural": "晓晓 (女声，自然亲切)",
        "zh-CN-YunxiNeural": "云希 (男声，阳光活力)",
        "zh-CN-YunyangNeural": "云扬 (男声，新闻播音)",
        "zh-CN-XiaoyiNeural": "晓伊 (女声，温柔甜美)",
        "zh-CN-YunjianNeural": "云健 (男声，沉稳大气)",
        "zh-CN-XiaochenNeural": "晓辰 (女声，知性优雅)",
        "zh-CN-XiaohanNeural": "晓涵 (女声，活泼可爱)",
        "zh-CN-XiaomengNeural": "晓梦 (女声，梦幻温柔)",
        "zh-CN-XiaomoNeural": "晓墨 (女声，文艺清新)",
        "zh-CN-XiaoruiNeural": "晓睿 (女声，邻家女孩)",
        "zh-CN-XiaoshuangNeural": "晓双 (女声，儿童音)",
        "zh-CN-XiaoxuanNeural": "晓萱 (女声，青春活力)",
        "zh-CN-XiaoyanNeural": "晓彦 (女声，温柔知性)",
        "zh-CN-XiaoyouNeural": "晓悠 (女声，可爱活泼)",
        "zh-CN-YunfengNeural": "云枫 (男声，成熟稳重)",
        "zh-CN-YunhaoNeural": "云皓 (男声，广告配音)",
        "zh-CN-YunxiaNeural": "云夏 (男声，年轻活力)",
        "zh-CN-YunyeNeural": "云野 (男声，轻松自然)",
        # 英文声音
        "en-US-JennyNeural": "Jenny (US Female)",
        "en-US-GuyNeural": "Guy (US Male)",
        "en-GB-SoniaNeural": "Sonia (UK Female)",
        "en-GB-RyanNeural": "Ryan (UK Male)",
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "edge-tts")

        if self.provider == "edge-tts":
            self.edge_config = config.get("edge_tts", {})
            self.voice = self.edge_config.get("voice", "zh-CN-XiaoxiaoNeural")
            self.rate = self.edge_config.get("rate", "+0%")
            self.volume = self.edge_config.get("volume", "+0%")

        # 输出目录
        self.output_dir = Path("outputs/audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"TTS引擎初始化完成，使用 {self.provider}，声音: {self.voice}")

    async def synthesize(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> str:
        """
        合成语音

        Args:
            text: 要合成的文本
            output_file: 输出文件路径，默认自动生成
            voice: 使用的声音
            rate: 语速 (-50% 到 +100%)
            volume: 音量 (-50% 到 +100%)

        Returns:
            生成的音频文件路径
        """
        if self.provider == "edge-tts":
            return await self._synthesize_edge(text, output_file, voice, rate, volume)
        else:
            raise ValueError(f"不支持的TTS提供商: {self.provider}")

    async def _synthesize_edge(
        self,
        text: str,
        output_file: Optional[str] = None,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None
    ) -> str:
        """使用Edge-TTS合成语音"""
        # 使用传入参数或默认配置
        use_voice = voice or self.voice
        use_rate = rate or self.rate
        use_volume = volume or self.volume

        # 生成输出文件路径
        if output_file is None:
            import uuid
            output_file = self.output_dir / f"{uuid.uuid4().hex}.mp3"
        else:
            output_file = Path(output_file)

        # 确保目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 创建Edge-TTS通信实例
            communicate = edge_tts.Communicate(
                text=text,
                voice=use_voice,
                rate=use_rate,
                volume=use_volume
            )

            # 合成并保存
            await communicate.save(str(output_file))

            logger.info(f"语音合成完成: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            raise

    async def synthesize_stream(self, text: str) -> bytes:
        """
        流式合成语音，返回音频数据

        Args:
            text: 要合成的文本

        Returns:
            音频数据字节
        """
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume
        )

        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    async def get_voices(self, language: Optional[str] = None) -> Dict[str, str]:
        """
        获取可用的声音列表

        Args:
            language: 语言代码过滤，如 "zh-CN", "en-US"

        Returns:
            声音名称到描述的映射
        """
        try:
            voices = await edge_tts.list_voices()

            result = {}
            for voice in voices:
                name = voice["ShortName"]
                if language is None or name.startswith(language):
                    result[name] = voice.get("FriendlyName", name)

            return result
        except Exception as e:
            logger.warning(f"获取声音列表失败: {e}")
            return self.EDGE_VOICES

    async def text_to_speech_with_ssml(
        self,
        ssml: str,
        output_file: Optional[str] = None
    ) -> str:
        """
        使用SSML合成语音（支持更丰富的控制）

        Args:
            ssml: SSML格式的文本
            output_file: 输出文件路径

        Returns:
            生成的音频文件路径
        """
        # Edge-TTS 不直接支持SSML，需要提取文本
        # 这里简化处理，直接使用文本
        import re
        text = re.sub(r'<[^>]+>', '', ssml)
        return await self.synthesize(text, output_file)

    def estimate_duration(self, text: str) -> float:
        """
        估算语音时长（秒）

        Args:
            text: 文本内容

        Returns:
            估算的时长（秒）
        """
        # 中文约每分钟200-250字，英文约每分钟150词
        # 这里使用一个简化的估算
        char_count = len(text)

        # 根据语速调整
        rate_factor = 1.0
        if self.rate:
            if self.rate.startswith("+"):
                rate_factor = 1 - int(self.rate[1:-1]) / 100
            elif self.rate.startswith("-"):
                rate_factor = 1 + int(self.rate[1:-1]) / 100

        # 假设每秒约4个中文字符
        duration = (char_count / 4) * rate_factor

        return max(duration, 0.5)  # 最小0.5秒