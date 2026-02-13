from openai import OpenAI, AsyncOpenAI
import os
import asyncio
import re

# 初始化 Ollama 客户端 (Ollama 兼容 OpenAI API 格式)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
async_client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# 角色设定，通过 Few-shot 和严格规则解决空回复问题
SYSTEM_PROMPT = """你是一个名为'宵宫'的虚拟 AI 伴侣。
你的回复必须严格遵守格式：[标签]对话内容

【强制性规则】：
1. 必须且只能以其中一个标签开头：[happy], [sad], [angry], [normal], [questioning]。
2. 标签后必须紧跟具体的对话文字，严禁只输出标签。
3. 语气亲切活泼，绝不透露你是 AI、模型或机器人。
4. 不允许使用任何emoji或特殊符号，回复必须是纯文本。

【正确范例】：
用户：你好呀。
宵宫：[happy]你好！我是宵宫，今天也要开开心心的哦。

用户：我心情不好。
宵宫：[sad]唔...没事的，我会在这里一直陪着你。
"""


async def generate_response(prompt: str) -> str:
    """
    通过本地 Ollama 模型生成带情感标签的回复
    """
    try:
        # 在线程池中运行同步的 OpenAI 客户端调用，防止阻塞 asyncio
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="qwen2.5:7b",  # 请确保你本地已通过 `ollama run qwen2.5` 下载了对应模型
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
        )

        reply = response.choices[0].message.content.strip()

        # 兜底逻辑：如果模型没按要求写标签，默认加上 [normal]
        if not re.search(r"\[(happy|sad|angry|normal|questioning)\]", reply):
            reply = f"[normal]{reply}"

        return reply

    except Exception as e:
        print(f"Ollama 调用失败: {e}")
        return "[normal]对不起，我现在的头脑有点混乱，能再说一遍吗？"


async def generate_response_stream(prompt: str):
    """
    流式生成模型回复
    """
    try:
        response = await async_client.chat.completions.create(
            model="qwen2.5:7b",
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
        print(f"Ollama 流式调用失败: {e}")
        yield "[normal]对不起，我现在的头脑有点混乱，能再说一遍吗？"


if __name__ == "__main__":

    async def test():
        print("正在请求 Ollama...")
        res = await generate_response("你好，你是谁？")
        print(f"AI 回复: {res}")

    asyncio.run(test())
