import mimetypes
import os
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.schemas import ChibisafeUpload


async def upload_to_chibisafe(file_path: str) -> ChibisafeUpload:
    """
    Three-step upload for chibisafe S3 network storage mode:
    1. POST /api/upload (JSON) → pre-signed S3 URL + identifier
    2. PUT file binary to S3 pre-signed URL
    3. POST /api/upload/process → confirm and register file in chibisafe DB
    """
    settings = get_settings()
    path = Path(file_path)
    file_size = os.path.getsize(file_path)

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    headers = {
        "x-api-key": settings.chibisafe_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Step 1: request pre-signed S3 URL
        resp1 = await client.post(
            f"{settings.chibisafe_base_url}/api/upload",
            headers=headers,
            json={"name": path.name, "size": file_size, "contentType": mime_type},
        )
        if resp1.status_code != 200:
            raise RuntimeError(
                f"Chibisafe presign failed [{resp1.status_code}]: {resp1.text}"
            )

        presign_data = resp1.json()
        s3_url = presign_data["url"]
        identifier = presign_data["identifier"]

        # Step 2: PUT file directly to S3 (read all bytes to avoid sync-read issue)
        file_bytes = Path(file_path).read_bytes()
        resp2 = await client.put(
            s3_url,
            content=file_bytes,
            headers={"Content-Type": mime_type, "Content-Length": str(file_size)},
        )
        if resp2.status_code not in (200, 204):
            raise RuntimeError(
                f"S3 upload failed [{resp2.status_code}]: {resp2.text}"
            )

        # Step 3: confirm upload with chibisafe
        resp3 = await client.post(
            f"{settings.chibisafe_base_url}/api/upload/process",
            headers=headers,
            json={"identifier": identifier, "name": path.name, "type": mime_type},
        )
        if resp3.status_code not in (200, 201):
            raise RuntimeError(
                f"Chibisafe process failed [{resp3.status_code}]: {resp3.text}"
            )

        data = resp3.json()
        return ChibisafeUpload(
            url=data.get("url", ""),
            name=data.get("name", path.name),
            uuid=data.get("uuid", ""),
        )
