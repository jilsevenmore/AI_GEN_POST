from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "AI Blog & Social Post Generator"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_gen_post"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OpenRouter (Free models)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_FREE_MODELS: List[str] = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-2-9b-it:free",
    ]
    OPENROUTER_FREE_ROUTER: str = "openrouter/free"
    OPENROUTER_DAILY_LIMIT: int = 50
    OPENROUTER_RATE_LIMIT_RPM: int = 20

    # OpenAI (Fallback / image generation)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_FALLBACK_ENABLED: bool = True

    # Hugging Face (Inference Providers / Hub)
    HF_TOKEN: Optional[str] = None
    HF_BASE_URL: str = "https://router.huggingface.co/v1"
    HF_PROMPT_MODEL: str = "MiniMaxAI/MiniMax-M2.7"

    # MiniMax (Prompt enhancement via Hugging Face by default; configurable)
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_BASE_URL: str = "https://router.huggingface.co/v1"
    MINIMAX_MODEL: str = "MiniMaxAI/MiniMax-M2.7"
    MINIMAX_PROMPT_ENHANCE_ENABLED: bool = True

    # Ollama (Local, free prompt enhancement)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: Optional[str] = None  # e.g. qwen2.5:3b-instruct
    OLLAMA_PROMPT_ENHANCE_ENABLED: bool = False

    # GPT Image 2.5 Sunburst
    SUNBURST_API_KEY: Optional[str] = None
    SUNBURST_BASE_URL: str = "https://api.openai.com/v1"
    SUNBURST_MODEL: str = "gpt-image-2.5-sunburst"

    # Embeddings (semantic search, Hugging Face)
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 768
    EMBEDDING_DEVICE: str = "cpu"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    CLOUDINARY_UPLOAD_PRESET: str = "ai_gen_post"
    CLOUDINARY_FOLDER_LIBRARY: str = "library"
    CLOUDINARY_FOLDER_PUBLISHED: str = "published"
    CLOUDINARY_FOLDER_DRAFTS: str = "drafts"
    CLOUDINARY_CREDITS_ALERT_THRESHOLD: float = 0.7  # 70%

    # Buffer
    BUFFER_CLIENT_ID: Optional[str] = None
    BUFFER_CLIENT_SECRET: Optional[str] = None
    BUFFER_REDIRECT_URI: str = "http://localhost:5173/auth/buffer/callback"
    BUFFER_API_BASE: str = "https://api.bufferapp.com/1"
    BUFFER_RATE_LIMIT_RPM: int = 100  # per 15 min per app

    # Django CRM Integration (Step 4)
    DJANGO_CRM_API_URL: Optional[str] = None
    DJANGO_CRM_AUTH_TOKEN: Optional[str] = None

    # Advertising Pixels (Step 5)
    META_PIXEL_ID: Optional[str] = None
    GOOGLE_MEASUREMENT_ID: Optional[str] = None

    # LangSmith
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "ai-gen-post"
    LANGSMITH_TRACING: bool = True

    # Quotas
    DAILY_FREE_REQUESTS_PER_USER: int = 12
    DAILY_SPEND_CAP_USD: float = 10.0
    MAX_REGENERATIONS_PER_JOB: int = 3

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Feature flags
    ENABLE_IMAGE_LIBRARY: bool = True
    ENABLE_BRAND_KIT: bool = True
    ENABLE_BUFFER_PUBLISHING: bool = True
    ENABLE_FREE_MODELS_FIRST: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()