"""
CRUD 操作 - 会话和消息的增删改查
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session as DBSession
from .models import Session, Message


# ==================== Session CRUD ====================

def create_session(db: DBSession, user_id: str, title: Optional[str] = None) -> Session:
    """创建新会话"""
    session = Session(user_id=user_id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: DBSession, session_id: str) -> Optional[Session]:
    """根据 ID 获取会话"""
    return db.query(Session).filter(Session.id == session_id).first()


def get_sessions_by_user(db: DBSession, user_id: str, limit: int = 50) -> List[Session]:
    """获取用户的所有会话，按更新时间倒序"""
    return db.query(Session).filter(
        Session.user_id == user_id
    ).order_by(Session.updated_at.desc()).limit(limit).all()


def update_session_title(db: DBSession, session_id: str, title: str) -> Optional[Session]:
    """更新会话标题"""
    session = get_session(db, session_id)
    if session:
        session.title = title[:50] if title else None  # 限制标题长度
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


def update_session_timestamp(db: DBSession, session_id: str) -> Optional[Session]:
    """更新会话时间戳"""
    session = get_session(db, session_id)
    if session:
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


def delete_session(db: DBSession, session_id: str) -> bool:
    """删除会话（级联删除所有消息）"""
    session = get_session(db, session_id)
    if session:
        db.delete(session)
        db.commit()
        return True
    return False


# ==================== Message CRUD ====================

def create_message(
    db: DBSession,
    session_id: str,
    role: str,
    content: str,
    raw_content: Optional[str] = None,
    audio_url: Optional[str] = None
) -> Message:
    """创建新消息"""
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        raw_content=raw_content,
        audio_url=audio_url
    )
    db.add(message)
    
    # 同时更新会话时间戳
    update_session_timestamp(db, session_id)
    
    # 如果是第一条用户消息且会话没有标题，自动设置标题
    session = get_session(db, session_id)
    if session and not session.title and role == 'user':
        # 取前10个字符作为标题
        title = content[:10] + ('...' if len(content) > 10 else '')
        session.title = title
    
    db.commit()
    db.refresh(message)
    return message


def get_message(db: DBSession, message_id: str) -> Optional[Message]:
    """根据 ID 获取消息"""
    return db.query(Message).filter(Message.id == message_id).first()


def get_messages_by_session(
    db: DBSession, 
    session_id: str, 
    limit: Optional[int] = None
) -> List[Message]:
    """获取会话的所有消息，按创建时间正序"""
    query = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def get_recent_messages(
    db: DBSession, 
    session_id: str, 
    count: int = 10
) -> List[Message]:
    """获取会话最近的 N 条消息（用于上下文注入）"""
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.desc()).limit(count).all()
    
    # 反转顺序，使其按时间正序
    return list(reversed(messages))


def delete_message(db: DBSession, message_id: str) -> bool:
    """删除单条消息"""
    message = get_message(db, message_id)
    if message:
        db.delete(message)
        db.commit()
        return True
    return False


def clear_session_messages(db: DBSession, session_id: str) -> int:
    """清空会话的所有消息"""
    count = db.query(Message).filter(Message.session_id == session_id).delete()
    db.commit()
    return count


# ==================== 辅助函数 ====================

def get_session_message_count(db: DBSession, session_id: str) -> int:
    """获取会话的消息数量"""
    return db.query(Message).filter(Message.session_id == session_id).count()


def format_messages_for_llm(messages: List[Message]) -> List[dict]:
    """
    将消息列表格式化为 LLM 所需的格式
    返回: [{"role": "user/assistant", "content": "..."}, ...]
    """
    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
