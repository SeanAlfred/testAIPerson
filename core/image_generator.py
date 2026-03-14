# -*- coding: utf-8 -*-
"""图像生成器 - 支持云端API (SiliconFlow, Replicate, Stability AI)"""

import os
import base64
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx
from loguru import logger
from PIL import Image
import io

# 导入凭证加载器
from config.credentials_loader import get_image_key, get_image_base_url, get_image_config


class ImageGenerator:
    """图像生成器 - 支持多种云端API"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "siliconflow")

        # 初始化对应提供商的配置
        if self.provider == "siliconflow":
            self.api_config = config.get("siliconflow", {})
            # 优先从凭证文件获取 API Key 和 Base URL
            self.api_key = get_image_key('siliconflow') or self.api_config.get("api_key", os.getenv("SILICONFLOW_API_KEY", ""))
            self.base_url = get_image_base_url('siliconflow') or "https://api.siliconflow.cn/v1"
        elif self.provider == "replicate":
            self.api_config = config.get("replicate", {})
            # 优先从凭证文件获取 API Key 和 Base URL
            self.api_key = get_image_key('replicate') or self.api_config.get("api_key", os.getenv("REPLICATE_API_KEY", ""))
            self.base_url = get_image_base_url('replicate') or "https://api.replicate.com/v1"
        elif self.provider == "stability":
            self.api_config = config.get("stability", {})
            # 优先从凭证文件获取 API Key 和 Base URL
            self.api_key = get_image_key('stability') or self.api_config.get("api_key", os.getenv("STABILITY_API_KEY", ""))
            self.base_url = get_image_base_url('stability') or "https://api.stability.ai/v1"

        # 输出目录
        self.output_dir = Path("outputs/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 默认参数
        self.model = self.api_config.get("model", "stabilityai/stable-diffusion-xl-base-1.0")
        self.negative_prompt = self.api_config.get("negative_prompt", "")

        logger.info(f"图像生成器初始化完成，使用 {self.provider}")

    async def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        seed: Optional[int] = None,
        output_file: Optional[str] = None
    ) -> List[str]:
        """
        生成图像

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图像宽度
            height: 图像高度
            num_images: 生成数量
            seed: 随机种子
            output_file: 输出文件路径

        Returns:
            生成的图像文件路径列表
        """
        if not self.api_key:
            # 使用占位图像
            logger.warning("API Key未配置，生成占位图像")
            return await self._generate_placeholder(prompt, output_file)

        if self.provider == "siliconflow":
            return await self._generate_siliconflow(
                prompt, negative_prompt, width, height, num_images, seed, output_file
            )
        elif self.provider == "replicate":
            return await self._generate_replicate(
                prompt, negative_prompt, width, height, num_images, seed, output_file
            )
        elif self.provider == "stability":
            return await self._generate_stability(
                prompt, negative_prompt, width, height, num_images, seed, output_file
            )
        else:
            raise ValueError(f"不支持的图像生成提供商: {self.provider}")

    async def _generate_siliconflow(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        num_images: int,
        seed: Optional[int],
        output_file: Optional[str]
    ) -> List[str]:
        """使用SiliconFlow API生成图像"""
        url = f"{self.base_url}/images/generations"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "negative_prompt": negative_prompt or self.negative_prompt,
            "size": f"{width}x{height}",  # 使用 size 而非 image_size
            "n": num_images,  # 使用 n 而非 num_images
        }
        if seed:
            payload["seed"] = seed

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                logger.info(f"SiliconFlow请求: model={self.model}, prompt={prompt[:50]}...")
                response = await client.post(url, json=payload, headers=headers)
                
                # 记录响应状态
                logger.info(f"SiliconFlow响应: status={response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"SiliconFlow API错误 [{response.status_code}]: {error_text}")
                    raise Exception(f"API返回错误 {response.status_code}: {error_text[:500]}")
                
                data = response.json()
                logger.debug(f"响应数据keys: {list(data.keys())}")

            # 保存图像
            saved_paths = []
            images = data.get("images", [])
            logger.info(f"收到 {len(images)} 张图像")
            for i, img_data in enumerate(images):
                if output_file and i == 0:
                    file_path = Path(output_file)
                else:
                    file_path = self.output_dir / f"{uuid.uuid4().hex}.png"

                # 处理不同格式的图像数据
                img_bytes = None
                
                if isinstance(img_data, dict):
                    # 字典格式，提取URL或base64
                    if "url" in img_data:
                        img_url = img_data["url"]
                        async with httpx.AsyncClient() as client:
                            img_response = await client.get(img_url)
                            img_bytes = img_response.content
                    elif "b64_json" in img_data:
                        img_bytes = base64.b64decode(img_data["b64_json"])
                elif isinstance(img_data, str):
                    if img_data.startswith("http"):
                        # URL格式，下载图像
                        async with httpx.AsyncClient() as client:
                            img_response = await client.get(img_data)
                            img_bytes = img_response.content
                    elif img_data.startswith("data:"):
                        # Base64格式
                        img_bytes = base64.b64decode(img_data.split(",")[1])
                    else:
                        # 纯Base64
                        img_bytes = base64.b64decode(img_data)

                if img_bytes:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
                    saved_paths.append(str(file_path))

            logger.info(f"图像生成完成: {saved_paths}")
            return saved_paths

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if hasattr(e, 'response') else str(e)
            logger.error(f"SiliconFlow HTTP错误: {error_detail}")
            raise Exception(f"SiliconFlow API HTTP错误: {error_detail[:500]}")
        except httpx.TimeoutException:
            logger.error("SiliconFlow请求超时")
            raise Exception("SiliconFlow API请求超时")
        except httpx.RequestError as e:
            logger.error(f"SiliconFlow网络错误: {e}")
            raise Exception(f"网络请求失败: {e}")
        except Exception as e:
            logger.error(f"图像生成失败: {type(e).__name__}: {e}")
            raise

    async def _generate_replicate(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        num_images: int,
        seed: Optional[int],
        output_file: Optional[str]
    ) -> List[str]:
        """使用Replicate API生成图像"""
        model = self.api_config.get(
            "model",
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
        )

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        # 创建预测
        create_url = f"{self.base_url}/predictions"
        payload = {
            "version": model.split(":")[-1] if ":" in model else model,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt or self.negative_prompt,
                "width": width,
                "height": height,
                "num_outputs": num_images,
            }
        }
        if seed:
            payload["input"]["seed"] = seed

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # 创建预测
                response = await client.post(create_url, json=payload, headers=headers)
                response.raise_for_status()
                prediction = response.json()

                # 轮询等待结果
                get_url = prediction["urls"]["get"]
                while True:
                    result = await client.get(get_url, headers=headers)
                    result.raise_for_status()
                    status = result.json()

                    if status["status"] == "succeeded":
                        break
                    elif status["status"] == "failed":
                        raise Exception(f"Replicate预测失败: {status.get('error')}")

                    await asyncio.sleep(1)

                # 下载并保存图像
                saved_paths = []
                for i, img_url in enumerate(status.get("output", [])):
                    if output_file and i == 0:
                        file_path = Path(output_file)
                    else:
                        file_path = self.output_dir / f"{uuid.uuid4().hex}.png"

                    img_response = await client.get(img_url)
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(img_response.content)

                    saved_paths.append(str(file_path))

                return saved_paths

        except Exception as e:
            logger.error(f"Replicate图像生成失败: {e}")
            raise

    async def _generate_stability(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        num_images: int,
        seed: Optional[int],
        output_file: Optional[str]
    ) -> List[str]:
        """使用Stability AI API生成图像"""
        url = f"{self.base_url}/generation/{self.model.split('/')[-1]}/text-to-image"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
            ],
            "cfg_scale": 7,
            "height": height,
            "width": width,
            "samples": num_images,
            "steps": 30,
        }
        if negative_prompt:
            payload["text_prompts"].append({"text": negative_prompt, "weight": -1.0})
        if seed:
            payload["seed"] = seed

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            # 保存图像
            saved_paths = []
            for i, artifact in enumerate(data.get("artifacts", [])):
                if output_file and i == 0:
                    file_path = Path(output_file)
                else:
                    file_path = self.output_dir / f"{uuid.uuid4().hex}.png"

                img_bytes = base64.b64decode(artifact["base64"])
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(img_bytes)

                saved_paths.append(str(file_path))

            return saved_paths

        except Exception as e:
            logger.error(f"Stability AI图像生成失败: {e}")
            raise

    async def _generate_placeholder(
        self,
        prompt: str,
        output_file: Optional[str]
    ) -> List[str]:
        """生成占位图像（当API Key未配置时）"""
        if output_file:
            file_path = Path(output_file)
        else:
            file_path = self.output_dir / f"{uuid.uuid4().hex}.png"

        # 创建一个简单的占位图像
        img = Image.new("RGB", (512, 512), color=(100, 150, 200))

        # 添加文本
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)

        # 使用默认字体
        text = f"数字人形象\n(配置API Key后生成真实图像)"
        draw.text((256, 256), text, fill="white", anchor="mm")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(file_path)

        logger.info(f"生成占位图像: {file_path}")
        return [str(file_path)]

    async def generate_avatar(
        self,
        description: str = "专业的AI数字人助手，微笑，正面视角，高质量肖像",
        style: str = "professional",
        gender: str = "female",
        age: str = "young",
        expression: str = "smile",
        pose: str = "front",
        background: str = "clean",
        output_file: Optional[str] = None
    ) -> str:
        """
        生成数字人头像

        Args:
            description: 人物描述
            style: 风格 (professional, casual, anime, realistic, cartoon, artistic)
            gender: 性别 (male, female)
            age: 年龄 (young, middle, senior)
            expression: 表情 (smile, serious, friendly, confident, neutral)
            pose: 姿势 (front, slight_angle, profile)
            background: 背景 (clean, office, outdoor, abstract)
            output_file: 输出文件路径

        Returns:
            生成的图像文件路径
        """
        # 构建风格提示词
        style_prompts = {
            "professional": "professional business portrait, studio lighting, clean background, corporate style",
            "casual": "casual portrait, natural lighting, friendly expression, lifestyle photography",
            "anime": "anime style, manga art, vibrant colors, cute character design, detailed anime illustration",
            "realistic": "photorealistic, ultra realistic, 8k photography, professional portrait photo",
            "cartoon": "cartoon style, digital art, colorful, friendly character design, modern illustration",
            "artistic": "artistic portrait, painterly style, beautiful lighting, creative composition"
        }

        # 性别特征
        gender_prompts = {
            "male": "professional man, masculine features, well-groomed",
            "female": "professional woman, feminine features, elegant"
        }

        # 年龄特征
        age_prompts = {
            "young": "young adult, fresh face, energetic",
            "middle": "middle-aged, mature, experienced",
            "senior": "senior, wise, distinguished"
        }

        # 表情特征
        expression_prompts = {
            "smile": "warm smile, friendly expression, happy",
            "serious": "serious expression, focused, professional",
            "friendly": "friendly expression, approachable, kind",
            "confident": "confident expression, self-assured, strong",
            "neutral": "neutral expression, calm, composed"
        }

        # 姿势特征
        pose_prompts = {
            "front": "facing camera directly, symmetrical composition, straight pose",
            "slight_angle": "slight angle pose, three-quarter view, dynamic composition",
            "profile": "profile view, side angle, artistic composition"
        }

        # 背景特征
        background_prompts = {
            "clean": "clean solid background, minimalist, simple backdrop",
            "office": "modern office background, professional environment",
            "outdoor": "outdoor background, natural environment, bokeh effect",
            "abstract": "abstract background, artistic, colorful gradients"
        }

        # 组合提示词
        prompt = f"""
        {description},
        {gender_prompts.get(gender, '')},
        {age_prompts.get(age, '')},
        {expression_prompts.get(expression, '')},
        {pose_prompts.get(pose, '')},
        {background_prompts.get(background, '')},
        {style_prompts.get(style, '')},
        portrait, head and shoulders, high quality, sharp focus, detailed skin texture,
        perfect face, symmetrical features, beautiful eyes
        """.replace("\n", " ").strip()

        negative = f"""
        low quality, blurry, distorted, ugly, bad anatomy, bad hands,
        text, watermark, signature, multiple people, full body,
        cropped head, bad proportions, deformed face, crossed eyes,
        {self.negative_prompt}
        """.replace("\n", " ").strip()

        results = await self.generate(
            prompt=prompt,
            negative_prompt=negative,
            width=1024,
            height=1024,
            output_file=output_file
        )

        return results[0] if results else ""

    async def generate_avatar_with_expression(
        self,
        base_avatar_path: str,
        expression: str = "smile",
        intensity: float = 0.5,
        output_file: Optional[str] = None
    ) -> str:
        """
        基于现有形象生成不同表情

        Args:
            base_avatar_path: 基础形象路径
            expression: 表情 (smile, happy, sad, angry, surprised, neutral)
            intensity: 表情强度 (0.0-1.0)
            output_file: 输出文件路径

        Returns:
            生成的图像文件路径
        """
        if not os.path.exists(base_avatar_path):
            raise FileNotFoundError(f"基础形象不存在: {base_avatar_path}")

        # 表情描述映射
        expression_descriptions = {
            "smile": "warm gentle smile, happy expression, eyes slightly squinted",
            "happy": "big smile, joyful expression, bright eyes, happy",
            "sad": "sad expression, downcast eyes, melancholic, sorrowful",
            "angry": "angry expression, furrowed brows, intense gaze",
            "surprised": "surprised expression, wide eyes, raised eyebrows",
            "neutral": "neutral expression, calm, composed, relaxed"
        }

        # 读取基础形象
        with open(base_avatar_path, "rb") as f:
            # 这里可以添加图像编辑逻辑
            # 目前使用提示词重新生成
            pass

        # 使用提示词生成带表情的形象
        description = f"portrait with {expression_descriptions.get(expression, 'neutral expression')}, "
        description += f"expression intensity {intensity:.1%}"

        return await self.generate_avatar(
            description=description,
            output_file=output_file
        )

    async def generate_avatar_variations(
        self,
        description: str,
        style: str = "professional",
        gender: str = "female",
        num_variations: int = 4
    ) -> list:
        """
        生成多个形象变体供选择

        Args:
            description: 人物描述
            style: 风格
            gender: 性别
            num_variations: 变体数量

        Returns:
            生成的图像文件路径列表
        """
        # 生成多个不同表情和角度的变体
        variations = []
        expressions = ["smile", "friendly", "confident", "neutral"]
        poses = ["front", "slight_angle", "front", "slight_angle"]

        for i in range(min(num_variations, 4)):
            avatar_path = await self.generate_avatar(
                description=description,
                style=style,
                gender=gender,
                expression=expressions[i % len(expressions)],
                pose=poses[i % len(poses)]
            )
            variations.append(avatar_path)

        return variations

    async def check_health(self) -> bool:
        """检查API是否可用"""
        if not self.api_key:
            return False

        try:
            # 发送一个简单请求测试API
            if self.provider == "siliconflow":
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        timeout=5
                    )
                    return response.status_code == 200
            return True
        except Exception as e:
            logger.warning(f"图像生成API检查失败: {e}")
            return False


# 导入asyncio（Replicate需要）
import asyncio