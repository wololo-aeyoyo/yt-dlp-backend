from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode(token: str) -> int:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        return int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> int | None:
    """Returns user_id if a valid Bearer token is present, None if no token. Raises 401 for bad tokens."""
    return _decode(credentials.credentials) if credentials else None


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> int:
    """Raises 401 if no valid Bearer token is present."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    return _decode(credentials.credentials)
