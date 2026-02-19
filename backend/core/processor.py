import asyncio
import re
import time
import ai_modules
from backend.config import settings

# 并发限制信号量（对于 V4 模型建议设为 1，优先保证首句合成速度）
TTS_SEMAPHORE = asyncio.Semaphore(2)


def data_construct(
    sender: str,
    type: str,
    format: str,
    time_str: str,
    content,
    live2d_emotion=None,
    id=None,
    mode=None,
    index=None,
) -> dict:
    import base64

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


class StreamProcessor:
    def __init__(self, websocket, manager, response_id):
        self.websocket = websocket
        self.manager = manager
        self.response_id = response_id

        self.full_response = ""
        self.sentence_buffer = ""
        self.current_emotion = "normal"  # 默认情感
        self.last_msg_emotion = None  # 上一次发送消息时的情感

        self.context = {"next_index": 0, "buffers": {}, "send_lock": asyncio.Lock()}
        self.sentence_index = 0
        self.tts_tasks = []

        self.first_sent_sent = False
        self.unit_text_buffer = []
        self.buffer_emotion = "normal"  # 当前 buffer 中文字的情感
        self.buffer_id = response_id  # 当前 buffer 对应的消息 ID

        # 断句符号优化
        self.hard_terminators = ("。", "！", "？", "!", "?", "\n")
        self.soft_terminators = ("；", ";")

    async def process_chunk(self, chunk: str):
        self.full_response += chunk
        self.sentence_buffer += chunk

        # 检查逻辑：精准断句 + 情感标签识别
        # 如果 chunk 中包含 [，说明可能开启了新情感，我们要尝试把之前的句子先切出来
        term_in_chunk_idx = -1

        # 1. 优先检查情感标签的开始 [
        if "[" in chunk:
            # 找到 [ 在 chunk 中的相对位置
            tag_start_idx = chunk.find("[") 
            # 只有当 [ 前面有内容时，才把之前的内容切为一个句子
            # 这里的逻辑是：[ 通常意味着新的一段开始
            if len(self.sentence_buffer) - (len(chunk) - tag_start_idx) > 0:
                term_in_chunk_idx = tag_start_idx - 1  # 假设在 [ 前切断

        # 2. 如果没触发情感切分，检查标点符号
        if term_in_chunk_idx == -1:
            for i, char in enumerate(chunk):
                if char in self.hard_terminators:
                    term_in_chunk_idx = i
                    break
                if char in self.soft_terminators:
                    current_buf_len = len(self.sentence_buffer) - (len(chunk) - i)
                    if not self.first_sent_sent and current_buf_len > 8:
                        term_in_chunk_idx = i
                        break
                    if current_buf_len > 25:
                        term_in_chunk_idx = i
                        break

        if term_in_chunk_idx != -1:
            # 找到切分点相对位置
            split_pos = len(self.sentence_buffer) - (len(chunk) - term_in_chunk_idx) + 1
            raw_sentence = self.sentence_buffer[:split_pos]
            self.sentence_buffer = self.sentence_buffer[split_pos:]

            # 在处理每一句之前，解析其中的情感标签
            # 提取最后出现的情感标签作为当前情感
            tags = re.findall(r"\[(happy|sad|angry|normal|questioning)\]", raw_sentence)
            if tags:
                self.current_emotion = tags[-1]

            # 过滤掉所有标签
            clean_text = re.sub(r"\[.*?\]", "", raw_sentence).strip()
            if clean_text:
                await self._handle_sentence(clean_text)

    async def _handle_sentence(self, clean_text):
        # 情感切换检查：如果当前句子的情感与上一句不同，强制分配新的消息 ID
        if (
            self.last_msg_emotion is not None
            and self.current_emotion != self.last_msg_emotion
        ):
            # 标记 ID 更新
            self.response_id = int(time.time() * 1000)

        self.last_msg_emotion = self.current_emotion

        # TTS 逻辑：如果情感变化了，必须立即冲掉之前的 buffer，保证语气一致
        if self.current_emotion != self.buffer_emotion and self.unit_text_buffer:
            await self._flush_tts_buffer()

        if not self.unit_text_buffer:
            # 开始新缓冲区时，同步当前的消息 ID
            self.buffer_id = self.response_id

        self.unit_text_buffer.append(clean_text)
        self.buffer_emotion = self.current_emotion

        # 合并策略优化：
        if not self.first_sent_sent:
            # 首句立即发送，保证首字响应速度
            await self._flush_tts_buffer()
            self.first_sent_sent = True
        else:
            # 除首句外，累积多句直到总字数大于 40 时发送（或等待结束时 finalize 冲刷）
            # 这样可以在保证性能的同时，让 TTS 合成更长的文本，语调更自然
            total_len = sum(len(s) for s in self.unit_text_buffer)
            if total_len > 40:
                await self._flush_tts_buffer()

    async def _flush_tts_buffer(self):
        """将当前 buffer 中的文本提交合成"""
        if not self.unit_text_buffer:
            return

        combo = " ".join(self.unit_text_buffer)
        emo = self.buffer_emotion
        idx = self.sentence_index
        resp_id = self.buffer_id  # 使用进入缓冲区时记录的消息 ID

        self.tts_tasks.append(
            asyncio.create_task(self._tts_worker(combo, emo, idx, resp_id))
        )

        self.sentence_index += 1
        self.unit_text_buffer = []

    async def finalize(self):
        # 处理剩余句子缓冲区
        if self.sentence_buffer.strip():
            tags = re.findall(
                r"\[(happy|sad|angry|normal|questioning)\]", self.sentence_buffer
            )
            if tags:
                self.current_emotion = tags[-1]

            clean_rem = re.sub(r"\[.*?\]", "", self.sentence_buffer).strip()
            if clean_rem:
                # 调用处理句子函数，自动处理消息分泡逻辑
                await self._handle_sentence(clean_rem)

        # 冲掉最后的 TTS
        await self._flush_tts_buffer()

        if self.tts_tasks:
            await asyncio.gather(*self.tts_tasks, return_exceptions=True)

    async def _tts_worker(self, text, emotion, index, resp_id):
        async with TTS_SEMAPHORE:
            try:
                start_time = time.time()
                tts_audio = await ai_modules.TTS.text_to_speech(text, emotion)

                if tts_audio:
                    duration = (time.time() - start_time) * 1000
                    print(f"[TTS完成] 第 {index} 单元 | 耗时 {duration:.2f}ms")
                    # 存储音频及其对应的文本、情感和消息 ID
                    self.context["buffers"][index] = {
                        "audio": tts_audio,
                        "text": text,
                        "emotion": emotion,
                        "id": resp_id,
                    }
                    await self._flush_audio_queue()
                else:
                    print(f"ERROR: [TTS失败] 第 {index} 单元合成返回空数据")
            except Exception as e:
                print(f"CRITICAL: [TTS异常] {e}")

    async def _flush_audio_queue(self):
        async with self.context["send_lock"]:
            while self.context["next_index"] in self.context["buffers"]:
                idx = self.context["next_index"]
                data_obj = self.context["buffers"].pop(idx)

                ai_audio_message = data_construct(
                    sender="ai",
                    type="voice",
                    format="audio",
                    time_str=str(time.time()),
                    content=data_obj["audio"],
                    index=idx,
                    id=data_obj["id"],
                )
                # 附加同步信息
                ai_audio_message["text"] = data_obj["text"]
                ai_audio_message["live2d_emotion"] = data_obj["emotion"]

                await self.manager.send(ai_audio_message, self.websocket)
                print(
                    f"SUCCESS: [音频下发] Index {idx} | Text: {data_obj['text'][:20]}..."
                )
                self.context["next_index"] += 1
