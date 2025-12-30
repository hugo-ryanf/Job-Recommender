from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # DB
    database_url: str = "postgresql://user:password@localhost:5432/job_recommender"

    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 8001

    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    default_n_results: int = 10

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
