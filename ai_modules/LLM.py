from openai import OpenAI, AsyncOpenAI
import httpx
import json
import os
import asyncio
import re
from backend.config import settings

# 动态加载角色配置
char_config = settings.get_character_config()
SYSTEM_PROMPT = char_config["llm"]["system_prompt"]
LLM_CONF = char_config["llm"]
LETTA_AGENT_ID = char_config.get("letta_agent_id")

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
    通过 Letta 或 DashScope 生成带情感标签的回复 (一次性生成全文)
    """
    # 优先尝试使用 Letta (带长期记忆)
    if settings.LETTA_URL and LETTA_AGENT_ID:
        try:
            async with httpx.AsyncClient(timeout=30.0) as httpx_client:
                # 请求 Letta 消息接口
                url = f"{settings.LETTA_URL.rstrip('/')}/v1/agents/{LETTA_AGENT_ID}/messages"
                # Letta v1 API 期望的消息字段是 "content" 而不是 "text"
                payload = {"messages": [{"role": "user", "content": prompt}]}

                resp = await httpx_client.post(url, json=payload, follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json()
                    # 兼容不同版本的 Letta 返回格式
                    messages = (
                        data if isinstance(data, list) else data.get("messages", [])
                    )

                    assistant_text = ""
                    for m in messages:
                        # 找到助手回复的消息块
                        if m.get("message_type") == "assistant_message":
                            # 优先尝试从 "text" 或 "content" 中获取内容
                            assistant_text = m.get("text") or m.get("content") or ""

                    if assistant_text:
                        # 兜底逻辑：如果模型没按要求写标签，默认加上 [normal]
                        if not re.search(
                            r"\[(happy|sad|angry|normal|questioning)\]", assistant_text
                        ):
                            assistant_text = f"[normal]{assistant_text}"
                        return assistant_text.strip()
                else:
                    print(f"Letta API Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Letta 调用失败: {e}，将回退至普通 LLM...")

    try:
        # 在线程池中运行同步的 OpenAI 客户端调用
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=LLM_CONF.get("temperature", 0.7),
            max_tokens=LLM_CONF.get("max_tokens", 1500),
            stream=False,  # 确保是一次性返回
        )

        reply = response.choices[0].message.content.strip()

        # 兜底逻辑：如果模型没按要求写标签，默认加上 [normal]
        if not re.search(r"\[(happy|sad|angry|normal|questioning)\]", reply):
            reply = f"[normal]{reply}"

        return reply

    except Exception as e:
        print(f"LLM 调用失败: {e}")
        return "[normal]对不起，我现在的头脑有点混乱，能再说一遍吗？"


# 如果之前有 generate_response_stream，可以保留定义但不再主动推荐使用
async def generate_response_stream(prompt: str):
    """
    (已弃用) 为了向后兼容保留，内部直接调用一次性生成
    """
    res = await generate_response(prompt)
    yield res


if __name__ == "__main__":

    async def test():
        print("正在请求 LLM...")
        res = await generate_response("你好，你是谁？")
        print(f"AI 回复: {res}")

    asyncio.run(test())
