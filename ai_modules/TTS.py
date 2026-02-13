import os
import uuid
import asyncio
import aiohttp
from pathlib import Path

# 配置项目根目录和相关路径
BASE_DIR = Path(__file__).parent.parent
CHARACTER_NAME = "yoimiya"
MODEL_ROOT = BASE_DIR / "ai_modules" / "TTS_model" / CHARACTER_NAME
OUTPUT_DIR = MODEL_ROOT / "output_audio"

# GPT-SoVITS API 配置
GPT_SOVITS_URL = "http://127.0.0.1:9880"

# 全局 aiohttp 会话，避免频繁握手
_session = None

async def get_session():
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session

# 当前使用的模型权重
CURRENT_GPT_WEIGHT = str(MODEL_ROOT / "yoimiya.ckpt")
CURRENT_SOVITS_WEIGHT = str(MODEL_ROOT / "yoimiya.pth")

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def gpt_sovits_tts(text, ref_audio_path, prompt_text, language="zh"):
    """
    通过 GPT-SoVITS API 生成语音
    """
    payload = {
        "text": text,
        "text_lang": language,
        "ref_audio_path": str(ref_audio_path),
        "prompt_text": prompt_text,
        "prompt_lang": language,
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
        "parallel_infer": True,  # 启用 API 内部并行推理
    }

    try:
        session = await get_session()
        async with session.post(f"{GPT_SOVITS_URL}/tts", json=payload) as response:
            if response.status == 200:
                return await response.read()
            else:
                try:
                    error_detail = await response.json()
                except:
                    error_detail = await response.text()
                print(f"GPT-SoVITS API 错误 (状态码 {response.status}): {error_detail}")
                return None
    except Exception as e:
        print(f"GPT-SoVITS 请求异常: {e}")
        return None


async def set_model_weights(gpt_path, sovits_path):
    """
    动态切换 GPT-SoVITS 的权重文件
    gpt_path: .ckpt 文件路径
    sovits_path: .pth 文件路径
    """
    try:
        async with aiohttp.ClientSession() as session:
            # 设置 GPT 权重
            async with session.get(
                f"{GPT_SOVITS_URL}/set_gpt_weights", params={"weights_path": gpt_path}
            ) as resp:
                gpt_res = await resp.text()

            # 设置 SoVITS 权重
            async with session.get(
                f"{GPT_SOVITS_URL}/set_sovits_weights",
                params={"weights_path": sovits_path},
            ) as resp:
                sovits_res = await resp.text()

            print(f"模型切换结果: GPT={gpt_res}, SoVITS={sovits_res}")
            return gpt_res == "success" and sovits_res == "success"
    except Exception as e:
        print(f"切换模型权重异常: {e}")
        return False


async def text_to_speech(text, emotion=None):
    """
    转换文本为对应的语音并直接返回音频数据

    Args:
        text: 要合成的文本
        emotion: 表情/情感倾向 (angry, happy, normal, questioning, sad)
    """
    # 1. 情感回退机制
    emotion = emotion or "normal"
    ref_text_path = MODEL_ROOT / "reference_audio" / f"{emotion}.txt"
    ref_audio_path = MODEL_ROOT / "reference_audio" / f"{emotion}.wav"

    if not ref_text_path.exists() or not ref_audio_path.exists():
        print(f"警告: 未找到表情 {emotion} 的参考文件，回退到 normal")
        emotion = "normal"
        ref_text_path = MODEL_ROOT / "reference_audio" / "normal.txt"
        ref_audio_path = MODEL_ROOT / "reference_audio" / "normal.wav"

    # 读取参考文本
    try:
        with open(ref_text_path, "r", encoding="utf-8") as f:
            reference_text = f.read().strip()
    except Exception as e:
        print(f"读取参考文本失败: {e}")
        reference_text = ""

    # 2. 使用 GPT-SoVITS API 合成语音
    print(f"使用 GPT-SoVITS API 合成语音 (表情: {emotion})...")
    return await gpt_sovits_tts(text, ref_audio_path, reference_text)


if __name__ == "__main__":
    # 测试代码
    async def test():
        data = await text_to_speech("你好呀，我是重构后的宵宫程序。", "happy")
        if data:
            with open("test_output.wav", "wb") as f:
                f.write(data)
            print(f"合成成功，获得数据大小: {len(data)} bytes")
        else:
            print("合成失败，请检查 GPT-SoVITS API 服务器是否启动")

    asyncio.run(test())
