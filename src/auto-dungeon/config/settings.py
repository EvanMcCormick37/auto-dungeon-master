from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Paths
    data_dir: Path = Path("data")
    content_dir: Path = Path("content")
    
    # LLM Settings
    ollama_host: str = "http://localhost:11434"
    router_model: str = "gemma2:2b"
    answerer_model: str = "mistral:7b"
    
    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # Game Settings
    dm_style: str = "classic"
    difficulty: str = "normal"
    
    class Config:
        env_file = ".env"
        env_prefix = "DND_"

settings = Settings()