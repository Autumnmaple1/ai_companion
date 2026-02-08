import os
import asyncio
from typing import List, Dict, Any
from mem0 import MemoryClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class MemoryManager:
    def __init__(self):
        """初始化 MemoryManager：链接 Mem0 托管端"""
        api_key = os.getenv("MEM_API_KEY")
        if not api_key:
            raise ValueError("MEM_API_KEY not found in environment variables")
        self.client = MemoryClient(api_key=api_key)

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        """内部方法：将原始 JSON 结果清洗为纯文本事实清单"""
        facts = []
        for res in results:
            # Mem0 搜索结果通常在 'memory' 或 'content' 字段中
            content = res.get("memory") or res.get("content") or ""
            if content:
                facts.append(f"- {content}")
        return "\n".join(facts) if facts else "无相关背景记忆。"

    def get_context(self, user_query: str, user_id: str, threshold: float = 0.5) -> str:
        try:
            # 1. 明确构造符合 v2 要求的 filter
            # 注意：这里的结构是 v2 托管端强制要求的
            memory_filters = {"user_id": user_id} 

            # 2. 调用时使用关键字参数显式传递
            results = self.client.search(
                query=user_query, 
                filters=memory_filters
            )
            
            # 3. 结果处理逻辑保持不变...
            filtered_results = [
                res for res in results 
                if res.get("score", 1.0) >= threshold or res.get("similarity", 1.0) >= threshold
            ]
            
            return self._format_results(filtered_results)
        except Exception as e:
            # 这里的 e 会包含更详细的 API 错误信息
            print(f"Detailed Error: {e}")
            return ""
    async def remember(self, user_query: str, assistant_answer: str, user_id: str):
        """
        异步存储记忆（对话对存储）。
        准备配合 FastAPI 的后台任务使用。
        """
        try:
            # 构造对话对以提高存储记忆的精准度
            messages = [
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": assistant_answer}
            ]
            
            # 由于 Mem0 SDK 通常是同步的，使用 asyncio.to_thread 避免阻塞事件循环
            await asyncio.to_thread(self.client.add, messages, user_id=user_id)
        except Exception as e:
            print(f"Error storing memory: {e}")
