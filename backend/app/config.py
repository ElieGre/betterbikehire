from dotenv import load_dotenv
from pydantic import BaseSettings

# load .env from project root if present
load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str | None = None
    TFL_API_KEY: str | None = None
    MAPBOX_API_KEY: str | None = None

    class Config:
        env_file = ".env"  # fall back to local file if not already loaded


settings = Settings()
