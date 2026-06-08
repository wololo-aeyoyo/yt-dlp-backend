import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
import yt_dlp.utils

from app.config import get_settings
from app.models.schemas import (
    ConvertRequest,
    ConvertResponse,
    DownloadRequest,
    DownloadResponse,
    VideoInfo,
)
from app.services import converter, downloader, uploader

router = APIRouter(prefix="/api", tags=["Videos"])


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def _cleanup(*paths: str | None) -> None:
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


@router.get("/info", response_model=VideoInfo, summary="Get video metadata and available formats")
async def get_info(url: str = Query(..., description="Video URL to inspect")):
    """
    Returns full video metadata including all available formats with their
    codec, resolution, filesize, and bitrate details.
    """
    try:
        return await downloader.get_video_info(url)
    except yt_dlp.utils.DownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/download", response_model=DownloadResponse, summary="Download a video")
async def download_video(request: DownloadRequest):
    """
    Downloads a video in the requested format/quality.

    - **format_id**: specific format ID from `/api/info` (e.g. `137+140`)
    - **quality**: yt-dlp format string (default: `bestvideo+bestaudio/best`)
    - **upload_to_chibisafe**: upload the file to chibisafe after download
    """
    settings = get_settings()
    filepath = None
    try:
        filepath, title = await downloader.download_video(
            url=request.url,
            output_dir=settings.download_dir,
            format_id=request.format_id,
            quality=request.quality,
        )

        file_size = os.path.getsize(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)

        chibi = None
        if request.upload_to_chibisafe:
            chibi = await uploader.upload_to_chibisafe(filepath)

        return DownloadResponse(
            success=True,
            title=title,
            filename=Path(filepath).name,
            file_size_bytes=file_size,
            file_size_human=_human_size(file_size),
            mime_type=mime_type,
            chibisafe=chibi,
        )
    except yt_dlp.utils.DownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _cleanup(filepath)


@router.post("/convert", response_model=ConvertResponse, summary="Download video and convert to MP3")
async def convert_to_mp3(request: ConvertRequest):
    """
    Downloads the audio from a video URL and converts it to MP3.

    - **audio_quality**: `96k` | `128k` | `192k` (default) | `320k`
    - **upload_to_chibisafe**: upload the MP3 to chibisafe after conversion
    """
    settings = get_settings()
    video_path = None
    mp3_path = None
    try:
        video_path, title = await downloader.download_video(
            url=request.url,
            output_dir=settings.download_dir,
            quality="bestaudio/best",
        )

        mp3_path = await converter.convert_to_mp3(video_path, request.audio_quality.value)

        file_size = os.path.getsize(mp3_path)

        chibi = None
        if request.upload_to_chibisafe:
            chibi = await uploader.upload_to_chibisafe(mp3_path)

        return ConvertResponse(
            success=True,
            title=title,
            filename=Path(mp3_path).name,
            file_size_bytes=file_size,
            file_size_human=_human_size(file_size),
            audio_quality=request.audio_quality.value,
            chibisafe=chibi,
        )
    except yt_dlp.utils.DownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _cleanup(video_path, mp3_path)
