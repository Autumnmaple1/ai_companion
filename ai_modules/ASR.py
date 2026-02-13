import json
import os
import asyncio
import base64


async def speech_to_text(audio_data):
    """
    将人声音频数据转换为文本字符串

    audio_data: 输入的人声音频数据
    """
    data = audio_data
    if isinstance(audio_data, str):
        data = base64.b64decode(audio_data)
    return "Hello, this is a test."
