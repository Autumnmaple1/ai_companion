import sys
import os
import time
import re

# 确保项目根目录在路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from backend.config import settings
from backend.db_process import Database
import ai_modules
import asyncio
import json
import base64
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from backend.core.processor import StreamProcessor
from backend.core.utils import data_construct


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器，负责在启动时加载角色权重和初始化数据库"""
    # 初始化数据库
    db_path = settings.DATABASE_DIR / "conversations.db"
    app.state.db = Database(db_path)
    await app.state.db.connect()

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
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/config")
async def get_config():
    """获取当前加载的角色基本配置，用于前端动态切换"""
    try:
        config = settings.get_character_config()
        return {
            "character_name": config["name"],
            "display_name": config.get("display_name", config["name"]),
            "live2d": config.get(
                "live2d", {"model_path": "/models/LSS/LSS.model3.json"}
            ),
        }
    except Exception as e:
        return {"error": str(e)}


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


manager = ConnectionManager()


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    db = websocket.app.state.db
    # 获取当前角色名作为 agent_id
    agent_id = settings.CHARACTER_NAME

    try:
        while True:
            message = await manager.receive(websocket)
            message_type = message.get("format")
            content = message.get("content")
            text = ""
            if message_type == "text":
                text = content
                print(f"\n[用户输入文本]: {text}")
                # 存储用户消息（不发回前端，因为前端已显示）
                user_msg_id = int(time.time() * 1000)
                await db.save_message(agent_id, user_msg_id, "user", time.time(), text)

            elif message_type == "audio":
                audio_data = content
                asr_start = time.time()
                text = await ai_modules.ASR.speech_to_text(audio_data)
                asr_duration = (time.time() - asr_start) * 1000
                print(f"\n[性能监控-ASR]: 耗时 {asr_duration:.2f}ms | 识别结果: {text}")

                # 语音识别出的文本需要发回给前端显示，并存储
                user_msg_id = int(time.time() * 1000)
                user_message = data_construct(
                    sender="user",
                    type="message",
                    format="text",
                    time=str(time.time()),
                    content=text,
                    id=user_msg_id,
                )
                await manager.send(user_message, websocket)
                await db.save_message(agent_id, user_msg_id, "user", time.time(), text)

            if not text or not text.strip():
                continue

            try:
                # ─── 状态管理 ───
                response_id = int(time.time() * 1000)
                llm_start = time.time()

                # 初始化处理器 (架构调整：一次性接收)
                processor = StreamProcessor(
                    websocket, manager, response_id, db, agent_id
                )

                # --- LLM 响应获取 ---
                # 一次性生成，不走 stream
                full_text = await ai_modules.LLM.generate_response(text)

                llm_duration = (time.time() - llm_start) * 1000
                print(
                    f"[性能监控-LLM]: 耗时 {llm_duration:.2f}ms | 全文: {full_text[:50]}..."
                )

                # 这里的打印是为了给控制台看完整回复
                print(f"AI回复全文: {full_text}")

                # 将全文交给处理器，由其内部进行句子切分和 TTS 调度
                await processor.process_full_text(full_text)

                llm_total_duration = (time.time() - llm_start) * 1000
                print(f"[性能监控-全链路处理完成]: 总耗时 {llm_total_duration:.2f}ms")

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
    host = settings.SERVER_HOST
    port = settings.SERVER_PORT
    uvicorn.run("server:app", host=host, port=port, reload=True)
