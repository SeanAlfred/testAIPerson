# -*- coding: utf-8 -*-
"""视频生成器 - 支持SadTalker、Wav2Lip和云端API"""

import os
import uuid
import asyncio
import subprocess
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx
from loguru import logger
from PIL import Image
import shutil


class VideoGenerator:
    """视频生成器 - 语音驱动的数字人视频"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "sadtalker")
        self._ffmpeg_path = None

        # 初始化配置
        if self.provider == "sadtalker":
            self.sadtalker_config = config.get("sadtalker", {})
            self.sadtalker_path = self.sadtalker_config.get("path", "")
            self.api_url = self.sadtalker_config.get("api_url", "")
        elif self.provider == "d-id":
            self.d_id_config = config.get("d_id", {})
            self.api_key = self.d_id_config.get("api_key", os.getenv("D_ID_API_KEY", ""))
        elif self.provider == "heygen":
            self.heygen_config = config.get("heygen", {})
            self.api_key = self.heygen_config.get("api_key", os.getenv("HEYGEN_API_KEY", ""))

        # 输出目录
        self.output_dir = Path("outputs/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置ffmpeg
        self._setup_ffmpeg()

        logger.info(f"视频生成器初始化完成，使用 {self.provider}")

    def _get_ffmpeg_path(self) -> str:
        """获取ffmpeg可执行文件路径"""
        if self._ffmpeg_path:
            return self._ffmpeg_path
            
        # 1. 首先尝试系统ffmpeg
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            self._ffmpeg_path = system_ffmpeg
            return system_ffmpeg
        
        # 2. 尝试使用imageio-ffmpeg
        try:
            import imageio_ffmpeg
            self._ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            return self._ffmpeg_path
        except ImportError:
            pass
        
        # 3. 返回默认值
        return 'ffmpeg'

    def _setup_ffmpeg(self):
        """设置ffmpeg环境变量"""
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path and ffmpeg_path != 'ffmpeg':
            os.environ["FFMPEG_BINARY"] = ffmpeg_path
            ffmpeg_dir = str(Path(ffmpeg_path).parent)
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path:
                os.environ["PATH"] = f"{ffmpeg_dir};{current_path}"
            logger.info(f"视频生成器已配置ffmpeg: {ffmpeg_path}")

    async def generate(
        self,
        image_path: str,
        audio_path: str,
        output_file: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        根据图片和音频生成视频

        Args:
            image_path: 数字人图片路径
            audio_path: 音频文件路径
            output_file: 输出视频路径
            **kwargs: 其他参数

        Returns:
            生成的视频文件路径
        """
        if self.provider == "sadtalker":
            return await self._generate_sadtalker(image_path, audio_path, output_file, **kwargs)
        elif self.provider == "d-id":
            return await self._generate_d_id(image_path, audio_path, output_file, **kwargs)
        elif self.provider == "heygen":
            return await self._generate_heygen(image_path, audio_path, output_file, **kwargs)
        else:
            # 使用简单合成作为备选
            return await self._generate_simple(image_path, audio_path, output_file)

    async def _generate_sadtalker(
        self,
        image_path: str,
        audio_path: str,
        output_file: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用SadTalker生成视频"""
        if not output_file:
            output_file = str(self.output_dir / f"{uuid.uuid4().hex}.mp4")

        # 如果配置了API URL，使用API调用
        if self.api_url:
            return await self._generate_sadtalker_api(image_path, audio_path, output_file)

        # 否则尝试本地调用
        return await self._generate_sadtalker_local(image_path, audio_path, output_file, **kwargs)

    async def _generate_sadtalker_api(
        self,
        image_path: str,
        audio_path: str,
        output_file: str
    ) -> str:
        """通过API调用SadTalker服务"""
        url = f"{self.api_url}/generate"

        try:
            # 读取文件
            with open(image_path, "rb") as f:
                image_data = f.read()
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            # 构建multipart请求
            files = {
                "image": ("image.png", image_data, "image/png"),
                "audio": ("audio.mp3", audio_data, "audio/mpeg")
            }

            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, files=files)
                response.raise_for_status()

                # 保存视频
                with open(output_file, "wb") as f:
                    f.write(response.content)

                logger.info(f"SadTalker API生成视频: {output_file}")
                return output_file

        except Exception as e:
            logger.error(f"SadTalker API调用失败: {e}")
            raise

    async def _generate_sadtalker_local(
        self,
        image_path: str,
        audio_path: str,
        output_file: str,
        preprocess: str = "crop",
        enhancer: str = "gfpgan"
    ) -> str:
        """本地调用SadTalker"""
        if not self.sadtalker_path:
            logger.warning("SadTalker路径未配置，使用简单合成")
            return await self._generate_simple(image_path, audio_path, output_file)

        try:
            # 构建命令
            cmd = [
                "python", f"{self.sadtalker_path}/inference.py",
                "--driven_audio", audio_path,
                "--source_image", image_path,
                "--result_dir", str(self.output_dir),
                "--preprocess", preprocess,
                "--enhancer", enhancer
            ]

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"SadTalker执行失败: {stderr.decode()}")
                raise Exception(f"SadTalker执行失败: {stderr.decode()}")

            # 查找生成的视频
            for f in self.output_dir.glob("*.mp4"):
                if f.stat().st_mtime > asyncio.get_event_loop().time() - 60:
                    # 重命名为目标文件
                    if str(f) != output_file:
                        shutil.move(str(f), output_file)
                    return output_file

            raise Exception("未找到生成的视频文件")

        except Exception as e:
            logger.error(f"SadTalker本地调用失败: {e}")
            raise

    async def _generate_d_id(
        self,
        image_path: str,
        audio_path: str,
        output_file: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用D-ID API生成视频"""
        if not self.api_key:
            logger.warning("D-ID API Key未配置，使用简单合成")
            return await self._generate_simple(image_path, audio_path, output_file)

        if not output_file:
            output_file = str(self.output_dir / f"{uuid.uuid4().hex}.mp4")

        url = "https://api.d-id.com/talks"

        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            # 上传图片
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_base64 = image_data.encode("base64").decode()

            # 上传音频
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            audio_base64 = audio_data.encode("base64").decode()

            # 创建talk
            payload = {
                "source_url": f"data:image/png;base64,{image_base64}",
                "driver_url": "bank://lively",
                "script": {
                    "type": "audio",
                    "audio_url": f"data:audio/mp3;base64,{audio_base64}"
                }
            }

            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                talk = response.json()

                # 轮询等待结果
                talk_id = talk["id"]
                while True:
                    result = await client.get(f"{url}/{talk_id}", headers=headers)
                    result.raise_for_status()
                    status = result.json()

                    if status["status"] == "done":
                        # 下载视频
                        video_url = status["result_url"]
                        video_response = await client.get(video_url)
                        with open(output_file, "wb") as f:
                            f.write(video_response.content)
                        return output_file
                    elif status["status"] == "error":
                        raise Exception(f"D-ID生成失败: {status.get('error')}")

                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"D-ID视频生成失败: {e}")
            raise

    async def _generate_heygen(
        self,
        image_path: str,
        audio_path: str,
        output_file: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用HeyGen API生成视频"""
        if not self.api_key:
            logger.warning("HeyGen API Key未配置，使用简单合成")
            return await self._generate_simple(image_path, audio_path, output_file)

        # HeyGen API实现
        # 类似D-ID的实现
        raise NotImplementedError("HeyGen API集成待实现")

    async def _generate_simple(
        self,
        image_path: str,
        audio_path: str,
        output_file: Optional[str] = None
    ) -> str:
        """
        简单视频合成 - 将静态图片和音频合成为视频
        当没有专业视频生成服务时使用
        """
        if not output_file:
            output_file = str(self.output_dir / f"{uuid.uuid4().hex}.mp4")

        try:
            # 使用ffmpeg合成
            # 视频时长由音频决定
            ffmpeg_path = self._get_ffmpeg_path()
            cmd = [
                ffmpeg_path, "-y",
                "-loop", "1",
                "-i", image_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                output_file
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg合成失败: {stderr.decode()}")
                raise Exception(f"视频合成失败: {stderr.decode()}")

            logger.info(f"简单视频合成完成: {output_file}")
            return output_file

        except FileNotFoundError:
            error_msg = """
FFmpeg 未安装！

安装方法：
  pip install imageio-ffmpeg  (推荐，自动安装)
  或
  Windows: winget install ffmpeg
  Linux: sudo apt install ffmpeg
  macOS: brew install ffmpeg
"""
            logger.warning(error_msg)
            return await self._create_mock_video(image_path, audio_path, output_file)
        except Exception as e:
            logger.error(f"视频合成失败: {e}")
            raise

    async def _create_mock_video(
        self,
        image_path: str,
        audio_path: str,
        output_file: str
    ) -> str:
        """创建模拟视频文件（当没有ffmpeg时）"""
        # 复制图片作为模拟输出
        mock_file = output_file.replace(".mp4", ".png")
        shutil.copy(image_path, mock_file)

        logger.warning(f"创建了模拟视频文件: {mock_file}")
        logger.warning("要生成真正的视频，请安装 FFmpeg 或配置 D-ID/HeyGen API")
        return mock_file

    async def generate_with_text(
        self,
        image_path: str,
        text: str,
        tts_engine,
        output_file: Optional[str] = None
    ) -> str:
        """
        一站式生成：文本 -> 语音 -> 视频

        Args:
            image_path: 数字人图片路径
            text: 要说的文本
            tts_engine: TTS引擎实例
            output_file: 输出视频路径

        Returns:
            生成的视频文件路径
        """
        from .tts_engine import TTSEngine

        # 1. 生成语音
        audio_file = await tts_engine.synthesize(text)
        logger.info(f"语音生成完成: {audio_file}")

        # 2. 生成视频
        video_file = await self.generate(image_path, audio_file, output_file)
        logger.info(f"视频生成完成: {video_file}")

        # 3. 清理临时音频文件
        try:
            os.remove(audio_file)
        except:
            pass

        return video_file

    async def check_health(self) -> bool:
        """检查服务是否可用"""
        try:
            if self.provider == "sadtalker" and self.api_url:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.api_url}/health", timeout=5)
                    return response.status_code == 200
            elif self.provider == "d-id":
                if self.api_key:
                    logger.info("D-ID API Key 已配置")
                    return True
                else:
                    logger.warning("D-ID API Key 未配置")
                    return False
            elif self.provider == "heygen":
                if self.api_key:
                    logger.info("HeyGen API Key 已配置")
                    return True
                else:
                    logger.warning("HeyGen API Key 未配置")
                    return False

            # 检查ffmpeg (使用imageio-ffmpeg或系统ffmpeg)
            ffmpeg_path = self._get_ffmpeg_path()
            process = await asyncio.create_subprocess_exec(
                ffmpeg_path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if process.returncode == 0:
                logger.info(f"FFmpeg 可用 ({ffmpeg_path})，视频生成功能正常")
                return True
            else:
                logger.warning("FFmpeg 检查失败")
                return False
        except FileNotFoundError:
            logger.warning("FFmpeg 未安装，视频生成将使用模拟模式")
            logger.warning("安装方法: pip install imageio-ffmpeg 或 winget install ffmpeg (Windows)")
            return False
        except Exception as e:
            logger.warning(f"视频生成服务检查失败: {e}")
            return False