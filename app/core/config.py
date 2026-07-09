from pydantic_settings import BaseSettings,SettingsConfigDict
import os
from functools import lru_cache

class Config (BaseSettings):
    """Application configuration settings."""
    model_config = SettingsConfigDict(env_file=".env")
    VERSION_PREFIX: str 
    VERSION : str 
    ENVIRONMENT: str = "development"
    HOST: str 
    PORT: int 
    USER_NAME: str
    DATABASE: str
    PASSWORD: str
    SECRET_KEY: str 
    ALGORITHM : str 
    LLAMA_MODEL_NAME: str
    LLAMA_API_KEY: str
    LLAMA_BASE_URL: str 
    GOOGLE_MODEL_NAME: str
    GOOGLE_API_KEY: str
    MAX_RETRY_ATTEMPTS: int
    RETRY_DELAYS: int
    DEFAULT_TEMPERATURE : float
    DIALECT: str
    DEFAULT_LLM_MODEL:str
    CHECKPOINTER_TYPE: str
    REDIS_URI: str
    POSTGRES_URI: str
    LANGSMITH_TRACING: str
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str
    OPENROUTER_API_KEY: str
    GROQ_API_KEY: str
    RAG_SERVICE: str
    RAG_SERVICE_TOKEN: str
    S3_BUCKET_NAME: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    AWS_S3_SOURCE_PATH: str
    

#@lru_cache
def get_config():
    try:
        settings = Config()
        os.environ["LANGSMITH_TRACING"] = settings.LANGSMITH_TRACING
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY
        return settings
    except Exception as e:
        raise Exception(f"Error loading settings: {e}")
    
config = get_config()