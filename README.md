# yt-dlp Backend

A FastAPI backend that downloads videos via yt-dlp, converts audio to MP3 with ffmpeg, and uploads files to a Chibisafe instance backed by S3.

## Requirements

- Python 3.10+
- `pip3 install -r requirements.txt`

ffmpeg is bundled via `imageio-ffmpeg` — no system install required.

## Running

Run from the **project root**:

```bash
uvicorn main:app --reload
```

API docs available at `http://localhost:8000/docs`.

## Configuration

Copy `.env.example` to `.env` and edit as needed:

```env
CHIBISAFE_BASE_URL=https://your-chibisafe-instance.com
CHIBISAFE_API_KEY=your_api_key
DOWNLOAD_DIR=/tmp/yt-dlp-downloads
MAX_FILESIZE_MB=2000
```

All fields have defaults — the server works out of the box without a `.env`.

## API

### `GET /api/info`

Returns video metadata and every available format with codec, resolution, filesize, and bitrate details.

```
GET /api/info?url=https://www.youtube.com/watch?v=...
```

**Response fields of note:**
- `formats[].format_id` — pass this to `/api/download` for exact format selection
- `formats[].filesize` / `filesize_approx` — size in bytes
- `formats[].has_video` / `has_audio` — whether the stream carries video/audio

---

### `POST /api/download`

Downloads a video. Optionally uploads the result to Chibisafe.

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "format_id": "137+140",
  "quality": "bestvideo+bestaudio/best",
  "upload_to_chibisafe": false
}
```

- `format_id` takes priority over `quality` when both are provided.
- `quality` accepts any yt-dlp format string: `bestvideo[height<=1080]+bestaudio`, `worst`, etc.
- Output is always remuxed to MP4 with the `moov` atom at the front (required for Telegram previews and in-browser playback).

**Response:**
```json
{
  "success": true,
  "title": "Video title",
  "filename": "abc12345_Video title.mp4",
  "file_size_bytes": 12345678,
  "file_size_human": "11.8 MB",
  "mime_type": "video/mp4",
  "chibisafe": {
    "url": "https://...",
    "name": "xYz123.mp4",
    "uuid": "..."
  }
}
```

`chibisafe` is `null` when `upload_to_chibisafe` is `false`.

---

### `POST /api/convert`

Downloads the best available audio stream and converts it to MP3.

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "audio_quality": "192k",
  "upload_to_chibisafe": false
}
```

`audio_quality` options: `96k` | `128k` | `192k` (default) | `320k`

---

### `GET /api/health`

Returns yt-dlp version, ffmpeg binary path, and available disk space.

## Rate limits

Per IP, per minute:

| Endpoint | Limit |
|---|---|
| `GET /api/info` | 30/min |
| `POST /api/download` | 10/min |
| `POST /api/convert` | 10/min |

Exceeding a limit returns `429 Too Many Requests` with a `Retry-After` header.

## Supported sites

Anything yt-dlp supports — YouTube, Twitch, TikTok, Twitter/X, Vimeo, Reddit, SoundCloud, and [thousands more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).
