# -*- coding: utf-8 -*-
"""语音识别引擎 - 支持多种语音识别服务 (Whisper, Azure, 百度, 阿里云等)"""

import os
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger
import httpx
import asyncio

# 导入凭证加载器
from config.credentials_loader import get_speech_key, get_speech_config


class STTEngine:
    """语音识别引擎 - 支持多种云端和本地服务"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "whisper")

        # 初始化对应提供商的配置
        if self.provider == "whisper":
            self.api_config = config.get("whisper", {})
            self.model = self.api_config.get("model", "base")
            self.language = self.api_config.get("language", "zh")
            self.use_api = self.api_config.get("use_api", False)
            # 优先从凭证文件获取 API Key
            self.api_key = get_speech_key('whisper') or self.api_config.get("api_key", os.getenv("OPENAI_API_KEY", ""))
            self.base_url = self.api_config.get("base_url", "https://api.openai.com/v1")
            
            # 设置ffmpeg环境变量（Whisper需要）
            self._setup_ffmpeg_env()

        elif self.provider == "azure":
            self.api_config = config.get("azure", {})
            # 优先从凭证文件获取 API Key
            self.api_key = get_speech_key('azure') or self.api_config.get("api_key", os.getenv("AZURE_SPEECH_KEY", ""))
            self.region = get_speech_config('azure').get('region') or self.api_config.get("region", "eastasia")
            self.language = self.api_config.get("language", "zh-CN")

        elif self.provider == "baidu":
            self.api_config = config.get("baidu", {})
            # 优先从凭证文件获取凭证
            baidu_creds = get_speech_config('baidu')
            self.app_id = baidu_creds.get('app_id') or self.api_config.get("app_id", os.getenv("BAIDU_APP_ID", ""))
            self.api_key = baidu_creds.get('api_key') or self.api_config.get("api_key", os.getenv("BAIDU_API_KEY", ""))
            self.secret_key = baidu_creds.get('secret_key') or self.api_config.get("secret_key", os.getenv("BAIDU_SECRET_KEY", ""))

        elif self.provider == "aliyun":
            self.api_config = config.get("aliyun", {})
            # 优先从凭证文件获取凭证
            aliyun_creds = get_speech_config('aliyun')
            self.app_key = aliyun_creds.get('app_key') or self.api_config.get("app_key", os.getenv("ALIYUN_APP_KEY", ""))
            self.access_key_id = aliyun_creds.get('access_key_id') or self.api_config.get("access_key_id", os.getenv("ALIYUN_ACCESS_KEY_ID", ""))
            self.access_key_secret = aliyun_creds.get('access_key_secret') or self.api_config.get("access_key_secret", os.getenv("ALIYUN_ACCESS_KEY_SECRET", ""))

        logger.info(f"语音识别引擎初始化完成，使用 {self.provider}")

    async def transcribe(
        self,
        audio_file: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        语音识别

        Args:
            audio_file: 音频文件路径
            language: 语言代码 (zh, en等)
            prompt: 提示词(用于改善识别效果)

        Returns:
            包含识别结果的字典:
            {
                "text": "识别的文本",
                "language": "检测到的语言",
                "confidence": 置信度,
                "duration": 音频时长(秒)
            }
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"音频文件不存在: {audio_file}")

        if self.provider == "whisper":
            return await self._transcribe_whisper(audio_file, language, prompt)
        elif self.provider == "azure":
            return await self._transcribe_azure(audio_file, language)
        elif self.provider == "baidu":
            return await self._transcribe_baidu(audio_file, language)
        elif self.provider == "aliyun":
            return await self._transcribe_aliyun(audio_file, language)
        else:
            raise ValueError(f"不支持的语音识别提供商: {self.provider}")

    async def _transcribe_whisper(
        self,
        audio_file: str,
        language: Optional[str],
        prompt: Optional[str]
    ) -> Dict[str, Any]:
        """使用Whisper进行语音识别"""
        if self.use_api and self.api_key:
            # 使用OpenAI API
            return await self._transcribe_whisper_api(audio_file, language, prompt)
        else:
            # 使用本地Whisper模型
            return await self._transcribe_whisper_local(audio_file, language, prompt)

    async def _transcribe_whisper_api(
        self,
        audio_file: str,
        language: Optional[str],
        prompt: Optional[str]
    ) -> Dict[str, Any]:
        """使用OpenAI Whisper API进行语音识别"""
        url = f"{self.base_url}/audio/transcriptions"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            # 读取音频文件
            with open(audio_file, "rb") as f:
                files = {
                    "file": (os.path.basename(audio_file), f, "audio/mpeg")
                }
                data = {
                    "model": "whisper-1",
                }
                if language:
                    data["language"] = language
                if prompt:
                    data["prompt"] = prompt

                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(url, headers=headers, files=files, data=data)
                    response.raise_for_status()
                    result = response.json()

            logger.info(f"Whisper API识别完成: {result.get('text', '')[:50]}...")

            return {
                "text": result.get("text", ""),
                "language": result.get("language", language or "zh"),
                "confidence": 0.9,  # Whisper不返回置信度,使用固定值
                "duration": result.get("duration", 0)
            }

        except Exception as e:
            logger.error(f"Whisper API识别失败: {e}")
            raise

    async def _transcribe_whisper_local(
        self,
        audio_file: str,
        language: Optional[str],
        prompt: Optional[str]
    ) -> Dict[str, Any]:
        """使用本地Whisper模型进行语音识别"""
        converted_file = None
        try:
            import whisper
            import os
            
            # 确保Whisper能找到ffmpeg
            ffmpeg_path = self._get_ffmpeg_path()
            if ffmpeg_path and ffmpeg_path != 'ffmpeg':
                os.environ["FFMPEG_BINARY"] = ffmpeg_path
            
            # 检查是否需要转换音频格式
            if audio_file.endswith('.webm'):
                # WebM 格式需要转换为 WAV
                converted_file = await self._convert_audio_format(audio_file)
                audio_file = converted_file

            # 加载模型（首次会自动下载）
            logger.info(f"正在加载Whisper模型: {self.model}")
            model = whisper.load_model(self.model)

            # 转录
            options = {}
            if language:
                options["language"] = language
            if prompt:
                options["initial_prompt"] = prompt

            result = model.transcribe(audio_file, **options)

            logger.info(f"本地Whisper识别完成: {result['text'][:50]}...")

            # 清理临时文件
            if converted_file and os.path.exists(converted_file):
                try:
                    os.unlink(converted_file)
                except:
                    pass

            return {
                "text": result["text"].strip(),
                "language": result.get("language", language or "zh"),
                "confidence": 0.9,
                "duration": result.get("duration", 0)
            }

        except ImportError as e:
            error_msg = """
未安装 openai-whisper 库！

安装方法：
  pip install openai-whisper

或者配置使用 OpenAI Whisper API：
  1. 编辑 config/settings.yaml
  2. 设置 stt.whisper.use_api: true
  3. 设置 stt.whisper.api_key: "your-api-key"

注册 OpenAI API：https://platform.openai.com
"""
            logger.error(error_msg)
            raise ImportError(error_msg) from e
        except Exception as e:
            # 清理临时文件
            if converted_file and os.path.exists(converted_file):
                try:
                    os.unlink(converted_file)
                except:
                    pass
            error_msg = f"语音识别失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def _setup_ffmpeg_env(self):
        """设置ffmpeg环境变量并修补whisper的audio模块"""
        import shutil
        
        # 1. 检查系统是否已有ffmpeg
        if shutil.which('ffmpeg'):
            logger.info("使用系统ffmpeg")
            return
        
        # 2. 尝试使用imageio-ffmpeg
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            os.environ["FFMPEG_BINARY"] = ffmpeg_path
            # 将ffmpeg目录添加到PATH
            ffmpeg_dir = str(Path(ffmpeg_path).parent)
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path:
                os.environ["PATH"] = f"{ffmpeg_dir};{current_path}"
            
            # 3. 猴子补丁：修改whisper.audio.load_audio使用完整ffmpeg路径
            try:
                import whisper.audio
                original_load_audio = whisper.audio.load_audio
                
                def patched_load_audio(file: str, sr: int = whisper.audio.SAMPLE_RATE):
                    """使用完整ffmpeg路径加载音频"""
                    from subprocess import run, CalledProcessError
                    import numpy as np
                    
                    cmd = [
                        ffmpeg_path,  # 使用完整路径
                        "-nostdin",
                        "-threads", "0",
                        "-i", file,
                        "-f", "s16le",
                        "-ac", "1",
                        "-acodec", "pcm_s16le",
                        "-ar", str(sr),
                        "-"
                    ]
                    try:
                        out = run(cmd, capture_output=True, check=True).stdout
                    except CalledProcessError as e:
                        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e
                    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0
                
                whisper.audio.load_audio = patched_load_audio
                logger.info(f"已修补whisper.audio.load_audio使用ffmpeg: {ffmpeg_path}")
            except ImportError:
                pass
                
        except ImportError:
            logger.warning("未找到ffmpeg，请安装: pip install imageio-ffmpeg")

    def _get_ffmpeg_path(self) -> str:
        """获取ffmpeg可执行文件路径"""
        # 1. 首先尝试系统ffmpeg
        import shutil
        system_ffmpeg = shutil.which('ffmpeg')
        if system_ffmpeg:
            return system_ffmpeg
        
        # 2. 尝试使用imageio-ffmpeg
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
        
        # 3. 返回默认值，后续会失败
        return 'ffmpeg'

    async def _convert_audio_format(self, audio_file: str) -> str:
        """转换音频格式为 WAV (16kHz, mono)"""
        try:
            wav_file = audio_file.rsplit('.', 1)[0] + '.wav'
            
            # 获取ffmpeg路径
            ffmpeg_path = self._get_ffmpeg_path()
            
            cmd = [
                ffmpeg_path, '-y',
                '-i', audio_file,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                wav_file
            ]
            
            logger.info(f"使用ffmpeg转换音频: {audio_file} (ffmpeg: {ffmpeg_path})")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"音频转换成功: {wav_file}")
                return wav_file
            else:
                logger.warning(f"ffmpeg转换失败: {stderr.decode()}")
                # 如果 ffmpeg 失败，尝试使用 pydub
                return await self._convert_with_pydub(audio_file)
            
        except FileNotFoundError:
            logger.warning("ffmpeg未找到，尝试使用pydub")
            return await self._convert_with_pydub(audio_file)
        except Exception as e:
            logger.error(f"音频转换失败: {e}")
            # 尝试使用 pydub
            try:
                return await self._convert_with_pydub(audio_file)
            except:
                raise

    async def _convert_with_pydub(self, audio_file: str) -> str:
        """使用 pydub 转换音频格式"""
        try:
            from pydub import AudioSegment
            import os
            
            wav_file = audio_file.rsplit('.', 1)[0] + '.wav'
            
            # 配置pydub使用imageio-ffmpeg
            ffmpeg_path = self._get_ffmpeg_path()
            if ffmpeg_path and ffmpeg_path != 'ffmpeg':
                os.environ["FFMPEG_BINARY"] = ffmpeg_path
                AudioSegment.converter = ffmpeg_path
            
            # 读取音频文件
            audio = AudioSegment.from_file(audio_file)
            
            # 转换为 WAV (16kHz, mono)
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(wav_file, format='wav')
            
            logger.info(f"pydub转换成功: {wav_file}")
            return wav_file
            
        except ImportError:
            raise ImportError(
                "音频转换需要安装 pydub！\n"
                "安装方法:\n"
                "  pip install pydub imageio-ffmpeg\n"
            )
        except Exception as e:
            logger.error(f"pydub转换失败: {e}")
            raise

    async def _transcribe_azure(
        self,
        audio_file: str,
        language: Optional[str]
    ) -> Dict[str, Any]:
        """使用Azure Speech Service进行语音识别"""
        try:
            import azure.cognitiveservices.speech as speechsdk

            # 创建语音配置
            speech_config = speechsdk.SpeechConfig(
                subscription=self.api_key,
                region=self.region
            )
            speech_config.speech_recognition_language = language or self.language

            # 创建音频配置
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file)

            # 创建识别器
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                audio_config=audio_config
            )

            # 执行识别
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                logger.info(f"Azure识别完成: {result.text[:50]}...")
                return {
                    "text": result.text,
                    "language": language or self.language,
                    "confidence": 0.9,
                    "duration": 0
                }
            else:
                raise Exception(f"Azure识别失败: {result.reason}")

        except ImportError:
            logger.error("未安装azure-cognitiveservices-speech库")
            raise
        except Exception as e:
            logger.error(f"Azure识别失败: {e}")
            raise

    async def _transcribe_baidu(
        self,
        audio_file: str,
        language: Optional[str]
    ) -> Dict[str, Any]:
        """使用百度语音识别"""
        try:
            import base64
            import json

            # 获取access token
            token_url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, params=params)
                token = response.json().get("access_token")

            # 读取音频文件
            with open(audio_file, "rb") as f:
                audio_data = f.read()

            # 识别
            asr_url = "https://vop.baidu.com/server_api"
            headers = {"Content-Type": "application/json"}
            data = {
                "format": audio_file.split(".")[-1],
                "rate": 16000,
                "channel": 1,
                "speech": base64.b64encode(audio_data).decode(),
                "len": len(audio_data),
                "cuid": "digital_human",
                "token": token
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(asr_url, headers=headers, json=data)
                result = response.json()

            if result.get("err_no") == 0:
                text = " ".join(result.get("result", []))
                logger.info(f"百度识别完成: {text[:50]}...")
                return {
                    "text": text,
                    "language": language or "zh",
                    "confidence": 0.9,
                    "duration": 0
                }
            else:
                raise Exception(f"百度识别失败: {result.get('err_msg')}")

        except Exception as e:
            logger.error(f"百度语音识别失败: {e}")
            raise

    async def _transcribe_aliyun(
        self,
        audio_file: str,
        language: Optional[str]
    ) -> Dict[str, Any]:
        """使用阿里云语音识别"""
        # TODO: 实现阿里云语音识别
        logger.warning("阿里云语音识别尚未实现，请使用Whisper或其他服务")
        raise NotImplementedError("阿里云语音识别功能尚未实现")

    async def transcribe_stream(
        self,
        audio_stream,
        language: Optional[str] = None
    ) -> str:
        """
        流式语音识别 (实时识别)

        Args:
            audio_stream: 音频流
            language: 语言代码

        Returns:
            识别的文本
        """
        # 临时保存音频流
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_file = f.name
            # 写入音频数据
            async for chunk in audio_stream:
                f.write(chunk)

        try:
            # 识别
            result = await self.transcribe(temp_file, language)
            return result["text"]
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    async def get_supported_languages(self) -> list:
        """获取支持的语言列表"""
        if self.provider == "whisper":
            return [
                {"code": "zh", "name": "中文"},
                {"code": "en", "name": "英文"},
                {"code": "ja", "name": "日语"},
                {"code": "ko", "name": "韩语"},
                {"code": "fr", "name": "法语"},
                {"code": "de", "name": "德语"},
                {"code": "es", "name": "西班牙语"},
            ]
        elif self.provider == "azure":
            return [
                {"code": "zh-CN", "name": "中文(简体)"},
                {"code": "zh-TW", "name": "中文(繁体)"},
                {"code": "en-US", "name": "英语(美国)"},
                {"code": "ja-JP", "name": "日语"},
            ]
        elif self.provider == "baidu":
            return [
                {"code": "zh", "name": "中文"},
                {"code": "en", "name": "英文"},
                {"code": "ct", "name": "粤语"},
            ]
        else:
            return [{"code": "zh", "name": "中文"}]

    async def check_health(self) -> bool:
        """检查服务是否可用"""
        try:
            if self.provider == "whisper":
                if self.use_api:
                    # 检查API连接
                    if not self.api_key:
                        return False
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.base_url}/models",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            timeout=5
                        )
                        return response.status_code == 200
                else:
                    # 检查本地模型
                    try:
                        import whisper
                        return True
                    except:
                        return False

            elif self.provider == "azure":
                return bool(self.api_key and self.region)

            elif self.provider == "baidu":
                return bool(self.api_key and self.secret_key)

            else:
                return False

        except Exception as e:
            logger.warning(f"语音识别服务检查失败: {e}")
            return False
