from typing import List,Dict
from langchain_openai import ChatOpenAI
from app.core.config import config as settings
from langchain_groq import ChatGroq


llm_models : List[Dict] = [
    {
        "name": settings.LLAMA_MODEL_NAME,
        "llm" : ChatOpenAI(
            model=settings.LLAMA_MODEL_NAME,
            api_key=settings.LLAMA_API_KEY,
            base_url=settings.LLAMA_BASE_URL,
            temperature = settings.DEFAULT_TEMPERATURE
        ),
        "provider":"meta"
    },
    {
        "name": "openai/gpt-oss-120b",
        "llm" : ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=settings.GROQ_API_KEY,
            temperature = settings.DEFAULT_TEMPERATURE,
            timeout=60,
            max_retries=2,
        ),
        "provider":"groq"
    }
]