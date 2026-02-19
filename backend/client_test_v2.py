"""
WebSocket 客户端测试脚本 - 用于测试 server_v2 的新协议
"""
import asyncio
import json
import websockets

SERVER_URL = "ws://localhost:8000/ws/chat"
USER_ID = "test_user_001"


async def send_and_print(ws, msg_type: str, data: dict = None):
    """发送消息并打印"""
    message = {"type": msg_type}
    if data:
        message.update(data)
    
    print(f"\n>>> 发送: {json.dumps(message, ensure_ascii=False)}")
    await ws.send(json.dumps(message))


async def receive_all(ws, timeout: float = 10.0):
    """接收所有响应直到超时"""
    responses = []
    try:
        while True:
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(response)
            responses.append(data)
            
            # 格式化打印
            resp_type = data.get("type", "unknown")
            if resp_type == "stream":
                print(data.get("delta", ""), end="", flush=True)
            elif resp_type == "stream_end":
                print(f"\n<<< 流结束: emo={data.get('emo')}")
            elif resp_type == "audio":
                print(f"<<< 收到音频数据 ({len(data.get('data', ''))} bytes)")
            else:
                print(f"<<< 收到: {json.dumps(data, ensure_ascii=False, indent=2)}")
            
            # 如果是流结束或错误，可能需要继续等待音频
            if resp_type in ["error", "session_deleted"]:
                break
                
    except asyncio.TimeoutError:
        print("\n[超时] 接收完毕")
    
    return responses


async def test_full_flow():
    """完整流程测试"""
    url = f"{SERVER_URL}?user_id={USER_ID}"
    
    async with websockets.connect(url) as ws:
        print("=" * 50)
        print("WebSocket 连接已建立")
        print("=" * 50)
        
        # 1. 获取会话列表
        print("\n### 测试 1: 获取会话列表 ###")
        await send_and_print(ws, "list_sessions")
        await receive_all(ws, timeout=3.0)
        
        # 2. 创建新会话
        print("\n### 测试 2: 创建新会话 ###")
        await send_and_print(ws, "new_session")
        responses = await receive_all(ws, timeout=3.0)
        
        session_id = None
        for resp in responses:
            if resp.get("type") == "session_created":
                session_id = resp.get("session_id")
                print(f"[会话ID] {session_id}")
                break
        
        if not session_id:
            print("[错误] 未能获取会话ID")
            return
        
        # 3. 发送聊天消息
        print("\n### 测试 3: 发送聊天消息 ###")
        await send_and_print(ws, "chat", {
            "session_id": session_id,
            "content": "你好，我叫小明，今年25岁，是一名程序员"
        })
        await receive_all(ws, timeout=30.0)
        
        # 4. 发送第二条消息
        print("\n### 测试 4: 发送第二条消息 ###")
        await send_and_print(ws, "chat", {
            "session_id": session_id,
            "content": "你还记得我的名字吗？"
        })
        await receive_all(ws, timeout=30.0)
        
        # 5. 重新加载会话（模拟刷新页面）
        print("\n### 测试 5: 重新加载会话 ###")
        await send_and_print(ws, "init_session", {
            "session_id": session_id
        })
        await receive_all(ws, timeout=3.0)
        
        # 6. 再次获取会话列表（应该能看到新会话）
        print("\n### 测试 6: 再次获取会话列表 ###")
        await send_and_print(ws, "list_sessions")
        await receive_all(ws, timeout=3.0)
        
        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)


async def test_simple_chat():
    """简单聊天测试"""
    url = f"{SERVER_URL}?user_id={USER_ID}"
    
    async with websockets.connect(url) as ws:
        print("已连接到服务器")
        
        # 创建新会话
        await send_and_print(ws, "new_session")
        responses = await receive_all(ws, timeout=3.0)
        
        session_id = None
        for resp in responses:
            if resp.get("type") == "session_created":
                session_id = resp.get("session_id")
                break
        
        # 发送消息
        await send_and_print(ws, "chat", {
            "content": "你好！"
        })
        await receive_all(ws, timeout=30.0)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "simple":
        asyncio.run(test_simple_chat())
    else:
        asyncio.run(test_full_flow())
