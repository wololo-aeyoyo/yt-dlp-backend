# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the server

Always run from the **project root** (`/home/wololo/code/yt-dlp-backend/`), never from inside `app/`:

```bash
uvicorn main:app --reload        # development
python3 main.py                  # alternative
uvicorn app.main:app --reload    # explicit form
```

`main.py` at the root re-exports `app` from `app/main.py` to keep absolute imports working.

API docs: http://localhost:8000/docs

## Installing dependencies

```bash
pip3 install -r requirements.txt
```

ffmpeg is provided by `imageio-ffmpeg` (bundled binary) — no system install needed. The path is resolved at startup via `imageio_ffmpeg.get_ffmpeg_exe()`.

## Configuration

Settings live in `app/config.py` as a `pydantic-settings` `BaseSettings` class. All fields can be overridden via environment variables or a `.env` file. The `get_settings()` function is `@lru_cache`'d — call it anywhere, it's cheap.

Key settings: `CHIBISAFE_BASE_URL`, `CHIBISAFE_API_KEY`, `DOWNLOAD_DIR`, `MAX_FILESIZE_MB`.

## Architecture

```
app/
  main.py         — FastAPI app, CORS middleware, rate limit exception handler
  limiter.py      — slowapi Limiter singleton (imported by routers to avoid circular import)
  config.py       — Settings singleton
  models/
    schemas.py    — All Pydantic request/response models
  routers/
    videos.py     — /api/info, /api/download, /api/convert
    health.py     — /api/health
  services/
    downloader.py — yt-dlp wrapper (blocking calls run in executor)
    converter.py  — ffmpeg MP3 conversion via subprocess
    uploader.py   — chibisafe upload (3-step S3 flow)
```

The routers own request validation and cleanup; the services contain no FastAPI dependencies and are purely functional.

## Key implementation details

**yt-dlp is blocking** — all `YoutubeDL` calls run in `asyncio.get_event_loop().run_in_executor(None, ...)`. Never call them directly in an async function.

**Downloaded files are cleaned up** in `finally` blocks in the router after the response is built (or after upload to chibisafe). The temp dir is `DOWNLOAD_DIR` (default `/tmp/yt-dlp-downloads`).

**MP4 faststart** — after every yt-dlp download that produces `.mp4`, `_faststart()` in `downloader.py` remuxes with `-movflags +faststart` so the `moov` atom is at the front of the file. This is required for Telegram and other clients to show video previews. Skip this only for audio-only formats.

**Chibisafe upload is 3 steps** (the instance uses S3 network storage, `useNetworkStorage: true`):
1. `POST /api/upload` with JSON `{name, size, contentType}` → returns `{url (S3 presigned), identifier}`
2. `PUT` file bytes directly to the S3 presigned URL
3. `POST /api/upload/process` with `{identifier, name, type}` → returns `{name, uuid, url}`

Do not attempt a multipart form upload — it will 500.

## Rate limits

Applied per IP via `slowapi`:
- `GET /api/info` — 30/minute
- `POST /api/download` — 10/minute  
- `POST /api/convert` — 10/minute

The `limiter` instance lives in `app/limiter.py` (not `app/main.py`) specifically to avoid a circular import since `main.py` imports the routers which need the limiter.
