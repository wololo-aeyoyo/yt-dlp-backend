import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
import yt_dlp.utils

from app import db
from app.auth import optional_user
from app.config import get_settings
from app.limiter import limiter
from app.models.schemas import (
    ConvertRequest,
    ConvertResponse,
    DownloadRequest,
    DownloadResponse,
    VideoInfo,
)
from app.services import converter, downloader, uploader

router = APIRouter(prefix="/api", tags=["Videos"])

_2GB = 2 * 1024 ** 3


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
@limiter.limit("30/minute")
async def get_info(
    request: Request,
    url: str = Query(..., description="Video URL to inspect"),
    user_id: int | None = Depends(optional_user),
):
    pool = request.app.state.db
    try:
        info = await downloader.get_video_info(url)
        await db.log_request(pool, url=url, action="info", success=True, user_id=user_id)
        return info
    except yt_dlp.utils.DownloadError as exc:
        await db.log_request(pool, url=url, action="info", success=False, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.log_request(pool, url=url, action="info", success=False, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/download", response_model=DownloadResponse, summary="Download a video")
@limiter.limit("10/minute")
async def download_video(
    request: Request,
    body: DownloadRequest,
    user_id: int | None = Depends(optional_user),
):
    settings = get_settings()
    pool = request.app.state.db
    filepath = None
    try:
        filepath, title = await downloader.download_video(
            url=body.url,
            output_dir=settings.download_dir,
            format_id=body.format_id,
            quality=body.quality,
        )

        file_size = os.path.getsize(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)

        if file_size > _2GB and user_id is None:
            await db.log_request(
                pool, url=body.url, action="download", success=False, title=title,
                file_size_bytes=file_size, error="auth required for files >2 GB",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to download files larger than 2 GB",
            )

        chibi = None
        if body.upload_to_chibisafe:
            chibi = await uploader.upload_to_chibisafe(filepath)

        await db.log_request(
            pool, url=body.url, action="download", success=True, title=title,
            file_size_bytes=file_size, chibisafe_url=chibi.url if chibi else None,
            user_id=user_id,
        )

        return DownloadResponse(
            success=True,
            title=title,
            filename=Path(filepath).name,
            file_size_bytes=file_size,
            file_size_human=_human_size(file_size),
            mime_type=mime_type,
            chibisafe=chibi,
        )
    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as exc:
        await db.log_request(pool, url=body.url, action="download", success=False, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.log_request(pool, url=body.url, action="download", success=False, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _cleanup(filepath)


@router.post("/convert", response_model=ConvertResponse, summary="Download video and convert to MP3")
@limiter.limit("10/minute")
async def convert_to_mp3(
    request: Request,
    body: ConvertRequest,
    user_id: int | None = Depends(optional_user),
):
    settings = get_settings()
    pool = request.app.state.db
    video_path = None
    mp3_path = None
    try:
        video_path, title = await downloader.download_video(
            url=body.url,
            output_dir=settings.download_dir,
            quality="bestaudio/best",
        )

        mp3_path = await converter.convert_to_mp3(video_path, body.audio_quality.value)
        file_size = os.path.getsize(mp3_path)

        if file_size > _2GB and user_id is None:
            await db.log_request(
                pool, url=body.url, action="convert", success=False, title=title,
                file_size_bytes=file_size, error="auth required for files >2 GB",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for files larger than 2 GB",
            )

        chibi = None
        if body.upload_to_chibisafe:
            chibi = await uploader.upload_to_chibisafe(mp3_path)

        await db.log_request(
            pool, url=body.url, action="convert", success=True, title=title,
            file_size_bytes=file_size, chibisafe_url=chibi.url if chibi else None,
            user_id=user_id,
        )

        return ConvertResponse(
            success=True,
            title=title,
            filename=Path(mp3_path).name,
            file_size_bytes=file_size,
            file_size_human=_human_size(file_size),
            audio_quality=body.audio_quality.value,
            chibisafe=chibi,
        )
    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as exc:
        await db.log_request(pool, url=body.url, action="convert", success=False, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.log_request(pool, url=body.url, action="convert", success=False, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _cleanup(video_path, mp3_path)
