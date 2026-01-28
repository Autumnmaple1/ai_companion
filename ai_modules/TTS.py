import requests
import asyncio
import re

# ================= 配置区 =================
BASE_URL = "https://u872052-a197-82f777af.westc.gpuhub.com:8443"

# 使用服务器端的绝对路径
REF_AUDIO_PATH = "/root/GPT-SoVITS/test.wav"
GPT_MODEL = "/root/GPT-SoVITS/GPT_weights_v2Pro/vertin-e10.ckpt"
SOVITS_MODEL = "/root/GPT-SoVITS/SoVITS_weights_v2Pro/vertin_e8_s272.pth"

REF_TEXT = "go ahead please.i'm not like you, and you know that well"
REF_LANG = "en"
# ==========================================

class CloudTTS:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url

    def initialize_models(self):
        """
        同步初始化方法。在程序启动时调用一次，确保云端加载了验证过的模型。
        """
        try:
            print(f"正在配置远程 TTS 模型预览...")
            # 1. 切换 GPT 模型
            requests.get(f"{self.base_url}/set_gpt_weights", params={"weights_path": GPT_MODEL}, timeout=10)
            # 2. 切换 SoVITS 模型
            requests.get(f"{self.base_url}/set_sovits_weights", params={"weights_path": SOVITS_MODEL}, timeout=10)
            # 3. 设置参考音频
            requests.get(f"{self.base_url}/set_refer_audio", params={"refer_audio_path": REF_AUDIO_PATH}, timeout=10)
            print("远程模型配置指令已发送。")
        except Exception as e:
            print(f"初始化远程模型失败: {e}")

    async def text_to_speech(self, text: str, lang: str = "zh") -> bytes:
        """
        异步推理方法。对接 AI 助手的对话流。
        """
        # 清洗文本，移除 emo 标签
        clean_text = re.sub(r"\[emo:.*?\]", "", text).strip()
        
        if not clean_text:
            return b""

        payload = {
            "text": clean_text,
            "text_lang": lang,
            "ref_audio_path": REF_AUDIO_PATH,
            "prompt_text": REF_TEXT,
            "prompt_lang": REF_LANG,
            "media_type": "wav",
            "streaming_mode": False
        }

        def sync_call():
            return requests.post(f"{self.base_url}/tts", json=payload, timeout=30)

        try:
            response = await asyncio.to_thread(sync_call)
            if response.status_code == 200:
                return response.content
            else:
                print(f"TTS 合成失败: {response.status_code}, {response.text}")
                return b""
        except Exception as e:
            print(f"TTS 请求异常: {e}")
            return b""

if __name__ == "__main__":
    # 测试代码保持不变
    tts = CloudTTS()
    tts.initialize_models()
    async def test():
        print("开始推理测试...")
        data = await tts.text_to_speech("Success.", lang="en")
        if data:
            with open("output.wav", "wb") as f:
                f.write(data)
            print("推理成功，音频已保存至 output.wav")
    asyncio.run(test())
