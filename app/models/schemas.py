from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from enum import Enum


class AudioQuality(str, Enum):
    low = "96k"
    medium = "128k"
    high = "192k"
    best = "320k"


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = None
    fps: Optional[float] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    tbr: Optional[float] = None
    vbr: Optional[float] = None
    abr: Optional[float] = None
    protocol: Optional[str] = None
    format_note: Optional[str] = None
    has_video: bool = False
    has_audio: bool = False


class VideoInfo(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    duration: Optional[float] = None
    duration_string: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    thumbnail: Optional[str] = None
    webpage_url: str
    extractor: str
    formats: list[FormatInfo]
    total_formats: int


class DownloadRequest(BaseModel):
    url: str
    format_id: Optional[str] = None
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()


class ChibisafeUpload(BaseModel):
    url: str
    name: str
    uuid: str


class DownloadResponse(BaseModel):
    success: bool
    title: str
    filename: str
    file_size_bytes: int
    file_size_human: str
    mime_type: Optional[str] = None
    chibisafe: ChibisafeUpload


class ConvertRequest(BaseModel):
    url: str
    audio_quality: AudioQuality = AudioQuality.high

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()


class ConvertResponse(BaseModel):
    success: bool
    title: str
    filename: str
    file_size_bytes: int
    file_size_human: str
    audio_quality: str
    chibisafe: ChibisafeUpload


class ErrorResponse(BaseModel):
    detail: str


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
