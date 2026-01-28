import dashscope
from dashscope.aigc.generation import AioGeneration
from typing import AsyncGenerator
import collections
import asyncio

class LLMModule:
    """
    NOVA AI 伴侣 LLM 模块，使用通义千问 qwen-turbo 模型。
    支持流式输出、上下文管理以及表情注入。
    """
    def __init__(self, api_key: str = "sk-b0ce58d3be194be4b5987f747247503b"):
        dashscope.api_key = api_key
        self.model = "qwen-turbo"
        # 简易对话记忆队列，保留最近 10 轮对话 (每轮包含 user 和 assistant)
        # 20 条消息对应 10 轮
        self.history = collections.deque(maxlen=20)
        
        # 系统提示词，定义角色和表情注入规则
        self.system_prompt = (
            "你是一个充满活力的AI伴侣，名字叫NOVA。你的性格活泼、体贴、友好。 "
            "语言规则：你要像镜像一样，根据用户使用的语言来回复。如果用户说中文，你就回复中文；如果用户说英文，你就回复英文。 "
            "在回复用户时，请根据当前语境在适当的位置插入表情代码，格式为 [emo:表情代码]。 "
            "可用的表情代码包括：happy, sad, angry, surprised, wink, blush。 "
            "例如：看到你真开心！[emo:happy] 或者：I'm so glad to see you! [emo:happy]\n"
            "请务必保持回复简洁生动。"
        )

    async def generate_response_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """
        异步生成器，实时返回模型生成的文本片段。
        """
        # 检测用户输入语言，并动态调整系统指令
        import re
        user_lang = "Chinese" if re.search(r"[\u4e00-\u9fa5]", user_input) else "English"
        dynamic_instruction = f"The user is speaking {user_lang}. Respond ONLY in {user_lang}."
        
        # 将用户输入添加到历史记录
        self.history.append({"role": "user", "content": user_input})

        # 构造发送给模型的完整消息列表
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": dynamic_instruction} # 动态插入语言锁定指令
        ] + list(self.history)

        try:
            # 调用 DashScope 异步流式接口
            responses = await AioGeneration.call(
                model=self.model,
                messages=messages,
                result_format='message',
                stream=True,
                incremental_output=True  # 启用增量输出
            )

            full_content = ""
            async for response in responses:
                if response.status_code == 200:
                    # 获取当前增加的文本片段
                    chunk = response.output.choices[0]['message']['content']
                    if chunk:
                        full_content += chunk
                        yield chunk
                else:
                    # 处理 API 错误
                    error_msg = f"\n[API 错误: {response.code} - {response.message}]"
                    print(f"DashScope Error: {response.code} - {response.message}")
                    yield error_msg
                    return # 发生错误时停止生成
            
            # 将助手的完整回复添加到历史记录中
            if full_content:
                self.history.append({"role": "assistant", "content": full_content})

        except Exception as e:
            # 处理网络或其他异常
            error_info = f"\n[系统异常: {str(e)}]"
            print(f"Exception during LLM call: {e}")
            yield error_info

    def clear_history(self):
        """清空对话历史数据"""
        self.history.clear()

if __name__ == "__main__":
    # 简单的本地测试逻辑
    async def test():
        llm = LLMModule()
        print("--- 开始测试 LLM 流式输出 ---")
        async for chunk in llm.generate_response_stream("你好呀，NOVA！你今天心情怎么样？"):
            print(chunk, end="", flush=True)
        print("\n--- 测试完成 ---")

    asyncio.run(test())

