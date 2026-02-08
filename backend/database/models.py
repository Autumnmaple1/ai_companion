"""
数据库模型定义
使用 SQLAlchemy ORM 定义 Sessions 和 Messages 表
"""
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


def generate_uuid():
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


class Session(Base):
    """会话表 - 存储会话元数据"""
    __tablename__ = 'sessions'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(50), nullable=True)  # 取首句前10字
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联消息
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, title={self.title})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0
        }


class Message(Base):
    """消息表 - 存储具体对话内容"""
    __tablename__ = 'messages'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' 或 'assistant'
    content = Column(Text, nullable=False)  # 纯文本内容
    raw_content = Column(Text, nullable=True)  # 带 emo 标签的原始内容
    audio_url = Column(String(500), nullable=True)  # 音频文件 URL
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联会话
    session = relationship("Session", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, content={self.content[:20]}...)>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "raw_content": self.raw_content,
            "audio_url": self.audio_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
