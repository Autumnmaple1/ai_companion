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
from ai_modules.MEM import MemoryManager
import asyncio
import json
import base64
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks

app = FastAPI()

# 初始化 TTS 引擎
tts_engine = CloudTTS()
tts_engine.initialize_models()

# 依赖注入：MemoryManager
def get_memory_manager():
    return MemoryManager()


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
async def websocket_endpoint(
    websocket: WebSocket, 
    memory: MemoryManager = Depends(get_memory_manager)
):
    await manager.connect(websocket)
    # 为每个连接创建一个 LLM 实例，以维护独立的会话历史
    llm = LLMModule()
    
    try:
        while True:
            message = await manager.receive(websocket)
            message_type = message.get("format")
            content = message.get("content")
            user_id = message.get("user_id") # 获取用户ID，不再使用默认值
            
            print(f"[DEBUG] 解析结果 - format: {message_type}, user_id: {user_id}, content长度: {len(str(content)) if content else 0}")
            
            # 强制要求 user_id，解决 Mem0 v2 API 报错问题
            if not user_id:
                error_message = data_construct(
                    sender="system",
                    type="error",
                    format="text",
                    time=str(time.time()),
                    content="Error: user_id is required. Please select a user.",
                )
                await manager.send(error_message, websocket)
                print(f"[ERROR] 请求缺少 user_id，已拒绝处理")
                continue
            
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

            # --- Step A (阻塞): 检索事实记忆 ---
            print(f"Retrieving context for user: {user_id}")
            facts = memory.get_context(text, user_id=user_id)
            
            # 观测点 1: 检索到了什么？
            print(f"\n[DEBUG] Mem0 检索结果: {facts}")

            full_ai_response = ""
            # --- Step B (流式): 将事实 + 问题丢给 Qwen 并返回 ---
            print(f"Starting LLM stream with facts: {facts[:50]}...")
            
            # 观测点 2: 最终发给 LLM 的 Prompt 长什么样？
            full_prompt = f"System: 你是一个有帮助的AI助手。已知事实: {facts} \nUser: {text}"
            print(f"[DEBUG] 最终 Prompt 长度: {len(full_prompt)}")
            print(f"[DEBUG] 完整 Prompt: {full_prompt}\n")
            
            async for chunk in llm.generate_response_stream(text, context=facts):
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
            
            # --- Step C (后台): 触发 remember 存储本次对话 ---
            # 在 WebSocket 环境中，使用 asyncio.create_task 实现非阻塞后台存储
            # 如果是 HTTP 接口，则可使用 BackgroundTasks
            print(f"Scheduling memory storage for user: {user_id}")
            asyncio.create_task(memory.remember(text, full_ai_response, user_id=user_id))

            # 生成结束，提取表情标签并发送最终状态
            emotion_tag = re.search(r"\[emo:(.*?)\]", full_ai_response)
            emotion = emotion_tag.group(1) if emotion_tag else None
            
            # 发送一个带有表情信息的结束信号（可选，这里复用 message 格式说明回答完毕）
            # 将 facts 也返回给前端方便调试
            final_message = data_construct(
                sender="ai",
                type="message",
                format="text", 
                time=str(time.time()),
                content="", # 内容已经在 chunks 中发完了
                live2d_emotion=emotion,
            )
            # 添加调试信息到消息中
            final_message["memories_used"] = facts
            await manager.send(final_message, websocket)
            
            print(f"[DEBUG] 本轮对话已完成 - 用户: {user_id}, 返回的记忆: {facts}")

            # 语音合成并发送音频 (添加降级处理)
            try:
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
            except Exception as tts_error:
                print(f"Error during TTS generation: {tts_error}")
                print("Degrading: Skipping TTS and continuing with text-only response.")

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
