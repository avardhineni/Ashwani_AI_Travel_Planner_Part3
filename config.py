"""All configuration is read from environment variables; no secrets in source."""
import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '').strip()
AVIATION_STACK_API_KEY = os.getenv('AVIATION_STACK_API_KEY', '').strip()
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '').strip()
AVIATION_MCP_PYTHON = os.getenv('AVIATION_MCP_PYTHON', '').strip()
AVIATION_MCP_DIR = os.getenv('AVIATION_MCP_DIR', '').strip()

@lru_cache(maxsize=1)
def get_llm():
    """Instantiate only when a node actually needs to contact Groq."""
    from langchain_groq import ChatGroq
    if not os.getenv('GROQ_API_KEY'):
        raise RuntimeError('GROQ_API_KEY is missing from .env')
    return ChatGroq(model=GROQ_MODEL, temperature=0, max_retries=2, timeout=60)
