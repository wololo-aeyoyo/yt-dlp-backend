from functools import lru_cache
from typing import Optional

import imageio_ffmpeg
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    chibisafe_base_url: str
    chibisafe_api_key: str
    download_dir: str = "/tmp/yt-dlp-downloads"
    ffmpeg_path: str = imageio_ffmpeg.get_ffmpeg_exe()
    max_filesize_mb: int = 2000

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "postgres"
    pg_password: str = ""
    pg_database: str = "ytdlp"

    # JWT
    jwt_secret: str
    jwt_expire_hours: int = 24

    # Observability
    environment: str = "production"
    json_logs: bool = True
    loki_url: Optional[str] = None
    otel_endpoint: Optional[str] = None
    mimir_url: Optional[str] = None
    pyroscope_url: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
