from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# litellm reads provider API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) from
# os.environ directly, so the .env file must be loaded into the process
# environment, not just into Settings.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://agentic:agentic@localhost:5432/agentic_life"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "text-embedding-3-small"
    judge_model: str = "openai/gpt-4o-mini"
    tick_seconds: float = 6.0
    personas_dir: str = "personas"
    constitution_path: str = "config/constitution.yaml"
    world_path: str = "config/world.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
