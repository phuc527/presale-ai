import time
import hmac
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request, Response, status
from backend.config import settings
from backend.database import get_db
from backend.security.crypto import generate_token, hash_session_token

SESSION_COOKIE_NAME = "presales_session"
CSRF_COOKIE_NAME = "presales_csrf"


class SlidingWindowRateLimiter:
    """Protects authentication and sensitive endpoints against brute-force attacks."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        recent = [t for t in self._hits[key] if t > cutoff]
        if len(recent) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau 60 giây.",
            )
        recent.append(now)
        self._hits[key] = recent


auth_rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
api_rate_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60)


def create_user_session(response: Response, user_id: int, request: Request) -> str:
    raw_token = generate_token(32)
    csrf_token = generate_token(24)
    token_hash = hash_session_token(raw_token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)).isoformat()
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = (request.headers.get("user-agent") or "")[:200]

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (user_id, token_hash, csrf_token, ip_address, user_agent, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, token_hash, csrf_token, client_ip, user_agent, expires_at),
        )

    is_https = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=is_https,
        samesite="strict",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=is_https,
        samesite="strict",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return csrf_token


def clear_user_session(request: Request, response: Response) -> None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if raw_token:
        token_hash = hash_session_token(raw_token)
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def get_current_user(request: Request) -> dict:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập phiên làm việc.")

    token_hash = hash_session_token(raw_token)
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.full_name, u.role, u.is_active, s.csrf_token, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ.")
        if row["expires_at"] < now_iso or not row["is_active"]:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn.")

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        header_csrf = request.headers.get("x-csrf-token", "")
        if not header_csrf or not hmac.compare_digest(header_csrf, row["csrf_token"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Xác thực CSRF không hợp lệ.")

    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "csrf_token": row["csrf_token"],
    }


def require_admin(user: dict) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yêu cầu quyền Quản trị viên (Admin).")
    return user
