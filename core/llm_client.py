# -*- coding: utf-8 -*-
"""
大语言模型客户端 - 支持 Ollama、OpenAI API 和 ZeroToken模式

ZeroToken模式: 直接调用各平台Web客户端，无需API Token
"""

import json
from typing import AsyncGenerator, List, Dict, Any, Optional
from loguru import logger
import httpx
import ollama

# 导入凭证加载器
from config.credentials_loader import get_llm_key, get_llm_base_url, get_llm_config


# 平台配置
PLATFORM_CONFIGS = {
    'deepseek': {
        'name': 'DeepSeek',
        'models': ['deepseek-chat', 'deepseek-reasoner'],
        'login_url': 'https://chat.deepseek.com',
    },
    'doubao': {
        'name': 'Doubao',
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


class LLMClient:
    """大语言模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "ollama")
        self.call_mode = config.get("call_mode", "ollamaAPI")  # ollamaAPI, zeroToken, deepseekAPI

        if self.provider == "ollama":
            self.ollama_config = config.get("ollama", {})
            self._init_ollama()
        elif self.provider == "openai":
            self.openai_config = config.get("openai", {})
            self._init_openai()
        
        # DeepSeek API 配置
        if self.call_mode == "deepseekAPI":
            self.deepseek_config = config.get("deepseek", {})
            self._init_deepseek()
        
        # ZeroToken 配置
        self.zero_token_platform = config.get("zero_token_platform", "deepseek")
        self.zero_token_model = config.get("zero_token_model", None)
        self.credentials_path = config.get("credentials_path", "config/credentials")
        
        # 初始化 ZeroToken 客户端
        self._zero_token_client = None
        
        if self.call_mode == "zeroToken":
            self._init_zero_token()
            logger.info(f"ZeroToken模式已启用，平台: {self.zero_token_platform}")

        logger.info(f"LLM客户端初始化完成，使用 {self.provider}, 调用模式: {self.call_mode}")

    def _init_ollama(self):
        """初始化Ollama客户端"""
        # 优先从凭证文件获取 Base URL
        self.base_url = get_llm_base_url('ollama') or self.ollama_config.get("base_url", "http://localhost:11434")
        self.model = self.ollama_config.get("model", "qwen2.5:7b")
        self.timeout = self.ollama_config.get("timeout", 60)
        self.ollama_client = ollama.Client(host=self.base_url)
        logger.info(f"Ollama客户端已连接: {self.base_url}, 模型: {self.model}")

    def _init_openai(self):
        """初始化OpenAI客户端"""
        from openai import AsyncOpenAI
        # 优先从凭证文件获取 API Key 和 Base URL
        self.api_key = get_llm_key('openai') or self.openai_config.get("api_key", "")
        self.base_url = get_llm_base_url('openai') or self.openai_config.get("base_url", "https://api.openai.com/v1")
        self.model = self.openai_config.get("model", "gpt-4o-mini")

        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            logger.warning("OpenAI API Key未配置")

    def _init_deepseek(self):
        """初始化DeepSeek API客户端"""
        from openai import AsyncOpenAI
        # 优先从凭证文件获取 API Key 和 Base URL
        self.deepseek_api_key = get_llm_key('deepseek') or self.deepseek_config.get("api_key", "")
        self.deepseek_base_url = get_llm_base_url('deepseek') or self.deepseek_config.get("base_url", "https://api.deepseek.com/v1")
        self.deepseek_model = self.deepseek_config.get("model", "deepseek-chat")

        if self.deepseek_api_key:
            self.deepseek_client = AsyncOpenAI(
                api_key=self.deepseek_api_key, 
                base_url=self.deepseek_base_url
            )
            logger.info(f"DeepSeek API客户端已初始化，模型: {self.deepseek_model}")
        else:
            logger.warning("DeepSeek API Key未配置")

    def _init_zero_token(self):
        """初始化ZeroToken客户端"""
        try:
            from pathlib import Path
            from .zero_token_base import CredentialManager, WebCredentials
            
            self._credential_manager = CredentialManager(Path(self.credentials_path))
            credentials = self._credential_manager.load_credentials(self.zero_token_platform)
            
            if credentials:
                self._zero_token_client = self._create_platform_client(credentials)
                logger.info(f"ZeroToken客户端已初始化: {self.zero_token_platform}")
            else:
                logger.warning(f"未找到 {self.zero_token_platform} 的凭证，请先登录")
        except Exception as e:
            logger.error(f"ZeroToken客户端初始化失败: {e}")

    def _create_platform_client(self, credentials):
        """创建平台客户端"""
        platform = self.zero_token_platform.lower()
        
        if platform == 'deepseek':
            from .deepseek_web import DeepSeekWebClient
            return DeepSeekWebClient(credentials)
        elif platform == 'doubao':
            from .doubao_web import DoubaoWebClient
            return DoubaoWebClient(credentials)
        else:
            raise ValueError(f"不支持的平台: {platform}")

    def _get_model_name(self) -> str:
        """获取模型名称"""
        if self.zero_token_model:
            return self.zero_token_model
        
        platform = self.zero_token_platform.lower()
        if platform in PLATFORM_CONFIGS:
            models = PLATFORM_CONFIGS[platform].get('models', [])
            if models:
                return models[0]
        
        return f"{platform}-default"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """
        生成回复

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            history: 对话历史
            stream: 是否流式输出

        Returns:
            生成的回复文本
        """
        # DeepSeek API 模式
        if self.call_mode == "deepseekAPI":
            return await self._generate_deepseek(prompt, system_prompt, history, stream)
        
        # ZeroToken模式
        if self.call_mode == "zeroToken":
            return await self._generate_zero_token(prompt, system_prompt, history, stream)
        
        # 传统API模式
        if self.provider == "ollama":
            return await self._generate_ollama(prompt, system_prompt, history, stream)
        elif self.provider == "openai":
            return await self._generate_openai(prompt, system_prompt, history, stream)
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """使用Ollama生成回复"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            if stream:
                return self._stream_ollama(messages)

            response = self.ollama_client.chat(model=self.model, messages=messages)
            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Ollama生成失败: {e}")
            raise

    async def _stream_ollama(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Ollama流式生成"""
        try:
            for chunk in self.ollama_client.chat(model=self.model, messages=messages, stream=True):
                if chunk["message"]["content"]:
                    yield chunk["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama流式生成失败: {e}")
            raise

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """使用OpenAI API生成回复"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            if stream:
                return self._stream_openai(messages)

            response = await self.client.chat.completions.create(model=self.model, messages=messages)
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI生成失败: {e}")
            raise

    async def _stream_openai(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """OpenAI流式生成"""
        try:
            stream = await self.client.chat.completions.create(model=self.model, messages=messages, stream=True)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI流式生成失败: {e}")
            raise

    async def _generate_deepseek(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """使用DeepSeek API生成回复"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            if stream:
                return self._stream_deepseek(messages)

            response = await self.deepseek_client.chat.completions.create(
                model=self.deepseek_model, 
                messages=messages
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"DeepSeek API生成失败: {e}")
            raise

    async def _stream_deepseek(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """DeepSeek流式生成"""
        try:
            stream = await self.deepseek_client.chat.completions.create(
                model=self.deepseek_model, 
                messages=messages, 
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"DeepSeek流式生成失败: {e}")
            raise

    async def _generate_zero_token(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        stream: bool = False
    ) -> str:
        """使用ZeroToken模式生成回复"""
        # 检查客户端是否可用
        if not self._zero_token_client:
            raise Exception(f"ZeroToken客户端未初始化，请先配置 {self.zero_token_platform} 的凭证")
        
        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        if stream:
            return self._stream_zero_token(messages)
        
        # 非流式模式
        full_response = ""
        async for chunk in self._stream_zero_token(messages):
            full_response += chunk
        
        return full_response

    async def _stream_zero_token(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """ZeroToken流式生成"""
        model = self._get_model_name()
        logger.info(f"ZeroToken调用: platform={self.zero_token_platform}, model={model}")
        
        if self._zero_token_client is None:
            raise Exception("ZeroToken客户端未初始化，请检查凭证配置")
        
        try:
            from .zero_token_base import StreamEvent
            
            async for event in self._zero_token_client.chat_completions(
                messages=messages,
                model=model,
                stream=True
            ):
                # 防御性检查：跳过 None 事件
                if event is None:
                    logger.warning("[ZeroToken] Received None event, skipping")
                    continue
                
                # 检查事件类型
                if isinstance(event, StreamEvent):
                    event_type = getattr(event, 'type', None)
                    event_delta = getattr(event, 'delta', None)
                    event_error = getattr(event, 'error', None)
                    
                    if event_type in ('content', 'thinking') and event_delta:
                        yield event_delta
                    elif event_type == 'error':
                        raise Exception(event_error or 'Unknown error from StreamEvent')
                        
                elif isinstance(event, dict):
                    # 兼容旧格式
                    event_type = event.get('type')
                    event_delta = event.get('delta')
                    event_error = event.get('error')
                    
                    if event_type in ('content', 'thinking') and event_delta:
                        yield event_delta
                    elif event_type == 'error':
                        raise Exception(event_error or 'Unknown error from dict')
                else:
                    logger.warning(f"[ZeroToken] Unknown event type: {type(event)}")
                    continue
                    
        except Exception as e:
            logger.error(f"ZeroToken流式生成失败: {e}")
            raise
        finally:
            # 关闭客户端连接
            if hasattr(self._zero_token_client, 'close'):
                try:
                    await self._zero_token_client.close()
                except Exception as e:
                    logger.warning(f"[ZeroToken] Failed to close client: {e}")

    async def check_health(self) -> bool:
        """检查服务是否可用"""
        try:
            if self.call_mode == "deepseekAPI":
                return bool(self.deepseek_api_key)
            
            if self.call_mode == "zeroToken":
                # 检查凭证是否有效
                if self._zero_token_client:
                    if hasattr(self._zero_token_client, 'check_session'):
                        return await self._zero_token_client.check_session()
                return False
            
            if self.provider == "ollama":
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.base_url}/api/tags", timeout=5)
                    return response.status_code == 200
            elif self.provider == "openai":
                return bool(self.api_key)
            return False
        except Exception as e:
            logger.warning(f"LLM服务检查失败: {e}")
            return False

    async def list_models(self) -> List[str]:
        """列出可用模型"""
        try:
            if self.call_mode == "deepseekAPI":
                return ["deepseek-chat", "deepseek-reasoner"]
            
            if self.call_mode == "zeroToken":
                platform = self.zero_token_platform.lower()
                if platform in PLATFORM_CONFIGS:
                    return PLATFORM_CONFIGS[platform].get('models', [])
                return []
            
            if self.provider == "ollama":
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.base_url}/api/tags", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        return [model["name"] for model in data.get("models", [])]
            elif self.provider == "openai":
                return ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            return []
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    async def check_credentials(self) -> bool:
        """检查ZeroToken凭证是否有效"""
        if self.call_mode != "zeroToken":
            return True
        
        credentials = self._credential_manager.load_credentials(self.zero_token_platform)
        return credentials is not None

    async def set_credentials(self, credentials_str: str):
        """设置ZeroToken凭证"""
        from .zero_token_base import WebCredentials
        
        try:
            credentials = WebCredentials.from_json(credentials_str)
            self._credential_manager.save_credentials(self.zero_token_platform, credentials)
            self._zero_token_client = self._create_platform_client(credentials)
            logger.info(f"凭证已保存并激活: {self.zero_token_platform}")
        except Exception as e:
            logger.error(f"设置凭证失败: {e}")
            raise

    def get_login_url(self) -> str:
        """获取登录URL"""
        platform = self.zero_token_platform.lower()
        if platform in PLATFORM_CONFIGS:
            return PLATFORM_CONFIGS[platform].get('login_url', '')
        return ''
