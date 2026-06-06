from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # AZURE_OPENAI_API_KEY: str
    # AZURE_OPENAI_ENDPOINT: str
    # AZURE_OPENAI_DEPLOYMENT_NAME: str
    # AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str
    # AZURE_OPENAI_API_VERSION: str
    
    DEBUG: bool = Field(default=False)
    API_KEY: str 
    OPENAI_API_KEY: str
    BASE_URL: str
    LLM_MODEL: str = Field(default="gpt-4o-mini")
    FIRST_FALLBACK_LLM :str = Field(default="meta-llama/Llama-3.1-70B-Instruct")
    REDIS_URL: str
    QDRANT_URL: str
    SUPABASE_DB_URL: str = Field(default="")
    OPENROUTER_API_KEY: str = Field(default="")
    HF_TOKEN: str = Field(default="")
    QDRANT_POLICY_COLLECTION: str = Field(default="policy_docs")
    QDRANT_MEMORY_COLLECTION: str = Field(default="session_memory")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

