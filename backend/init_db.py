"""
数据库初始化脚本
运行此脚本来创建数据库表
"""
import sys
import os

# 添加父目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_db_session, Session, Message


def create_tables():
    """创建所有数据库表"""
    print("正在创建数据库表...")
    init_db()
    print("数据库表创建完成！")


def test_db():
    """测试数据库连接和基本操作"""
    from database.crud import (
        create_session, 
        create_message, 
        get_sessions_by_user,
        get_messages_by_session
    )
    
    db = get_db_session()
    
    try:
        # 创建测试会话
        print("\n--- 测试创建会话 ---")
        session = create_session(db, user_id="test_user_001")
        print(f"创建会话: {session.to_dict()}")
        
        # 创建测试消息
        print("\n--- 测试创建消息 ---")
        msg1 = create_message(
            db, 
            session_id=session.id, 
            role="user", 
            content="你好，我是测试用户"
        )
        print(f"用户消息: {msg1.to_dict()}")
        
        msg2 = create_message(
            db,
            session_id=session.id,
            role="assistant",
            content="你好！我是你的AI伙伴，很高兴认识你~",
            raw_content="[emo:开心]你好！我是你的AI伙伴，很高兴认识你~[/emo]",
            audio_url="/audio/response_001.wav"
        )
        print(f"助手消息: {msg2.to_dict()}")
        
        # 查询会话
        print("\n--- 测试查询会话 ---")
        sessions = get_sessions_by_user(db, "test_user_001")
        for s in sessions:
            print(f"会话: {s.to_dict()}")
        
        # 查询消息
        print("\n--- 测试查询消息 ---")
        messages = get_messages_by_session(db, session.id)
        for m in messages:
            print(f"消息: {m.to_dict()}")
        
        print("\n✅ 数据库测试通过！")
        
    except Exception as e:
        print(f"\n❌ 数据库测试失败: {e}")
        raise
    finally:
        db.close()


def show_help():
    """显示帮助信息"""
    print("""
数据库初始化脚本使用方法:

    python init_db.py create    # 创建数据库表
    python init_db.py test      # 测试数据库操作
    python init_db.py help      # 显示帮助信息
    """)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        create_tables()
    elif command == "test":
        create_tables()
        test_db()
    elif command == "help":
        show_help()
    else:
        print(f"未知命令: {command}")
        show_help()
        sys.exit(1)
