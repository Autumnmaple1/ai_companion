import base64
import time

def data_construct(
    sender: str,
    type: str,
    format: str,
    content,
    time_str: str = None,
    live2d_emotion=None,
    id=None,
    mode=None,
    index=None,
) -> dict:
    if not time_str:
        time_str = str(time.time())
        
    if isinstance(content, bytes):
        content = base64.b64encode(content).decode("utf-8")
        
    res = {
        "sender": sender,
        "type": type,
        "format": format,
        "time": time_str,
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
