from fastapi import APIRouter, Depends, HTTPException, Request

from app import auth as auth_utils
from app.limiter import limiter
from app.models.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, summary="Create a new account")
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest):
    pool = request.app.state.db
    async with pool.acquire() as conn:
        if await conn.fetchrow("SELECT 1 FROM users WHERE username=$1", body.username):
            raise HTTPException(status_code=409, detail="Username already taken")
        row = await conn.fetchrow(
            "INSERT INTO users(username, password_hash) VALUES($1,$2) RETURNING id",
            body.username,
            auth_utils.hash_password(body.password),
        )
    return TokenResponse(access_token=auth_utils.create_token(row["id"]))


@router.post("/login", response_model=TokenResponse, summary="Obtain a JWT token")
@limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest):
    pool = request.app.state.db
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE username=$1", body.username
        )
    if not row or not auth_utils.verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=auth_utils.create_token(row["id"]))


@router.get("/me", summary="Get current user info")
async def me(request: Request, user_id: int = Depends(auth_utils.require_user)):
    pool = request.app.state.db
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, created_at FROM users WHERE id=$1", user_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}
