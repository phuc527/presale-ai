from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from backend.database import get_db
from backend.models.schemas import ChangePasswordRequest, LoginRequest, SetupOrRegisterRequest
from backend.security.auth import (
    auth_rate_limiter,
    clear_user_session,
    create_user_session,
    get_current_user,
    require_admin,
)
from backend.security.crypto import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/status")
def auth_status(request: Request):
    with get_db() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    try:
        user = get_current_user(request)
        return {"initialized": user_count > 0, "authenticated": True, "user": user}
    except HTTPException:
        return {"initialized": user_count > 0, "authenticated": False, "user": None}


@router.post("/setup")
def initial_admin_setup(payload: SetupOrRegisterRequest, request: Request, response: Response):
    """Creates the very first Admin account on a fresh local installation (no hardcoded default password)."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    auth_rate_limiter.check(f"setup:{client_ip}")

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hệ thống đã có tài khoản Quản trị viên. Vui lòng đăng nhập hoặc nhờ Admin tạo tài khoản mới.",
            )
        pw_hash = hash_password(payload.password)
        cur = conn.execute(
            "INSERT INTO users (username, full_name, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 'admin', 1, ?) RETURNING id",
            (payload.username.lower(), payload.full_name.strip(), pw_hash, now_iso),
        )
        user_id = cur.fetchone()["id"]

    csrf_token = create_user_session(response, user_id, request)
    return {
        "message": "Khởi tạo tài khoản Quản trị viên thành công.",
        "user": {
            "id": user_id,
            "username": payload.username.lower(),
            "full_name": payload.full_name.strip(),
            "role": "admin",
            "csrf_token": csrf_token,
        },
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "127.0.0.1"
    auth_rate_limiter.check(f"login:{client_ip}:{payload.username.lower()}")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, full_name, password_hash, role, is_active FROM users WHERE username = ?",
            (payload.username.lower(),),
        ).fetchone()

    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
    if not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị vô hiệu hóa.")

    csrf_token = create_user_session(response, row["id"], request)
    return {
        "message": "Đăng nhập thành công.",
        "user": {
            "id": row["id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
            "csrf_token": csrf_token,
        },
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    clear_user_session(request, response)
    return {"message": "Đã đăng xuất an toàn."}


@router.get("/users")
def list_users(user: dict = Depends(get_current_user)):
    require_admin(user)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id ASC"
        ).fetchall()
    return {"users": [dict(r) for r in rows]}


@router.post("/users")
def create_user(payload: SetupOrRegisterRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        exists = conn.execute("SELECT id FROM users WHERE username = ?", (payload.username.lower(),)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại.")
        pw_hash = hash_password(payload.password)
        conn.execute(
            "INSERT INTO users (username, full_name, password_hash, role, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (payload.username.lower(), payload.full_name.strip(), pw_hash, payload.role, now_iso),
        )
    return {"message": f"Đã tạo người dùng '{payload.username.lower()}' thành công."}


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not row or not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác.")
        new_hash = hash_password(payload.new_password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    return {"message": "Đã cập nhật mật khẩu mới."}
