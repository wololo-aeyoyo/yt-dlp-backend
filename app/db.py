import asyncpg
from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS video_requests (
    id                    SERIAL PRIMARY KEY,
    url                   TEXT NOT NULL,
    title                 TEXT,
    action                TEXT NOT NULL,
    success               BOOLEAN NOT NULL,
    error                 TEXT,
    file_size_bytes       BIGINT,
    uploaded_to_chibisafe BOOLEAN DEFAULT FALSE,
    chibisafe_url         TEXT,
    user_id               INTEGER REFERENCES users(id),
    requested_at          TIMESTAMPTZ DEFAULT NOW()
);
"""


async def create_pool() -> asyncpg.Pool:
    s = get_settings()
    pool = await asyncpg.create_pool(
        host=s.pg_host,
        port=s.pg_port,
        user=s.pg_user,
        password=s.pg_password,
        database=s.pg_database,
    )
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA)
    return pool


async def log_request(
    pool: asyncpg.Pool,
    *,
    url: str,
    action: str,
    success: bool,
    title: str | None = None,
    error: str | None = None,
    file_size_bytes: int | None = None,
    chibisafe_url: str | None = None,
    user_id: int | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO video_requests
               (url, title, action, success, error, file_size_bytes,
                uploaded_to_chibisafe, chibisafe_url, user_id)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            url, title, action, success, error, file_size_bytes,
            chibisafe_url is not None, chibisafe_url, user_id,
        )
