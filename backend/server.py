import sys
import os
import time
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_modules
import asyncio
import json
import base64
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


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
    sender: str,
    type: str,
    format: str,
    time: str,
    content,
    live2d_emotion=None,
    id=None,
    mode=None,
    index=None,
) -> dict:
    if isinstance(content, bytes):
        content = base64.b64encode(content).decode("utf-8")
    res = {
        "sender": sender,
        "type": type,
        "format": format,
        "time": time,
        "content": content,
    }
    if live2d_emotion is not None:
        res["live2d_emotion"] = live2d_emotion
    if id is not None:
        res["id"] = id
    if mode is not None:
        res["mode"] = mode
    if index is not None:
        res["index"] = index
    return res


manager = ConnectionManager()


# 并发限制信号量（根据显存调整，建议 2-3 以兼顾速度和稳定性）
TTS_SEMAPHORE = asyncio.Semaphore(1)


async def tts_and_send(text, emotion, index, websocket):
    """合成并立即通过 WebSocket 发送音频，带编号并受信号量限制"""
    async with TTS_SEMAPHORE:
        try:
            tts_audio = await ai_modules.TTS.text_to_speech(text, emotion)
            if tts_audio:
                ai_audio_message = data_construct(
                    sender="ai",
                    type="voice",
                    format="audio",
                    time=str(time.time()),
                    content=tts_audio,
                    index=index,
                )
                await manager.send(ai_audio_message, websocket)
        except Exception as e:
            print(f"TTS 并发合成或发送异常 (index {index}): {e}")


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # ... (ASR and user message handling) ...
            message = await manager.receive(websocket)
            message_type = message.get("format")
            content = message.get("content")
            text = ""
            if message_type == "text":
                text = content
            elif message_type == "audio":
                audio_data = content
                text = await ai_modules.ASR.speech_to_text(audio_data)
                print(f"Recognized text: {text}")
                user_message = data_construct(
                    sender="user",
                    type="message",
                    format="text",
                    time=str(time.time()),
                    content=text,
                )
                await manager.send(user_message, websocket)

            if not text or not text.strip():
                continue

            try:
                # ─── 流式处理逻辑 ───
                response_id = int(time.time() * 1000)
                full_response = ""
                sentence_buffer = ""
                emotion_ref = [None]  # 使用 list 以便在 worker 中共享引用
                emotion_found = False
                sentence_index = 0
                tts_tasks = []

                try:
                    # 句子结束标志
                    terminators = ("。", "！", "？", "!", "?", "\n")

                    async for chunk in ai_modules.LLM.generate_response_stream(text):
                        full_response += chunk
                        sentence_buffer += chunk

                        # 1. 提取情感
                        if not emotion_found and "]" in full_response:
                            emotion_tag = re.search(r"\[(.*?)\]", full_response)
                            if emotion_tag:
                                emotion_ref[0] = emotion_tag.group(1)
                                emotion_found = True
                                sentence_buffer = re.sub(
                                    r"\[.*?\]", "", sentence_buffer
                                )

                        # 2. 检查是否有完整的句子
                        if any(t in chunk for t in terminators):
                            clean_text = re.sub(r"\[.*?\]", "", sentence_buffer).strip()

                            if clean_text:
                                # 发送文本消息
                                ai_message = data_construct(
                                    sender="ai",
                                    type="message",
                                    format="text",
                                    time=str(time.time()),
                                    content=clean_text + " ",
                                    live2d_emotion=emotion_ref[0],
                                    id=response_id,
                                    mode="append",
                                )
                                await manager.send(ai_message, websocket)

                                # 并行：立即创建 TTS 异步任务并直接发送 (带 index)
                                current_emo = emotion_ref[0] or "normal"
                                task = asyncio.create_task(
                                    tts_and_send(
                                        clean_text,
                                        current_emo,
                                        sentence_index,
                                        websocket,
                                    )
                                )
                                tts_tasks.append(task)
                                sentence_index += 1

                                sentence_buffer = ""

                    # 3. 处理最后剩余的部分
                    if sentence_buffer.strip():
                        clean_text = re.sub(r"\[.*?\]", "", sentence_buffer).strip()
                        if clean_text:
                            ai_message = data_construct(
                                sender="ai",
                                type="message",
                                format="text",
                                time=str(time.time()),
                                content=clean_text,
                                live2d_emotion=emotion_ref[0],
                                id=response_id,
                                mode="append",
                            )
                            await manager.send(ai_message, websocket)

                            current_emo = emotion_ref[0] or "normal"
                            task = asyncio.create_task(
                                tts_and_send(
                                    clean_text, current_emo, sentence_index, websocket
                                )
                            )
                            tts_tasks.append(task)
                            sentence_index += 1

                finally:
                    # 等待所有开启的 TTS 任务完成
                    if tts_tasks:
                        await asyncio.gather(*tts_tasks, return_exceptions=True)

            except Exception as e:
                print(f"全链路处理异常: {e}")
                error_msg = data_construct(
                    "ai",
                    "message",
                    "text",
                    str(time.time()),
                    "我现在的连接好像有点问题，请稍后再试。",
                )
                await manager.send(error_msg, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("client disconnected")


if __name__ == "__main__":
    uvicorn.run("server:app", host="localhost", port=8000, reload=True)
