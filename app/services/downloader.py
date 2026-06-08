import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional

import yt_dlp

from app.config import get_settings
from app.models.schemas import VideoInfo, FormatInfo


def _build_format_info(fmt: dict) -> FormatInfo:
    vcodec = fmt.get("vcodec", "none")
    acodec = fmt.get("acodec", "none")
    return FormatInfo(
        format_id=fmt.get("format_id", ""),
        ext=fmt.get("ext", ""),
        resolution=fmt.get("resolution") or fmt.get("format_note"),
        fps=fmt.get("fps"),
        vcodec=vcodec if vcodec != "none" else None,
        acodec=acodec if acodec != "none" else None,
        filesize=fmt.get("filesize"),
        filesize_approx=fmt.get("filesize_approx"),
        tbr=fmt.get("tbr"),
        vbr=fmt.get("vbr"),
        abr=fmt.get("abr"),
        protocol=fmt.get("protocol"),
        format_note=fmt.get("format_note"),
        has_video=vcodec not in (None, "none"),
        has_audio=acodec not in (None, "none"),
    )


def _extract_info_sync(url: str) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _download_sync(url: str, format_spec: str, output_dir: str) -> tuple[str, str]:
    """Returns (filepath, title)."""
    session_id = uuid.uuid4().hex[:8]
    output_template = os.path.join(output_dir, f"{session_id}_%(title).100s.%(ext)s")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": format_spec,
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "postprocessors": [{"key": "FFmpegMetadata"}],
        "ffmpeg_location": get_settings().ffmpeg_path,
    }

    downloaded_path: list[str] = []

    def on_postprocessor_hook(d: dict) -> None:
        if d.get("status") == "finished":
            downloaded_path.append(d.get("info_dict", {}).get("filepath", ""))

    opts["postprocessor_hooks"] = [on_postprocessor_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown")

    # Use the hook-captured path first (most reliable after post-processing)
    if downloaded_path and os.path.exists(downloaded_path[-1]):
        return downloaded_path[-1], title

    # Fall back to guessing the filepath
    guessed = os.path.join(
        output_dir,
        f"{session_id}_{info.get('title', 'video')[:100]}.{info.get('ext', 'mp4')}",
    )
    if not os.path.exists(guessed):
        guessed = guessed.replace(f".{info.get('ext', 'mp4')}", ".mp4")

    # Last resort: scan dir for the session-prefixed file
    if not os.path.exists(guessed):
        for fname in os.listdir(output_dir):
            if fname.startswith(session_id):
                guessed = os.path.join(output_dir, fname)
                break

    return guessed, title


async def get_video_info(url: str) -> VideoInfo:
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _extract_info_sync, url)

    formats = [_build_format_info(f) for f in info.get("formats", [])]

    return VideoInfo(
        id=info.get("id", ""),
        title=info.get("title", ""),
        description=info.get("description"),
        uploader=info.get("uploader"),
        upload_date=info.get("upload_date"),
        duration=info.get("duration"),
        duration_string=info.get("duration_string"),
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        thumbnail=info.get("thumbnail"),
        webpage_url=info.get("webpage_url", url),
        extractor=info.get("extractor", ""),
        formats=formats,
        total_formats=len(formats),
    )


async def download_video(
    url: str,
    output_dir: str,
    format_id: Optional[str] = None,
    quality: str = "bestvideo+bestaudio/best",
) -> tuple[str, str]:
    """Returns (filepath, title). Runs blocking yt-dlp in a thread."""
    os.makedirs(output_dir, exist_ok=True)
    format_spec = format_id if format_id else quality

    loop = asyncio.get_event_loop()
    filepath, title = await loop.run_in_executor(
        None, _download_sync, url, format_spec, output_dir
    )
    return filepath, title
