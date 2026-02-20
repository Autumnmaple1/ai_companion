import asyncio
import re
import time
import ai_modules
from backend.config import settings
from backend.core.utils import data_construct

TTS_SEMAPHORE = asyncio.Semaphore(2)

class StreamProcessor:
    def __init__(self, websocket, manager, response_id, db=None, agent_id=None):
        self.websocket, self.manager, self.db, self.agent_id = websocket, manager, db, agent_id
        self.response_id = response_id
        self.current_emotion = "normal"
        self.last_msg_emotion = None
        self.context = {"next_index": 0, "buffers": {}, "send_lock": asyncio.Lock()}
        self.sentence_index = 0
        self.tts_tasks = []
        self.first_sent_sent = False
        self.unit_text_buffer = []
        self.buffer_emotion, self.buffer_id = "normal", response_id

    async def process_full_text(self, text: str):
        parts = re.split(r"(\[(?:happy|sad|angry|normal|questioning)\])", text)
        for i, p in enumerate(parts):
            if not p and i % 2 == 0: continue
            if re.match(r"\[(happy|sad|angry|normal|questioning)\]", p):
                if self.unit_text_buffer: await self._flush_tts_buffer()
                self.current_emotion = p.strip("[]")
                self.response_id = max(int(time.time()*1000), self.response_id + 1)
            else:
                content = p.strip()
                if not content: continue
                if self.db and self.agent_id:
                    await self.db.save_message(self.agent_id, self.response_id, "ai", time.time(), content, self.current_emotion)
                for sent in re.findall(r"([^。！？!?;；\n]+[。！？!?;；\n]*)", content):
                    await self._handle_sentence(sent.strip())
        await self.finalize()

    async def _handle_sentence(self, clean_text):
        if self.current_emotion != self.buffer_emotion and self.unit_text_buffer:
            await self._flush_tts_buffer()
            self.first_sent_sent = True
        
        if not self.unit_text_buffer: self.buffer_id = self.response_id
        self.unit_text_buffer.append(clean_text)
        self.buffer_emotion = self.current_emotion
        
        total_len = sum(len(s) for s in self.unit_text_buffer)
        if (not self.first_sent_sent and total_len >= 15) or total_len > 40:
            await self._flush_tts_buffer()
            self.first_sent_sent = True

    async def _flush_tts_buffer(self):
        if not self.unit_text_buffer: return
        self.tts_tasks.append(asyncio.create_task(self._tts_worker(" ".join(self.unit_text_buffer), self.buffer_emotion, self.sentence_index, self.buffer_id)))
        self.sentence_index += 1
        self.unit_text_buffer = []

    async def finalize(self):
        await self._flush_tts_buffer()
        if self.tts_tasks: await asyncio.gather(*self.tts_tasks, return_exceptions=True)

    async def _tts_worker(self, text, emotion, index, resp_id):
        async with TTS_SEMAPHORE:
            tts_audio = await ai_modules.TTS.text_to_speech(text, emotion)
            if tts_audio:
                self.context["buffers"][index] = {"audio": tts_audio, "text": text, "emotion": emotion, "id": resp_id}
                await self._flush_audio_queue()

    async def _flush_audio_queue(self):
        async with self.context["send_lock"]:
            while self.context["next_index"] in self.context["buffers"]:
                idx = self.context["next_index"]
                d = self.context["buffers"].pop(idx)
                msg = data_construct("ai", "voice", "audio", d["audio"], id=d["id"], index=idx, live2d_emotion=d["emotion"])
                msg["text"] = d["text"]
                await self.manager.send(msg, self.websocket)
                self.context["next_index"] += 1
