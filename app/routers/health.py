import shutil
from fastapi import APIRouter
import yt_dlp
import imageio_ffmpeg

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
async def health():
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    disk = shutil.disk_usage("/tmp")
    return {
        "status": "ok",
        "yt_dlp_version": yt_dlp.version.__version__,
        "ffmpeg": ffmpeg_path,
        "disk_free_gb": round(disk.free / 1024**3, 2),
    }
