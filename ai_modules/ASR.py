import json
import os
import asyncio
import base64


async def speech_to_text(audio_data):
    """
    将人声音频数据转换为文本字符串
    (当前为模拟版本)
    提示：如果需要测试中英自动切换，请在前端输入框直接输入文本测试。
    """
    # 默认返回中文，以便触发中文回复逻辑
    return "你好，NOVA。" 
