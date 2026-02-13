import asyncio
import websockets


async def hello():
    uri = "ws://127.0.0.1:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        message = "Hello, Server!"
        print(f"Sending message: {message}")
        await websocket.send(message)
        response = await websocket.recv()
        print(f"Received response: {response}")


if __name__ == "__main__":
    asyncio.run(hello())
