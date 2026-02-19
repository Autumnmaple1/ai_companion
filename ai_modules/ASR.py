import os
import asyncio
import base64
import io
import numpy as np
import soundfile as sf
import subprocess
from faster_whisper import WhisperModel
from backend.config import settings

# 全局模型实例，实现首次调用时加载并常驻显存
_model = None

def get_model():
    global _model
    if _model is None:
        print(f"INFO: 正在加载本地 ASR 模型 (Faster-Whisper, Size: {settings.ASR_MODEL_SIZE})...")
        # model_size: 'base', 'small', 'medium', 'large-v3-turbo'
        _model = WhisperModel(settings.ASR_MODEL_SIZE, device=settings.ASR_DEVICE, compute_type="float16")
        print(f"SUCCESS: ASR 模型已加载至 {settings.ASR_DEVICE}")
    return _model

async def speech_to_text(audio_data):
    """
    本地 ASR 部署方案：Faster-Whisper
    """
    if not audio_data:
        return ""

    # 1. 解码音频数据
    if isinstance(audio_data, str):
        if "," in audio_data:
            audio_data = audio_data.split(",")[1]
        data = base64.b64decode(audio_data)
    else:
        data = audio_data

    try:
        # 2. 调用 FFmpeg 将 WebM 转为 Faster-Whisper 需要的 PCM 格式 (16k, 单声道)
        # 使用你之前的 FFmpeg 成功逻辑
        def run_conversion():
            cmd = [
                'ffmpeg', '-y', '-i', 'pipe:0', 
                '-f', 'wav', '-ar', '16000', '-ac', '1', 
                '-acodec', 'pcm_s16le', 'pipe:1'
            ]
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=data)
            return stdout

        pcm_data = await asyncio.to_thread(run_conversion)
        if not pcm_data:
            print("ERROR: 音频转换失败")
            return ""

        # 3. 加载音频流识别
        audio_stream = io.BytesIO(pcm_data)
        audio_array, _ = sf.read(audio_stream)

        # 4. 在线程中推理，避免阻塞
        def transcribe():
            model = get_model()
            # 通过 initial_prompt 引导模型输出简体中文
            segments, info = model.transcribe(
                audio_array, 
                beam_size=5, 
                language="zh", 
                initial_prompt="以下是普通话的句子，使用简体中文。"
            )
            return "".join([segment.text for segment in segments])

        result_text = await asyncio.to_thread(transcribe)
        return result_text.strip()

    except Exception as e:
        print(f"Local ASR Error: {e}")
        return ""
