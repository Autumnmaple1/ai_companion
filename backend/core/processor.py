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

    async def process_full_text(self, text: str):
        """
        一次性处理整段回复文字 (架构调整：一次性接收)
        """
        self.full_response = text

        # 提取每一句的情感和文字
        # 我们可以利用正则分割情感标签或利用之前的分句符号
        # [happy]你好呀！[questioning]要出去玩吗？ -> 分成两部分

        # 使用正则表达式分割：找到 [标签] 为起始点的每一段
        parts = re.split(r"(\[(?:happy|sad|angry|normal|questioning)\])", text)
        # parts [0] 可能是标签前内容, [1] 标签, [2] 标签后内容...

        current_emo = self.current_emotion

        # 遍历 parts
        i = 0
        while i < len(parts):
            p = parts[i]
            if not p:
                i += 1
                continue

            if re.match(r"\[(happy|sad|angry|normal|questioning)\]", p):
                current_emo = p.strip("[]")
                i += 1
                # 后面跟着的一段文本
                if i < len(parts):
                    content = parts[i].strip()
                    if content:
                        # 内部再按标点进行进一步细分句子处理，以减小单次合成粒度
                        sentences = self._split_to_sentences(content)
                        for sent in sentences:
                            self.current_emotion = current_emo
                            await self._handle_sentence(sent)
                i += 1
            else:
                # 处理没有标签开头的内容（通常是第一段）
                sentences = self._split_to_sentences(p.strip())
                for sent in sentences:
                    self.current_emotion = current_emo
                    await self._handle_sentence(sent)
                i += 1

        # 处理完成，冲刷剩余 buffer 并等待
        await self.finalize()

    def _split_to_sentences(self, text: str) -> list:
        """辅助方法：按标点符号细分句子"""
        # 使用正则分句 (保留标点)
        pattern = r"([^。！？!?;；\n]+[。！？!?;；\n]*)"
        results = re.findall(pattern, text)
        return [r.strip() for r in results if r.strip()]

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
            # 标记 ID 更新，确保在快速循环中生成唯一且递增的 ID
            new_id = int(time.time() * 1000)
            self.response_id = new_id if new_id > self.response_id else self.response_id + 1

        self.last_msg_emotion = self.current_emotion

        # TTS 逻辑：如果情感变化了，必须立即冲掉之前的 buffer，保证语气一致
        if self.current_emotion != self.buffer_emotion and self.unit_text_buffer:
            await self._flush_tts_buffer()
            # 如果在合并首句过程中发生情感变化导致冲刷，需标记首句已发送
            if not self.first_sent_sent:
                self.first_sent_sent = True

        if not self.unit_text_buffer:
            # 开始新缓冲区时，同步当前的消息 ID
            self.buffer_id = self.response_id

        self.unit_text_buffer.append(clean_text)
        self.buffer_emotion = self.current_emotion

        # 合并策略优化：
        total_len = sum(len(s) for s in self.unit_text_buffer)
        if not self.first_sent_sent:
            # 首句响应至少要 15 字，不够就合并后续句子直到 15 字
            if total_len >= 15:
                await self._flush_tts_buffer()
                self.first_sent_sent = True
        else:
            # 除首句外，累积多句直到总字数大于 40 时发送（或等待结束时 finalize 冲刷）
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
