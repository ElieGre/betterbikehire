import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    TFL_BASE_URL: str = "https://api.tfl.gov.uk"
    TFL_APP_ID: str | None = os.getenv("TFL_APP_ID")
    TFL_APP_KEY: str | None = os.getenv("TFL_APP_KEY")
    # scoring tunables
    DEST_STATION_RADIUS_M: int = int(os.getenv("DEST_STATION_RADIUS_M", "450"))
    ORIGIN_SEARCH_RADIUS_M: int = int(os.getenv("ORIGIN_SEARCH_RADIUS_M", "800"))


settings = Settings()
