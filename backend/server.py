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


@app.on_event("startup")
async def startup_event():
    """服务器启动时加载角色权重"""
    try:
        from ai_modules.TTS import (
            CHARACTER_NAME,
            CURRENT_GPT_WEIGHT,
            CURRENT_SOVITS_WEIGHT,
        )

        print(f"INFO: [系统初始化] 正在加载角色模型: {CHARACTER_NAME}...")
        success = await ai_modules.TTS.set_model_weights(
            CURRENT_GPT_WEIGHT, CURRENT_SOVITS_WEIGHT
        )
        if success:
            print(f"SUCCESS: [模型加载完毕] 已成功切换至 GPU 加速引擎")
        else:
            print(f"WARNING: [模型加载异常] 无法读取模型权重，请检查路径。")
    except Exception as e:
        print(f"WARNING: [初始化跳过] {e}")


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


# 并发限制信号量（建议 2-3 以兼顾速度和稳定性）
TTS_SEMAPHORE = asyncio.Semaphore(3)


async def tts_worker(text, emotion, index, websocket, context):
    """
    合成生产者：负责调用 TTS，并将结果放入缓冲区
    """
    async with TTS_SEMAPHORE:
        try:
            start_time = time.time()
            tts_audio = await ai_modules.TTS.text_to_speech(text, emotion)

            if tts_audio:
                duration = (time.time() - start_time) * 1000
                print(f"[TTS完成] 第 {index} 单元 | 耗时 {duration:.2f}ms")
                context["buffers"][index] = tts_audio
                await flush_audio_queue(websocket, context)
            else:
                print(f"ERROR: [TTS失败] 第 {index} 单元合成返回空数据")
        except Exception as e:
            print(f"CRITICAL: [TTS异常] {e}")


async def flush_audio_queue(websocket, context):
    """
    发送消费者：严格按 index 顺序发送已完成的音频
    """
    async with context["send_lock"]:
        while context["next_index"] in context["buffers"]:
            idx = context["next_index"]
            audio_data = context["buffers"].pop(idx)

            ai_audio_message = data_construct(
                sender="ai",
                type="voice",
                format="audio",
                time=str(time.time()),
                content=audio_data,
                index=idx,
            )
            await manager.send(ai_audio_message, websocket)
            print(f"SUCCESS: [音频下发] Index {idx}")
            context["next_index"] += 1


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await manager.receive(websocket)
            message_type = message.get("format")
            content = message.get("content")
            text = ""
            if message_type == "text":
                text = content
                print(f"\n[用户输入文本]: {text}")
            elif message_type == "audio":
                audio_data = content
                asr_start = time.time()
                text = await ai_modules.ASR.speech_to_text(audio_data)
                asr_duration = (time.time() - asr_start) * 1000
                print(f"\n[性能监控-ASR]: 耗时 {asr_duration:.2f}ms | 识别结果: {text}")
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
                # ─── 状态管理 ───
                response_id = int(time.time() * 1000)
                llm_start = time.time()
                first_token_time = None
                full_response = ""
                sentence_buffer = ""
                emotion_ref = [None]
                emotion_found = False

                # 核心：有序发送上下文
                context = {"next_index": 0, "buffers": {}, "send_lock": asyncio.Lock()}
                sentence_index = 0
                tts_tasks = []

                # --- 单元合并状态 ---
                first_sent_sent = False
                unit_text_buffer = []
                UNIT_SIZE = 2

                # 断句符号优化
                hard_terminators = ("。", "！", "？", "!", "?", "\n")
                soft_terminators = ("，", ",", "；", ";")

                async for chunk in ai_modules.LLM.generate_response_stream(text):
                    if first_token_time is None:
                        first_token_time = (time.time() - llm_start) * 1000
                        print(
                            f"[性能监控-LLM首字]: 耗时 {first_token_time:.2f}ms (打字机效果开始)"
                        )

                    full_response += chunk
                    sentence_buffer += chunk
                    print(chunk, end="", flush=True)

                    # 1. 提取情感
                    if not emotion_found and "]" in full_response:
                        emotion_tag = re.search(r"\[(.*?)\]", full_response)
                        if emotion_tag:
                            emotion_ref[0] = emotion_tag.group(1)
                            emotion_found = True
                            sentence_buffer = re.sub(r"\[.*?\]", "", sentence_buffer)

                    # 2. 检查逻辑：首句极速，后续积累
                    should_split = False
                    if any(t in chunk for t in hard_terminators):
                        should_split = True
                    elif (
                        not first_sent_sent
                        and len(sentence_buffer) > 8
                        and any(t in chunk for t in soft_terminators)
                    ):
                        should_split = True
                    elif len(sentence_buffer) > 25 and any(
                        t in chunk for t in soft_terminators
                    ):
                        should_split = True

                    if should_split:
                        clean_text = re.sub(r"\[.*?\]", "", sentence_buffer).strip()
                        if clean_text:
                            # 文本消息
                            msg = data_construct(
                                sender="ai",
                                type="message",
                                format="text",
                                time=str(time.time()),
                                content=clean_text + " ",
                                live2d_emotion=emotion_ref[0],
                                id=response_id,
                                mode="append",
                            )
                            await manager.send(msg, websocket)

                            # TTS 调度
                            current_emo = emotion_ref[0] or "normal"
                            if not first_sent_sent:
                                tts_tasks.append(
                                    asyncio.create_task(
                                        tts_worker(
                                            clean_text,
                                            current_emo,
                                            sentence_index,
                                            websocket,
                                            context,
                                        )
                                    )
                                )
                                sentence_index += 1
                                first_sent_sent = True
                            else:
                                unit_text_buffer.append(clean_text)
                                if len(unit_text_buffer) >= UNIT_SIZE:
                                    combo = " ".join(unit_text_buffer)
                                    tts_tasks.append(
                                        asyncio.create_task(
                                            tts_worker(
                                                combo,
                                                current_emo,
                                                sentence_index,
                                                websocket,
                                                context,
                                            )
                                        )
                                    )
                                    sentence_index += 1
                                    unit_text_buffer = []
                        sentence_buffer = ""
                    # 结束当前 chunk 处理
                # 结束 LLM stream

                # 3. 收尾逻辑
                final_rem = re.sub(r"\[.*?\]", "", sentence_buffer).strip()
                if final_rem:
                    unit_text_buffer.append(final_rem)
                    # 发送最后一段文本
                    final_msg = data_construct(
                        sender="ai",
                        type="message",
                        format="text",
                        time=str(time.time()),
                        content=final_rem,
                        live2d_emotion=emotion_ref[0],
                        id=response_id,
                        mode="append",
                    )
                    await manager.send(final_msg, websocket)

                if unit_text_buffer:
                    combined = " ".join(unit_text_buffer)
                    tts_tasks.append(
                        asyncio.create_task(
                            tts_worker(
                                combined,
                                emotion_ref[0] or "normal",
                                sentence_index,
                                websocket,
                                context,
                            )
                        )
                    )

                if tts_tasks:
                    await asyncio.gather(*tts_tasks, return_exceptions=True)

                llm_total_duration = (time.time() - llm_start) * 1000
                print(f"\n[性能监控-LLM结束]: 总生成时间 {llm_total_duration:.2f}ms")

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
