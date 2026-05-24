import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class VoiceConfig:
    rate: int = int(os.getenv("DREX_VOICE_RATE", "175"))
    volume: float = float(os.getenv("DREX_VOICE_VOLUME", "0.9"))
    voice_index: int = int(os.getenv("DREX_VOICE_INDEX", "0"))
    language: str = os.getenv("DREX_VOICE_LANG", "en-US")
    energy_threshold: int = int(os.getenv("DREX_ENERGY_THRESHOLD", "300"))
    pause_threshold: float = float(os.getenv("DREX_PAUSE_THRESHOLD", "0.8"))
    timeout: int = int(os.getenv("DREX_LISTEN_TIMEOUT", "5"))
    phrase_limit: int = int(os.getenv("DREX_PHRASE_LIMIT", "15"))


@dataclass
class AIConfig:
    default_provider: str = os.getenv("DEFAULT_AI", "gemini")
    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # Groq
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    # OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    # Cerebras
    cerebras_api_key: str = os.getenv("CEREBRAS_API_KEY", "")
    cerebras_model: str = os.getenv("CEREBRAS_MODEL", "llama3.3-70b")
    # General
    max_tokens: int = int(os.getenv("DREX_MAX_TOKENS", "1024"))
    temperature: float = float(os.getenv("DREX_TEMPERATURE", "0.7"))
    max_history: int = int(os.getenv("DREX_MAX_HISTORY", "20"))


@dataclass
class AppConfig:
    name: str = "DREX"
    version: str = "1.0.0"
    debug: bool = os.getenv("DREX_DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("DREX_LOG_LEVEL", "INFO")
    log_file: str = os.getenv("DREX_LOG_FILE", "logs/drex.log")
    db_path: str = os.getenv("DREX_DB_PATH", "data/drex_memory.db")
    wake_word: str = os.getenv("DREX_WAKE_WORD", "hey drex")
    wake_word_enabled: bool = os.getenv("DREX_WAKE_WORD_ENABLED", "false").lower() == "true"
    gui_enabled: bool = os.getenv("DREX_GUI_ENABLED", "true").lower() == "true"
    voice_enabled: bool = os.getenv("DREX_VOICE_ENABLED", "true").lower() == "true"
    theme: str = os.getenv("DREX_THEME", "dark")
    window_width: int = int(os.getenv("DREX_WIN_WIDTH", "1100"))
    window_height: int = int(os.getenv("DREX_WIN_HEIGHT", "700"))
    # Personality mode: jarvis | friendly | hacker | calm
    personality: str = os.getenv("DREX_PERSONALITY", "jarvis")


@dataclass
class DrexConfig:
    app: AppConfig = field(default_factory=AppConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    ai: AIConfig = field(default_factory=AIConfig)


# Singleton
_config: DrexConfig | None = None


def get_config() -> DrexConfig:
    global _config
    if _config is None:
        _config = DrexConfig()
    return _config