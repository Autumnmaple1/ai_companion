from . import ASR
from . import LLM
from . import TTS

# 也可以保留原有的便捷导出
from .ASR import speech_to_text
from .LLM import generate_response
from .TTS import text_to_speech
