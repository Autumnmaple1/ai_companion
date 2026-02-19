from openai import OpenAI, AsyncOpenAI
import os
import asyncio
import re
from backend.config import settings

# 动态加载角色配置
char_config = settings.get_character_config()
SYSTEM_PROMPT = char_config["llm"]["system_prompt"]
LLM_CONF = char_config["llm"]

# 初始化 DashScope 客户端 (兼容 OpenAI API 格式)
client = OpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
)
async_client = AsyncOpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
)


async def generate_response(prompt: str) -> str:
    """
    通过 DashScope LLM 模型生成带情感标签的回复
    """
    try:
        # 在线程池中运行同步的 OpenAI 客户端调用，防止阻塞 asyncio
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_CONF.get("temperature", 0.7),
            max_tokens=LLM_CONF.get("max_tokens", 1500),
        )

        reply = response.choices[0].message.content.strip()

        # 兜底逻辑：如果模型没按要求写标签，默认加上 [normal]
        if not re.search(r"\[(happy|sad|angry|normal|questioning)\]", reply):
            reply = f"[normal]{reply}"

        return reply

    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return "[normal]对不起，我现在的头脑有点混乱，能再说一遍吗？"


async def generate_response_stream(prompt: str):
    """
    流式生成模型回复
    """
    try:
        response = await async_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        print(f"LLM 流式调用失败: {e}")
        yield "[normal]对不起，我现在的头脑有点混乱，能再说一遍吗？"


if __name__ == "__main__":

    async def test():
        print("正在请求 LLM...")
        res = await generate_response("你好，你是谁？")
        print(f"AI 回复: {res}")

    asyncio.run(test())
