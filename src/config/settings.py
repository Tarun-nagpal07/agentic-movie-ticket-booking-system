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
    REDIS_URL: str
    QDRANT_URL: str

    QDRANT_POLICY_COLLECTION: str = Field(default="policy_docs")
    QDRANT_MEMORY_COLLECTION: str = Field(default="session_memory")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

