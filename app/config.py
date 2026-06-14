from pydantic_settings import BaseSettings
from functools import lru_cache
import imageio_ffmpeg


class Settings(BaseSettings):
    chibisafe_base_url: str
    chibisafe_api_key: str
    download_dir: str = "/tmp/yt-dlp-downloads"
    ffmpeg_path: str = imageio_ffmpeg.get_ffmpeg_exe()
    max_filesize_mb: int = 2000

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
