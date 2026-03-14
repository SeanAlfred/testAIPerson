# -*- coding: utf-8 -*-
"""网络搜索模块 - 支持实时联网获取信息"""

import re
import json
import asyncio
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus, urlparse
from loguru import logger
import httpx
from bs4 import BeautifulSoup


class WebSearchEngine:
    """网络搜索引擎 - 支持多种搜索方式"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_results = self.config.get("max_results", 5)
        self.timeout = self.config.get("timeout", 10)
        self.user_agent = self.config.get("user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # 搜索引擎配置
        self.search_provider = self.config.get("provider", "baidu")

        # 内容提取配置
        self.max_content_length = self.config.get("max_content_length", 4000)

        # 域名白名单（优先抓取的网站）
        self.trusted_domains = self.config.get("trusted_domains", [
            "wikipedia.org",
            "baike.baidu.com",
            "zhihu.com",
            "news.qq.com",
            "news.sina.com.cn",
            "cctv.com",
            "gov.cn",
            "github.com",
            "stackoverflow.com",
            "medium.com"
        ])

        logger.info(f"网络搜索模块初始化完成，使用 {self.search_provider}")

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        extract_content: bool = True
    ) -> Dict[str, Any]:
        """
        执行网络搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            extract_content: 是否提取网页内容

        Returns:
            包含搜索结果的字典
        """
        if not self.enabled:
            return {"success": False, "error": "搜索功能未启用", "results": []}

        max_results = max_results or self.max_results

        try:
            results = []

            # 根据配置选择搜索方式
            if self.search_provider == "duckduckgo":
                results = await self._search_duckduckgo(query, max_results)
            elif self.search_provider == "baidu":
                results = await self._search_baidu(query, max_results)
            elif self.search_provider == "bing":
                results = await self._search_bing(query, max_results)
            elif self.search_provider == "google":
                results = await self._search_google(query, max_results)
            else:
                results = await self._search_baidu(query, max_results)  # 默认使用百度

            # 如果主搜索无结果，尝试百度作为备选（百度在国内可用）
            if not results and self.search_provider != "baidu":
                logger.info("主搜索无结果，尝试百度搜索...")
                results = await self._search_baidu(query, max_results)

            # 最后尝试 DuckDuckGo（无需翻墙）
            if not results and self.search_provider != "duckduckgo":
                logger.info("百度搜索也无结果，尝试DuckDuckGo...")
                results = await self._search_duckduckgo(query, max_results)

            # 提取网页内容
            if extract_content and results:
                results = await self._extract_contents(results)

            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {"success": False, "error": str(e), "results": []}

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, str]]:
        """使用DuckDuckGo搜索（无需API Key）"""
        results = []

        # 尝试多种URL格式
        urls = [
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            f"https://duckduckgo.com/html/?q={quote_plus(query)}",
        ]

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }

        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                    response = await client.get(url, headers=headers, follow_redirects=True)
                    response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # 尝试多种选择器
                selectors = [
                    (".result", ".result__a", ".result__snippet"),
                    (".web-result", ".result__a", ".result__snippet"),
                    ("div[class*='result']", "a[class*='result']", None),
                ]

                for container_sel, title_sel, snippet_sel in selectors:
                    for result in soup.select(container_sel)[:max_results]:
                        title_elem = result.select_one(title_sel)
                        if not title_elem:
                            continue

                        href = title_elem.get("href", "")
                        # 提取真实URL
                        if "uddg=" in href:
                            import urllib.parse
                            href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])

                        snippet = ""
                        if snippet_sel:
                            snippet_elem = result.select_one(snippet_sel)
                            if snippet_elem:
                                snippet = snippet_elem.get_text(strip=True)

                        title = title_elem.get_text(strip=True)
                        if title and href:
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": snippet
                            })

                    if results:
                        break

                if results:
                    break

            except Exception as e:
                logger.warning(f"DuckDuckGo搜索尝试失败: {e}")
                continue

        if results:
            logger.info(f"DuckDuckGo搜索完成: {len(results)}条结果")
        else:
            # 使用百度搜索作为备选
            results = await self._search_baidu(query, max_results)

        return results[:max_results]

    async def _search_baidu(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, str]]:
        """使用百度搜索（国内可用）"""
        results = []
        url = f"https://www.baidu.com/s?wd={quote_plus(query)}"

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 百度搜索结果选择器
            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one("h3 a, .t a")
                snippet_elem = result.select_one(".c-abstract, .c-span9, .c-color-text")

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")

                    # 尝试获取真实URL
                    if href.startswith("/link?url="):
                        href = f"https://www.baidu.com{href}"

                    snippet = ""
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)

                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })

            if results:
                logger.info(f"百度搜索完成: {len(results)}条结果")

        except Exception as e:
            logger.warning(f"百度搜索失败: {e}")

        return results

    async def _search_wikipedia(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, str]]:
        """搜索维基百科"""
        # 先尝试中文维基
        results = []

        for lang in ["zh", "en"]:
            try:
                # 搜索API
                search_url = f"https://{lang}.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": max_results
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(search_url, params=params)
                    response.raise_for_status()
                    data = response.json()

                for item in data.get("query", {}).get("search", []):
                    title = item.get("title", "")
                    page_id = item.get("pageid", 0)
                    snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")

                    results.append({
                        "title": f"[Wikipedia] {title}",
                        "url": f"https://{lang}.wikipedia.org/wiki/{quote_plus(title)}",
                        "snippet": snippet
                    })

                if results:
                    break

            except Exception as e:
                logger.warning(f"Wikipedia搜索失败 ({lang}): {e}")
                continue

        return results[:max_results]

    async def _search_bing(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, str]]:
        """使用Bing搜索API（需要API Key）"""
        api_key = self.config.get("bing_api_key", "")
        if not api_key:
            logger.warning("Bing API Key未配置，回退到百度搜索")
            return await self._search_baidu(query, max_results)

        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {"q": query, "count": max_results, "mkt": "zh-CN"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", "")
                })

            return results

        except Exception as e:
            logger.error(f"Bing搜索失败: {e}")
            return await self._search_duckduckgo(query, max_results)

    async def _search_google(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, str]]:
        """使用Google Custom Search API（需要API Key和搜索引擎ID）"""
        api_key = self.config.get("google_api_key", "")
        search_engine_id = self.config.get("google_cx", "")

        if not api_key or not search_engine_id:
            logger.warning("Google API配置不完整，回退到百度搜索")
            return await self._search_baidu(query, max_results)

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "num": max_results
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })

            return results

        except Exception as e:
            logger.error(f"Google搜索失败: {e}")
            return await self._search_duckduckgo(query, max_results)

    async def _extract_contents(
        self,
        results: List[Dict[str, str]],
        max_concurrent: int = 3
    ) -> List[Dict[str, str]]:
        """并发提取网页内容"""
        enriched_results = []

        async def extract_single(result: Dict[str, str]) -> Dict[str, str]:
            url = result.get("url", "")
            if not url:
                return result

            content = await self._fetch_page_content(url)
            result["content"] = content
            return result

        # 并发提取，但限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_extract(result):
            async with semaphore:
                return await extract_single(result)

        tasks = [limited_extract(r) for r in results]
        enriched_results = await asyncio.gather(*tasks)

        return enriched_results

    async def _fetch_page_content(self, url: str) -> str:
        """抓取网页内容"""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

                # 检测编码
                content_type = response.headers.get("content-type", "")
                if "charset=" in content_type:
                    encoding = content_type.split("charset=")[1].split(";")[0].strip()
                    if encoding.lower() in ["gb2312", "gbk"]:
                        response.encoding = "gbk"
                    elif encoding.lower() == "utf-8":
                        response.encoding = "utf-8"

                text = response.text

            # 解析并提取主要内容
            soup = BeautifulSoup(text, "html.parser")

            # 移除脚本和样式
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # 尝试提取主要内容区域
            main_content = None
            for selector in ["article", "main", ".content", "#content", ".article", ".post"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            # 限制长度
            if len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "..."

            return text

        except Exception as e:
            logger.warning(f"抓取网页内容失败 {url}: {e}")
            return ""

    async def get_weather(self, city: str) -> Dict[str, Any]:
        """获取天气信息 - 使用免费天气API"""
        try:
            # 使用 wttr.in 免费天气 API（支持中文城市名）
            url = f"https://wttr.in/{quote_plus(city)}?format=j1&lang=zh"
            headers = {"User-Agent": "curl/7.68.0"}  # wttr.in 需要类似 curl 的 UA

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            current = data.get("current_condition", [{}])[0]
            weather_desc = current.get("lang_zh", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "未知"))
            temp = current.get("temp_C", "N/A")
            humidity = current.get("humidity", "N/A")
            wind = current.get("windspeedKmph", "N/A")
            feels_like = current.get("FeelsLikeC", "N/A")

            weather_info = f"""{city}当前天气：
天气状况：{weather_desc}
当前温度：{temp}°C
体感温度：{feels_like}°C
湿度：{humidity}%
风速：{wind} 公里/小时"""

            return {
                "success": True,
                "city": city,
                "data": weather_info,
                "raw": {
                    "temp": temp,
                    "humidity": humidity,
                    "description": weather_desc,
                    "wind": wind,
                    "feels_like": feels_like
                }
            }
        except Exception as e:
            logger.warning(f"天气API查询失败: {e}，尝试搜索引擎...")
            # 回退到搜索引擎
            query = f"{city} 天气"
            result = await self.search(query, max_results=1, extract_content=True)

            if result["success"] and result["results"]:
                return {
                    "success": True,
                    "city": city,
                    "data": result["results"][0].get("content", result["results"][0].get("snippet", ""))
                }
            return {"success": False, "error": f"获取天气失败: {str(e)}"}

    async def get_news(self, topic: str = "", max_results: int = 5) -> Dict[str, Any]:
        """获取新闻"""
        query = f"{topic} 最新新闻" if topic else "今日新闻"
        result = await self.search(query, max_results=max_results, extract_content=False)

        return result

    async def get_knowledge(self, question: str) -> Dict[str, Any]:
        """获取知识点"""
        # 尝试从维基百科或百度百科获取
        wiki_query = f"{question} wiki"
        result = await self.search(wiki_query, max_results=3, extract_content=True)

        if result["success"] and result["results"]:
            # 合并多个来源的信息
            contents = []
            for r in result["results"]:
                if r.get("content"):
                    contents.append(f"【{r['title']}】\n{r['content'][:1000]}")

            return {
                "success": True,
                "question": question,
                "answers": contents
            }

        return {"success": False, "error": "未找到相关信息"}

    async def check_health(self) -> bool:
        """检查搜索服务是否可用"""
        try:
            result = await self.search("test", max_results=1, extract_content=False)
            return result["success"]
        except Exception as e:
            logger.warning(f"搜索服务检查失败: {e}")
            return False


# 创建总结函数（供LLM调用）
def format_search_results(search_result: Dict[str, Any], max_length: int = 2000) -> str:
    """格式化搜索结果为文本摘要"""
    if not search_result.get("success"):
        return f"搜索失败: {search_result.get('error', '未知错误')}"

    results = search_result.get("results", [])
    if not results:
        return "未找到相关结果。"

    summary_parts = [f"搜索关键词: {search_result.get('query', '')}\n"]

    for i, result in enumerate(results[:5], 1):
        summary_parts.append(f"\n{i}. {result.get('title', '无标题')}")
        summary_parts.append(f"   来源: {result.get('url', '')}")

        if result.get("content"):
            content = result["content"][:500]
            summary_parts.append(f"   内容摘要: {content}...")
        elif result.get("snippet"):
            summary_parts.append(f"   摘要: {result['snippet']}")

    summary = "\n".join(summary_parts)

    if len(summary) > max_length:
        summary = summary[:max_length] + "..."

    return summary