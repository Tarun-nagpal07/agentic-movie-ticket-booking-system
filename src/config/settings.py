from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    
    DEBUG: bool = Field(default=False)
    API_KEY: str 
    OPENAI_API_KEY: str
    BASE_URL: str
    LLM_MODEL: str = Field(default="gpt-4o-mini")
    FIRST_FALLBACK_LLM :str = Field(default="openai/gpt-oss-120b")
    SECOND_FALLBACK_LLM :str = Field(default="meta-llama/Llama-3.1-70B-Instruct")
    REDIS_URL: str
    QDRANT_URL: str
    QDRANT_API: str = Field(default="")
    QDRANT_API_KEY: str = Field(default="")
    SUPABASE_DB_URL: str = Field(default="")
    OPENROUTER_API_KEY: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    HF_TOKEN: str = Field(default="")
    QDRANT_POLICY_COLLECTION: str = Field(default="policy_docs")
    LANGFUSE_SECRET_KEY: str = Field(default="")
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_BASE_URL: str = Field(default="https://cloud.langfuse.com")
    JWT_SECRET_KEY: str = Field(default="super-secret-key-change-in-production")
    SESSION_EXPIRE_MINUTES: int = Field(default=60)
    TMDB_API_KEY: str = Field(default="")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

