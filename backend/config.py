import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class Settings:
    # 基础路径
    BASE_DIR = PROJECT_ROOT

    # 路径配置

    CHARACTERS_DIR = PROJECT_ROOT / "backend" / "characters"
    AI_MODULES_DIR = PROJECT_ROOT / "ai_modules"

    # 服务器配置
    LETTA_URL = os.getenv("LETTA_URL", "http://localhost:8083")
    SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
    SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

    # ASR 配置
    ASR_MODEL_SIZE = os.getenv("ASR_MODEL_SIZE", "base")
    ASR_DEVICE = "cuda"  # 或 'cpu'

    # LLM 配置
    LLM_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    LLM_BASE_URL = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen-max")

    # TTS 配置
    GPT_SOVITS_URL = os.getenv("GPT_SOVITS_URL", "http://127.0.0.1:9880")

    def get_character_config(self, name: str = None) -> dict:
        import json

        char_name = name or os.getenv("CHARACTER_NAME", "yoimiya")
        config_path = self.CHARACTERS_DIR / f"{char_name}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Character config not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)


settings = Settings()
