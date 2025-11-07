"""Configuration settings for Semantix."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Voting thresholds
    VOTE_THRESHOLD: int = 3
    QUALITY_MIN: int = 1

    # Directories
    INPUT_DIR: Path = Path("/data/input")
    ARTIFACTS_DIR: Path = Path("./artifacts")

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080

    # Training
    TRAINING_MODE: str = "offline"  # "offline" or "online"
    TRAINING_CHUNK_SIZE: int = 100_000

    # Auto-labeling
    AUTO_LABEL_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2"
    LLM_PROVIDER: str = "ollama"  # "ollama" or "openai"

    # Limits
    MAX_TEXT_LENGTH: int = 1_000_000  # ~1MB
    MAX_FILE_SIZE_MB: int = 50

    # WebSocket
    WS_SEND_TIMEOUT: float = 0.25  # seconds

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.INPUT_DIR = Path(self.INPUT_DIR)
        self.ARTIFACTS_DIR = Path(self.ARTIFACTS_DIR)
        self.INPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()

