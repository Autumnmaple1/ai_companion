import sys
import os
import time
import re
from dotenv import load_dotenv

# 加载 .env 文件
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_modules
from ai_modules import LLMModule, CloudTTS
import asyncio
import json
import base64
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# 初始化 TTS 引擎
tts_engine = CloudTTS()
tts_engine.initialize_models()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def receive(self, websocket: WebSocket) -> dict:
        data = await websocket.receive_text()
        return json.loads(data)

    async def send(self, content: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(content))


def data_construct(
    sender: str, type: str, format: str, time: str, content, live2d_emotion=None
) -> dict:
    if isinstance(content, bytes):
        content = base64.b64encode(content).decode("utf-8")
    if live2d_emotion is not None:
        return {
            "sender": sender,
            "type": type,
            "format": format,
            "time": time,
            "content": content,
            "live2d_emotion": live2d_emotion,
        }
    return {
        "sender": sender,
        "type": type,
        "format": format,
        "time": time,
        "content": content,
    }


manager = ConnectionManager()


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # 为每个连接创建一个 LLM 实例，以维护独立的会话历史
    llm = LLMModule()
    
    try:
        while True:
            message = await manager.receive(websocket)
            message_type = message.get("format")
            content = message.get("content")
            text = ""
            
            if message_type == "text":
                text = content
            elif message_type == "audio":
                audio_data = content
                # 假设 ASR 接收 base64 或 字节流，这里根据 LLM 的改动保持 ASR 接口一致性
                text = await ai_modules.speech_to_text(audio_data)
                print(f"Recognized text: {text}")
                user_message = data_construct(
                    sender="user",
                    type="message",
                    format="text",
                    time=str(time.time()),
                    content=text,
                )
                await manager.send(user_message, websocket)
            
            if not text:
                continue

            full_ai_response = ""
            # 开始流式生成回复
            async for chunk in llm.generate_response_stream(text):
                full_ai_response += chunk
                
                # 实时发送文本片段给前端
                chunk_message = data_construct(
                    sender="ai",
                    type="message",
                    format="text_chunk", # 使用 text_chunk 标识这是增量内容
                    time=str(time.time()),
                    content=chunk,
                )
                await manager.send(chunk_message, websocket)
            
            # 生成结束，提取表情标签并发送最终状态
            emotion_tag = re.search(r"\[emo:(.*?)\]", full_ai_response)
            emotion = emotion_tag.group(1) if emotion_tag else None
            
            # 发送一个带有表情信息的结束信号（可选，这里复用 message 格式说明回答完毕）
            final_message = data_construct(
                sender="ai",
                type="message",
                format="text", 
                time=str(time.time()),
                content="", # 内容已经在 chunks 中发完了
                live2d_emotion=emotion,
            )
            await manager.send(final_message, websocket)

            # 语音合成并发送音频
            # 强化语言判断：优先检查中文字符，若无则视为英文
            has_chinese = re.search(r"[\u4e00-\u9fa5]", full_ai_response)
            tts_lang = "zh" if has_chinese else "en"
            
            print(f"TTS Language detected: {tts_lang} for text: {full_ai_response[:20]}...")
            tts_audio = await tts_engine.text_to_speech(full_ai_response, lang=tts_lang)
            ai_audio_message = data_construct(
                sender="ai",
                type="voice",
                format="audio",
                time=str(time.time()),
                content=tts_audio,
            )
            await manager.send(ai_audio_message, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("client disconnected")
    except Exception as e:
        print(f"Error in websocket loop: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "server:app", 
        host="localhost", 
        port=8000, 
        reload=True,
        reload_excludes=[".conda"]
    )
