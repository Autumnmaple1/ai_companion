import os
import re
import uuid
import asyncio
import aiohttp
from pathlib import Path
from backend.config import settings

# 动态加载角色配置
char_config = settings.get_character_config()
CHARACTER_NAME = char_config["name"]
MODEL_ROOT = settings.BASE_DIR / "ai_modules" / "TTS_model" / CHARACTER_NAME
REFERENCE_AUDIO_DIR = settings.BASE_DIR / char_config["tts"]["reference_audio_dir"]

# GPT-SoVITS API 配置
GPT_SOVITS_URL = settings.GPT_SOVITS_URL

# 当前使用的模型权重（从配置读取并转换为绝对路径）
CURRENT_GPT_WEIGHT = str(settings.BASE_DIR / char_config["tts"]["weights"]["gpt"])
CURRENT_SOVITS_WEIGHT = str(settings.BASE_DIR / char_config["tts"]["weights"]["sovits"])

# 确保输出目录存在
OUTPUT_DIR = MODEL_ROOT / "output_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 全局 aiohttp 会话，避免频繁握手
_session = None


async def get_session():
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session


async def gpt_sovits_tts(text, ref_audio_path, prompt_text, language="zh"):
    """
    通过 GPT-SoVITS API 生成语音
    """
    # 转换路径为 Docker 容器内部相对路径
    ref_audio_path_obj = Path(ref_audio_path)
    root_name = "GPT-SoVITS-v2pro-20250604-nvidia50"
    if root_name in ref_audio_path_obj.parts:
        idx = ref_audio_path_obj.parts.index(root_name)
        ref_audio_path = "/".join(ref_audio_path_obj.parts[idx + 1 :])

    payload = {
        "text": text,
        "text_lang": language,
        "ref_audio_path": str(ref_audio_path),
        "prompt_text": prompt_text,
        "prompt_lang": language,
        "text_split_method": "cut1",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
        "parallel_infer": True,
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
    # 转换路径为 Docker 容器内部相对路径
    root_name = "GPT-SoVITS-v2pro-20250604-nvidia50"

    def to_relative(p):
        path_obj = Path(p)
        if root_name in path_obj.parts:
            idx = path_obj.parts.index(root_name)
            return "/".join(path_obj.parts[idx + 1 :])
        return str(p)

    gpt_path = to_relative(gpt_path)
    sovits_path = to_relative(sovits_path)

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
    """
    # 0. 文本预处理：将非常规标点（如 ~、～）替换为中文句号，并进行基础清洗
    if text:
        # 替换 ~ 为 。
        text = re.sub(r"[~～]+", "。", text)
        # 清理常见的聊天装饰符号
        text = re.sub(r"[❤⭐♪★☆]+", "。", text)
        # 合并重复的标点，避免合成过多冗余停顿
        text = re.sub(r"[。，！？]{2,}", lambda m: m.group(0)[0], text)

    # 1. 情感映射与回退机制
    emotion = emotion or "normal"

    # 定义支持的情感列表
    available_emotions = ["normal", "happy", "sad", "angry", "questioning"]
    if emotion not in available_emotions:
        emotion = "normal"

    ref_text_path = REFERENCE_AUDIO_DIR / f"{emotion}.txt"
    ref_audio_path = REFERENCE_AUDIO_DIR / f"{emotion}.wav"

    # 如果对应情感文件不存在，统一回退到 normal 并不再重复报警告
    if not ref_text_path.exists() or not ref_audio_path.exists():
        emotion = "normal"
        ref_text_path = REFERENCE_AUDIO_DIR / "normal.txt"
        ref_audio_path = REFERENCE_AUDIO_DIR / "normal.wav"

    # 读取参考文本
    reference_text = ""
    if ref_text_path.exists():
        try:
            with open(ref_text_path, "r", encoding="utf-8") as f:
                reference_text = f.read().strip()
        except:
            pass

    # 2. 使用 GPT-SoVITS API 合成语音
    # print(f"使用 GPT-SoVITS API 合成语音 (表情: {emotion})...")
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
