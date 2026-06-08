import asyncio
import subprocess
from pathlib import Path

from app.config import get_settings


def _convert_sync(input_path: str, output_path: str, audio_quality: str) -> str:
    ffmpeg = get_settings().ffmpeg_path
    cmd = [
        ffmpeg,
        "-i", input_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", audio_quality,
        "-y",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
    return output_path


async def convert_to_mp3(input_path: str, audio_quality: str = "192k") -> str:
    output_path = str(Path(input_path).with_suffix(".mp3"))
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _convert_sync, input_path, output_path, audio_quality)
    return output_path
