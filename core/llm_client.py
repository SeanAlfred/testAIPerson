# -*- coding: utf-8 -*-
"""大语言模型客户端 - 支持 Ollama 和 OpenAI API"""

import json
from typing import AsyncGenerator, List, Dict, Any, Optional
from loguru import logger
import httpx
import ollama


class LLMClient:
    """大语言模型客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "ollama")

        if self.provider == "ollama":
            self.ollama_config = config.get("ollama", {})
            self._init_ollama()
        elif self.provider == "openai":
            self.openai_config = config.get("openai", {})
            self._init_openai()

        logger.info(f"LLM客户端初始化完成，使用 {self.provider}")

    def _init_ollama(self):
        """初始化Ollama客户端"""
        self.base_url = self.ollama_config.get("base_url", "http://localhost:11434")
        self.model = self.ollama_config.get("model", "qwen2.5:7b")
        self.timeout = self.ollama_config.get("timeout", 60)

        # 设置Ollama客户端
        ollama.Client(host=self.base_url)

    def _init_openai(self):
        """初始化OpenAI客户端"""
        from openai import AsyncOpenAI

        self.api_key = self.openai_config.get("api_key", "")
        self.base_url = self.openai_config.get("base_url", "https://api.openai.com/v1")
        self.model = self.openai_config.get("model", "gpt-4o-mini")

        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            logger.warning("OpenAI API Key未配置")

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

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        if history:
            messages.extend(history)

        # 添加当前输入
        messages.append({"role": "user", "content": prompt})

        try:
            if stream:
                return self._stream_ollama(messages)

            response = ollama.chat(
                model=self.model,
                messages=messages
            )
            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Ollama生成失败: {e}")
            raise

    async def _stream_ollama(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Ollama流式生成"""
        try:
            for chunk in ollama.chat(
                model=self.model,
                messages=messages,
                stream=True
            ):
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

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI生成失败: {e}")
            raise

    async def _stream_openai(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """OpenAI流式生成"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI流式生成失败: {e}")
            raise

    async def check_health(self) -> bool:
        """检查服务是否可用"""
        try:
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