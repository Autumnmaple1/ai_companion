import json
import time
import aiosqlite
import asyncio
import os
from backend.config import settings


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection = None

    async def connect(self):
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        self.connection = await aiosqlite.connect(self.db_path)
        await self._initialize_system_tables()

    async def _initialize_system_tables(self):
        """初始化代理列表管理表"""
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE
            )
            """
        )
        await self.connection.commit()

    async def _get_or_create_agent_index(self, agent_id: str) -> int:
        """获取 agent 的唯一索引 ID，不存在则创建"""
        async with self.connection.execute(
            "SELECT id FROM agent_list WHERE agent_id = ?", (agent_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
        
        # 插入新 agent 并获取自增 ID
        await self.connection.execute(
            "INSERT INTO agent_list (agent_id) VALUES (?)", (agent_id,)
        )
        await self.connection.commit()
        
        async with self.connection.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0]

    async def _ensure_agent_chat_table(self, agent_id: str) -> str:
        """确保对应 agent 映射的索引表存在"""
        agent_index = await self._get_or_create_agent_index(agent_id)
        table_name = f"chats_{agent_index}"
        
        # 每一条消息存一行，存储发送者、时间、内容、情感等
        await self.connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                sender TEXT,
                timestamp INTEGER,
                content TEXT,
                emotion TEXT
            )
        """
        )
        await self.connection.commit()
        return table_name

    async def save_message(self, agent_id, message_id, sender, timestamp, content, emotion="normal"):
        """保存单条消息到 agent 对应的索引表"""
        table_name = await self._ensure_agent_chat_table(agent_id)
        await self.connection.execute(
            f"""
            INSERT INTO {table_name} (message_id, sender, timestamp, content, emotion)
            VALUES (?, ?, ?, ?, ?)
        """,
            (str(message_id), sender, int(timestamp), content, emotion),
        )
        await self.connection.commit()

    async def get_history(self, agent_id, limit=50):
        """获取指定 agent 的历史消息列表"""
        table_name = await self._ensure_agent_chat_table(agent_id)
        cursor = await self.connection.execute(
            f"SELECT message_id, sender, timestamp, content, emotion FROM {table_name} ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        messages = []
        for row in rows:
            messages.append({
                "message_id": row[0],
                "sender": row[1],
                "timestamp": row[2],
                "content": row[3],
                "emotion": row[4]
            })
        return messages[::-1] # 按时间顺序返回

    async def close(self):
        if self.connection:
            await self.connection.close()
