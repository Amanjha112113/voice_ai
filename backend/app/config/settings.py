from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Configuration settings for EchoDrive."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Environment
    APP_NAME: str = "EchoDrive Realtime Voice Agent"
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Agora Credentials
    AGORA_APP_ID: str = Field(default="test_agora_app_id_32_chars_long___", description="Agora App ID")
    AGORA_APP_CERTIFICATE: Optional[str] = Field(default=None, description="Agora App Certificate")
    AGORA_TOKEN_EXPIRY_SECONDS: int = 3600

    # AI Provider Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API Key")
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    DEEPGRAM_API_KEY: Optional[str] = Field(default=None, description="Deepgram API Key")
    CARTESIA_API_KEY: Optional[str] = Field(default=None, description="Cartesia API Key")
    CARTESIA_VOICE_ID: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None, description="ElevenLabs API Key")
    ELEVENLABS_VOICE_ID: Optional[str] = Field(default="oO7sLA3dWfQXsKeSAjpA", description="ElevenLabs Voice ID")

    # Latency & VAD Configuration
    VAD_SAMPLE_RATE: int = 16000
    VAD_FRAME_MS: int = 20  # 20ms audio frame chunks (640 bytes)
    VAD_ENERGY_THRESHOLD: float = 0.02
    VAD_PREFIX_PADDING_MS: int = 60   # Fast onset speech detection
    VAD_SILENCE_DURATION_MS: int = 400 # Trailing silence threshold for turn end

    # Buffer & Queue Limits
    AUDIO_INPUT_QUEUE_MAXSIZE: int = 100
    AUDIO_OUTPUT_QUEUE_MAXSIZE: int = 50
    TOKEN_STREAM_QUEUE_MAXSIZE: int = 200

    # Targets for Latency (ms)
    TARGET_TTFA_MS: float = 700.0
    TARGET_INTERRUPTION_STOP_MS: float = 200.0


settings = Settings()








