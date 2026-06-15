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

    # Observability
    environment: str = "production"
    json_logs: bool = True

    # Loki — set to ship logs, e.g. http://localhost:3100
    loki_url: Optional[str] = None

    # Tempo — OTLP HTTP endpoint, e.g. http://localhost:4318
    otel_endpoint: Optional[str] = None

    # Mimir — exposes /metrics for Prometheus scrape; set False to disable
    prometheus_enabled: bool = True

    # Pyroscope — set to enable continuous profiling, e.g. http://localhost:4040
    pyroscope_url: Optional[str] = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
