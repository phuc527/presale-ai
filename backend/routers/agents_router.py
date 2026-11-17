import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from backend.config import settings
from backend.database import get_db
from backend.models.schemas import AgentConfigUpdate, AgentRunRequest
from backend.security.auth import api_rate_limiter, get_current_user
from backend.security.crypto import decrypt_secret, encrypt_secret, mask_secret
from backend.services.llm_router import detect_local_google_adc_token
from backend.services.orchestrator import execute_single_agent
from backend.services.token_optimizer import get_token_telemetry

router = APIRouter(prefix="/api/agents", tags=["AI Agents"])

MODEL_CATALOG = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
    "openai": ["gpt-4.1", "gpt-4.1-mini", "o4-mini", "gpt-4o"],
    "anthropic": ["claude-sonnet-4-20250514", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
    "ollama": ["qwen2.5:32b", "llama3.3:70b", "deepseek-r1:14b", "gemma3:27b"],
}

_OAUTH_PENDING_STATES: dict[str, str] = {}


def _serialize_agent(row: dict) -> dict:
    raw_api = decrypt_secret(row.get("encrypted_api_key", ""))
    raw_oauth = decrypt_secret(row.get("encrypted_oauth_token", ""))
    adc_token, adc_label = detect_local_google_adc_token()
    return {
        "agent_key": row["agent_key"],
        "name": row["name"],
        "short_role": row["short_role"],
        "provider": row["provider"],
        "model_name": row["model_name"],
        "auth_mode": row["auth_mode"],
        "has_api_key": bool(raw_api),
        "masked_api_key": mask_secret(raw_api),
        "has_oauth_token": bool(raw_oauth) or (row["provider"] == "gemini" and bool(adc_token)),
        "oauth_account_email": row.get("oauth_account_email") or (adc_label if row["provider"] == "gemini" and adc_token else ""),
        "base_url": row.get("base_url", ""),
        "vendors": json.loads(row.get("vendors") or "[]"),
        "technologies": json.loads(row.get("technologies") or "[]"),
        "industries": json.loads(row.get("industries") or "[]"),
        "frameworks": json.loads(row.get("frameworks") or "[]"),
        "depth_level": row.get("depth_level", "architect"),
        "max_output_tokens": row.get("max_output_tokens", 1600),
        "compression_level": row.get("compression_level", "balanced"),
        "cache_enabled": bool(row.get("cache_enabled", 1)),
        "temperature": row.get("temperature", 0.2),
        "system_prompt": row.get("system_prompt", ""),
        "updated_at": row.get("updated_at", ""),
    }


@router.get("")
def list_agents(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agent_configs ORDER BY agent_key ASC").fetchall()
    return {
        "agents": [_serialize_agent(dict(r)) for r in rows],
        "catalog": MODEL_CATALOG,
        "telemetry": get_token_telemetry(),
    }


@router.put("/{agent_key}")
def update_agent(agent_key: str, payload: AgentConfigUpdate, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM agent_configs WHERE agent_key = ?", (agent_key,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy AI Agent.")

        enc_api = existing["encrypted_api_key"]
        if payload.api_key is not None and payload.api_key.strip():
            enc_api = encrypt_secret(payload.api_key.strip())

        enc_oauth = existing["encrypted_oauth_token"]
        if payload.oauth_token is not None and payload.oauth_token.strip():
            enc_oauth = encrypt_secret(payload.oauth_token.strip())

        oauth_email = (
            payload.oauth_account_email.strip()
            if payload.oauth_account_email is not None
            else existing["oauth_account_email"]
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            UPDATE agent_configs SET
                provider = ?,
                model_name = ?,
                auth_mode = ?,
                encrypted_api_key = ?,
                encrypted_oauth_token = ?,
                oauth_account_email = ?,
                base_url = ?,
                vendors = ?,
                technologies = ?,
                industries = ?,
                frameworks = ?,
                depth_level = ?,
                max_output_tokens = ?,
                compression_level = ?,
                cache_enabled = ?,
                temperature = ?,
                system_prompt = ?,
                updated_at = ?
            WHERE agent_key = ?
            """,
            (
                payload.provider,
                payload.model_name.strip(),
                payload.auth_mode,
                enc_api,
                enc_oauth,
                oauth_email,
                (payload.base_url or "").strip(),
                json.dumps(payload.vendors, ensure_ascii=False),
                json.dumps(payload.technologies, ensure_ascii=False),
                json.dumps(payload.industries, ensure_ascii=False),
                json.dumps(payload.frameworks, ensure_ascii=False),
                payload.depth_level,
                payload.max_output_tokens,
                payload.compression_level,
                1 if payload.cache_enabled else 0,
                payload.temperature,
                payload.system_prompt.strip(),
                now_iso,
                agent_key,
            ),
        )
        updated = conn.execute("SELECT * FROM agent_configs WHERE agent_key = ?", (agent_key,)).fetchone()
    return {"message": f"Đã lưu cấu hình cho {updated['name']}.", "agent": _serialize_agent(dict(updated))}


@router.post("/{agent_key}/sync-local-login")
def sync_local_login(agent_key: str, user: dict = Depends(get_current_user)):
    """Detects local workstation OAuth/ADC credentials (e.g., Google ADC) and binds them securely to the AI."""
    token, label = detect_local_google_adc_token()
    if not token:
        raise HTTPException(
            status_code=400,
            detail=(
                "Chưa phát hiện phiên đăng nhập Google cục bộ. Bạn có thể chạy lệnh "
                "'gcloud auth application-default login' trên máy hoặc dán trực tiếp Session/OAuth Token."
            ),
        )
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE agent_configs
            SET provider = 'gemini', auth_mode = 'oauth_login', encrypted_oauth_token = ?,
                oauth_account_email = ?, updated_at = ?
            WHERE agent_key = ?
            """,
            (encrypt_secret(token), label or "Google Direct Login", now_iso, agent_key),
        )
    return {"message": "Đã đồng bộ phiên đăng nhập Google trực tiếp thành công.", "account": label}


@router.get("/oauth/google/start/{agent_key}")
def google_oauth_start(agent_key: str, request: Request, user: dict = Depends(get_current_user)):
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=400,
            detail="Chưa cấu hình GOOGLE_OAUTH_CLIENT_ID trong .env. Bạn có thể dùng nút 'Đồng bộ Google ADC cục bộ' hoặc nhập Session Token.",
        )
    state = f"{agent_key}:{secrets.token_urlsafe(24)}"
    _OAUTH_PENDING_STATES[state] = agent_key
    redirect_uri = str(request.base_url).rstrip("/") + "/api/agents/oauth/google/callback"
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email https://www.googleapis.com/auth/generative-language.retriever",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return {"auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"}


@router.get("/oauth/google/callback", response_class=HTMLResponse)
def google_oauth_callback(state: str = "", code: str = ""):
    agent_key = _OAUTH_PENDING_STATES.pop(state, None)
    if not agent_key or not code:
        return HTMLResponse("<h3>Xác thực OAuth không hợp lệ hoặc đã hết hạn. Vui lòng đóng cửa sổ này.</h3>", status_code=400)
    return HTMLResponse(
        "<script>if(window.opener){window.opener.postMessage({type:'oauth_done'}, window.location.origin);} window.close();</script>"
        "<p>Đăng nhập Google thành công! Bạn có thể đóng cửa sổ này.</p>"
    )


@router.post("/{agent_key}/run")
async def run_agent(agent_key: str, payload: AgentRunRequest, user: dict = Depends(get_current_user)):
    api_rate_limiter.check(f"agent:{user['username']}")
    result = await execute_single_agent(
        agent_key=agent_key,
        raw_prompt=payload.prompt,
        focus_vendor=payload.focus_vendor or "",
        focus_technology=payload.focus_technology or "",
        focus_industry=payload.focus_industry or "",
        depth_override=payload.depth_override or "",
        bypass_cache=payload.bypass_cache,
    )
    return {"result": result, "telemetry": get_token_telemetry()}
