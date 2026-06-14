from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.limiter import limiter
from app.routers import health, videos

app = FastAPI(
    openapi_tags=[
        {"name": "Videos", "description": "Download, inspect, and convert videos"},
        {"name": "Health", "description": "Service health check"},
    ],
    title="yt-dlp Backend",
    description="""
## yt-dlp FastAPI Backend

A backend service for downloading videos, extracting audio, and uploading to Chibisafe.

### yt-dlp Capabilities
- **Thousands of supported sites**: YouTube, Vimeo, Twitch, Twitter/X, TikTok, Reddit, SoundCloud, and [many more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- **Format selection**: Choose specific video/audio streams by format ID or quality string
- **Quality control**: `bestvideo+bestaudio`, `worst`, `bestvideo[height<=1080]`, etc.
- **Metadata extraction**: title, description, uploader, duration, view/like counts, thumbnails
- **Post-processing**: merge streams, embed metadata/thumbnails/subtitles
- **Rate limiting**: control download speed to avoid throttling
- **Subtitle download**: extract and embed subtitles in many formats (SRT, VTT, ASS)
- **Authentication**: cookies, username/password, browser cookie import
- **Playlist support**: download entire playlists with ordering and filtering
- **Fragment/HLS/DASH**: supports adaptive streaming formats
- **SponsorBlock**: automatically skip/mark sponsored segments (YouTube)
- **Geo-bypass**: built-in support for circumventing geo-restrictions
- **Chapter splitting**: split output files by video chapters
- **Thumbnail conversion**: download and convert thumbnails
- **Output templates**: powerful filename templating with metadata fields
- **Concurrent fragments**: parallel fragment downloads for speed (`-N`)
- **Retry logic**: configurable retries for network failures
- **Archive file**: skip already-downloaded videos
- **Audio extraction**: extract audio-only streams
- **Custom post-processing commands**: run arbitrary shell commands after download

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/info` | Get video metadata + all available formats |
| POST | `/api/download` | Download video (optionally upload to Chibisafe) |
| POST | `/api/convert` | Download + convert to MP3 (optionally upload to Chibisafe) |
| GET | `/api/health` | Service health check |
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(videos.router)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "yt-dlp backend — visit /docs for API reference"}
