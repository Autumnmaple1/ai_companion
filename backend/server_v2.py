"""
AI Companion WebSocket 服务端 v2
实现多会话管理、历史消息持久化、上下文自动注入
"""
import sys
import os
import time
import re
import asyncio
import json
import base64
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 加载 .env 文件
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_modules
from ai_modules import LLMModule, CloudTTS
from ai_modules.MEM import MemoryManager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks

# 数据库导入
from database import get_db_session, init_db
from database.crud import (
    create_session, get_session, get_sessions_by_user, delete_session,
    create_message, get_recent_messages, format_messages_for_llm
)

app = FastAPI(title="AI Companion Server v2")

# 初始化数据库
init_db()

# 初始化 TTS 引擎
tts_engine = CloudTTS()
tts_engine.initialize_models()


# ==================== 消息协议定义 ====================

class MessageType(str, Enum):
    """客户端消息类型"""
    INIT_SESSION = "init_session"      # 初始化/加载会话
    NEW_SESSION = "new_session"        # 创建新会话
    LIST_SESSIONS = "list_sessions"    # 获取会话列表
    DELETE_SESSION = "delete_session"  # 删除会话
    CHAT = "chat"                      # 发送聊天消息
    CHAT_AUDIO = "chat_audio"          # 发送语音消息


class ResponseType(str, Enum):
    """服务端响应类型"""
    SESSION_CREATED = "session_created"    # 会话已创建
    SESSION_LOADED = "session_loaded"      # 会话已加载（含历史）
    SESSION_LIST = "session_list"          # 会话列表
    SESSION_DELETED = "session_deleted"    # 会话已删除
    STREAM = "stream"                      # 流式文本片段
    STREAM_END = "stream_end"              # 流结束信号
    AUDIO = "audio"                        # 音频数据
    ERROR = "error"                        # 错误信息
    USER_MESSAGE_ECHO = "user_message_echo"  # 回显用户消息（语音转文字后）


@dataclass
class ClientSession:
    """客户端连接会话状态"""
    websocket: WebSocket
    user_id: str
    session_id: Optional[str] = None
    llm: LLMModule = field(default_factory=LLMModule)
    memory: MemoryManager = field(default_factory=MemoryManager)
    response_accumulator: str = ""
    
    def reset_accumulator(self):
        self.response_accumulator = ""


# ==================== 连接管理器 ====================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, ClientSession] = {}  # websocket_id -> ClientSession

    async def connect(self, websocket: WebSocket, user_id: str) -> ClientSession:
        """建立连接并创建客户端会话"""
        await websocket.accept()
        ws_id = str(id(websocket))
        client = ClientSession(websocket=websocket, user_id=user_id)
        self.active_connections[ws_id] = client
        print(f"[连接] 用户 {user_id} 已连接 (ws_id: {ws_id})")
        return client

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        ws_id = str(id(websocket))
        if ws_id in self.active_connections:
            client = self.active_connections.pop(ws_id)
            print(f"[断开] 用户 {client.user_id} 已断开 (ws_id: {ws_id})")

    def get_client(self, websocket: WebSocket) -> Optional[ClientSession]:
        """获取客户端会话"""
        ws_id = str(id(websocket))
        return self.active_connections.get(ws_id)


manager = ConnectionManager()


# ==================== 消息发送工具 ====================

async def send_response(websocket: WebSocket, msg_type: ResponseType, data: Dict[str, Any] = None):
    """统一发送响应格式"""
    response = {"type": msg_type.value}
    if data:
        response.update(data)
    await websocket.send_text(json.dumps(response, ensure_ascii=False))


async def send_error(websocket: WebSocket, message: str, code: str = "UNKNOWN_ERROR"):
    """发送错误响应"""
    await send_response(websocket, ResponseType.ERROR, {
        "code": code,
        "message": message
    })


# ==================== 后台任务 ====================

def save_assistant_message_task(
    session_id: str, 
    content: str, 
    raw_content: str,
    audio_url: Optional[str] = None
):
    """后台任务：保存助手消息到数据库"""
    db = get_db_session()
    try:
        create_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=content,
            raw_content=raw_content,
            audio_url=audio_url
        )
        print(f"[DB] 助手消息已保存 (session: {session_id[:8]}...)")
    except Exception as e:
        print(f"[DB Error] 保存助手消息失败: {e}")
    finally:
        db.close()


async def update_memory_task(memory: MemoryManager, user_query: str, assistant_response: str, user_id: str):
    """后台任务：更新 Mem0 长期记忆"""
    try:
        await memory.remember(user_query, assistant_response, user_id)
        print(f"[Mem0] 记忆已更新 (user: {user_id})")
    except Exception as e:
        print(f"[Mem0 Error] 更新记忆失败: {e}")


# ==================== 核心处理逻辑 ====================

async def handle_init_session(client: ClientSession, data: dict):
    """处理会话初始化/加载"""
    session_id = data.get("session_id")
    db = get_db_session()
    
    try:
        if session_id:
            # 加载已有会话
            session = get_session(db, session_id)
            if not session:
                await send_error(client.websocket, f"会话 {session_id} 不存在", "SESSION_NOT_FOUND")
                return
            
            # 加载最近 10 条消息到 LLM 的 history
            messages = get_recent_messages(db, session_id, count=10)
            client.llm.history.clear()
            for msg in messages:
                client.llm.history.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            client.session_id = session_id
            
            # 返回历史消息给前端
            await send_response(client.websocket, ResponseType.SESSION_LOADED, {
                "session_id": session_id,
                "title": session.title,
                "messages": [msg.to_dict() for msg in messages]
            })
            print(f"[会话] 已加载会话 {session_id[:8]}... (历史消息: {len(messages)} 条)")
        else:
            # 创建新会话
            session = create_session(db, user_id=client.user_id)
            client.session_id = session.id
            client.llm.history.clear()  # 清空 LLM 历史
            
            await send_response(client.websocket, ResponseType.SESSION_CREATED, {
                "session_id": session.id,
                "title": None
            })
            print(f"[会话] 已创建新会话 {session.id[:8]}...")
    finally:
        db.close()


async def handle_list_sessions(client: ClientSession):
    """处理获取会话列表"""
    db = get_db_session()
    try:
        sessions = get_sessions_by_user(db, client.user_id, limit=50)
        await send_response(client.websocket, ResponseType.SESSION_LIST, {
            "sessions": [s.to_dict() for s in sessions]
        })
    finally:
        db.close()


async def handle_delete_session(client: ClientSession, data: dict):
    """处理删除会话"""
    session_id = data.get("session_id")
    if not session_id:
        await send_error(client.websocket, "缺少 session_id", "MISSING_PARAM")
        return
    
    db = get_db_session()
    try:
        success = delete_session(db, session_id)
        if success:
            # 如果删除的是当前会话，清空状态
            if client.session_id == session_id:
                client.session_id = None
                client.llm.history.clear()
            
            await send_response(client.websocket, ResponseType.SESSION_DELETED, {
                "session_id": session_id
            })
        else:
            await send_error(client.websocket, "会话不存在", "SESSION_NOT_FOUND")
    finally:
        db.close()


async def handle_chat(client: ClientSession, data: dict):
    """处理聊天消息（核心逻辑）"""
    content = data.get("content", "").strip()
    if not content:
        await send_error(client.websocket, "消息内容不能为空", "EMPTY_CONTENT")
        return
    
    if not client.session_id:
        await send_error(client.websocket, "请先初始化会话", "NO_SESSION")
        return
    
    db = get_db_session()
    
    try:
        # === Step 1: 立即保存用户消息到数据库 ===
        create_message(
            db=db,
            session_id=client.session_id,
            role="user",
            content=content
        )
        print(f"[DB] 用户消息已保存: {content[:30]}...")
        
        # === Step 2: 检索 Mem0 长期记忆 ===
        facts = client.memory.get_context(content, user_id=client.user_id)
        print(f"[Mem0] 检索到记忆: {facts[:100] if facts else '无'}...")
        
        # === Step 3: 流式生成响应 ===
        client.reset_accumulator()
        
        async for chunk in client.llm.generate_response_stream(content, context=facts):
            client.response_accumulator += chunk
            
            # 实时推送文本片段
            await send_response(client.websocket, ResponseType.STREAM, {
                "delta": chunk,
                "emo": None  # emo 在流结束时统一提取
            })
        
        # === Step 4: 流结束处理 ===
        full_response = client.response_accumulator
        
        # 提取表情标签
        emo_match = re.search(r"\[emo:(\w+)\]", full_response)
        emotion = emo_match.group(1) if emo_match else None
        
        # 清理响应文本（移除 emo 标签及其后可能跟随的标点符号）
        clean_content = re.sub(r"\[emo:\w+\]\s*[!?！？。，、~]*", "", full_response).strip()
        # 同时处理句首残留的标点
        clean_content = re.sub(r"^[!?！？。，、~\s]+", "", clean_content)
        
        # 发送流结束信号
        await send_response(client.websocket, ResponseType.STREAM_END, {
            "emo": emotion,
            "content": clean_content  # 可选：发送完整的清理后文本
        })
        
        # === Step 5: 后台任务 - 保存助手消息 ===
        asyncio.create_task(asyncio.to_thread(
            save_assistant_message_task,
            client.session_id,
            clean_content,
            full_response  # raw_content 保留 emo 标签
        ))
        
        # === Step 6: 后台任务 - 更新 Mem0 记忆 ===
        asyncio.create_task(update_memory_task(
            client.memory, content, clean_content, client.user_id
        ))
        
        # === Step 7: TTS 语音合成 ===
        try:
            has_chinese = re.search(r"[\u4e00-\u9fa5]", clean_content)
            tts_lang = "zh" if has_chinese else "en"
            
            audio_data = await tts_engine.text_to_speech(clean_content, lang=tts_lang)
            audio_base64 = base64.b64encode(audio_data).decode("utf-8") if isinstance(audio_data, bytes) else audio_data
            
            await send_response(client.websocket, ResponseType.AUDIO, {
                "data": audio_base64,
                "format": "wav"
            })
        except Exception as tts_error:
            print(f"[TTS Error] 语音合成失败: {tts_error}")
            # TTS 失败不影响主流程，只记录日志
        
        print(f"[完成] 对话轮次完成 (emotion: {emotion})")
        
    except Exception as e:
        print(f"[Chat Error] 处理聊天消息失败: {e}")
        await send_error(client.websocket, f"处理失败: {str(e)}", "CHAT_ERROR")
    finally:
        db.close()


async def handle_chat_audio(client: ClientSession, data: dict):
    """处理语音消息"""
    audio_data = data.get("audio")
    if not audio_data:
        await send_error(client.websocket, "缺少音频数据", "MISSING_AUDIO")
        return
    
    try:
        # ASR 语音转文字
        text = await ai_modules.speech_to_text(audio_data)
        print(f"[ASR] 识别结果: {text}")
        
        # 回显用户消息
        await send_response(client.websocket, ResponseType.USER_MESSAGE_ECHO, {
            "content": text
        })
        
        # 复用文字聊天逻辑
        await handle_chat(client, {"content": text})
        
    except Exception as e:
        print(f"[ASR Error] 语音识别失败: {e}")
        await send_error(client.websocket, f"语音识别失败: {str(e)}", "ASR_ERROR")


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 主入口"""
    # 从查询参数获取 user_id
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        await websocket.close(code=4001, reason="Missing user_id parameter")
        return
    
    client = await manager.connect(websocket, user_id)
    
    try:
        while True:
            # 接收消息
            raw_data = await websocket.receive_text()
            
            try:
                message = json.loads(raw_data)
            except json.JSONDecodeError:
                await send_error(websocket, "无效的 JSON 格式", "INVALID_JSON")
                continue
            
            msg_type = message.get("type")
            
            # 消息路由
            if msg_type == MessageType.INIT_SESSION:
                await handle_init_session(client, message)
            
            elif msg_type == MessageType.NEW_SESSION:
                await handle_init_session(client, {})  # 空 session_id 表示新建
            
            elif msg_type == MessageType.LIST_SESSIONS:
                await handle_list_sessions(client)
            
            elif msg_type == MessageType.DELETE_SESSION:
                await handle_delete_session(client, message)
            
            elif msg_type == MessageType.CHAT:
                await handle_chat(client, message)
            
            elif msg_type == MessageType.CHAT_AUDIO:
                await handle_chat_audio(client, message)
            
            else:
                await send_error(websocket, f"未知消息类型: {msg_type}", "UNKNOWN_TYPE")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket Error] {e}")
        manager.disconnect(websocket)


# ==================== HTTP 端点（可选） ====================

@app.get("/api/sessions/{user_id}")
async def get_user_sessions(user_id: str):
    """HTTP 接口：获取用户会话列表"""
    db = get_db_session()
    try:
        sessions = get_sessions_by_user(db, user_id, limit=50)
        return {"sessions": [s.to_dict() for s in sessions]}
    finally:
        db.close()


@app.get("/api/sessions/{user_id}/{session_id}/messages")
async def get_session_messages(user_id: str, session_id: str, limit: int = 50):
    """HTTP 接口：获取会话消息"""
    db = get_db_session()
    try:
        session = get_session(db, session_id)
        if not session or session.user_id != user_id:
            return {"error": "Session not found"}, 404
        
        from database.crud import get_messages_by_session
        messages = get_messages_by_session(db, session_id, limit=limit)
        return {"messages": [m.to_dict() for m in messages]}
    finally:
        db.close()


# ==================== 启动入口 ====================

if __name__ == "__main__":
    uvicorn.run(
        "server_v2:app",
        host="localhost",
        port=8000,
        reload=True,
        reload_excludes=[".conda", "*.db"]
    )
