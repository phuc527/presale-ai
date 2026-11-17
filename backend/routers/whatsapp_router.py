import hashlib
import hmac
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from backend.config import settings
from backend.database import get_db
from backend.models.schemas import WhatsAppSimulateRequest
from backend.security.auth import get_current_user
from backend.services.orchestrator import execute_single_agent
from backend.services.token_optimizer import get_token_telemetry

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp Bridge"])


def _log_wa(direction: str, sender: str, command: str, text: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO whatsapp_logs (direction, sender, command, message_text, created_at) VALUES (?, ?, ?, ?, ?)",
            (direction, sender[:40], command[:30], text[:4000], now_iso),
        )


def _route_command(raw_message: str) -> tuple[str, str]:
    msg = raw_message.strip()
    lower = msg.lower()
    if lower.startswith("/research "):
        return "ai1", msg[10:].strip()
    if lower.startswith("/opportunity "):
        return "ai2", msg[13:].strip()
    if lower.startswith("/rfp "):
        return "ai3", msg[5:].strip()
    if lower.startswith("/pitch "):
        return "ai4", msg[7:].strip()
    if lower in {"/status", "/tokens"}:
        return "system_status", msg
    if any(k in lower for k in ["nghị định", "thông tư", "iso", "spec", "datasheet", "hãng", "tuân thủ"]):
        return "ai1", msg
    if any(k in lower for k in ["slide", "pitch", "demo", "thuyết trình", "c-level"]):
        return "ai4", msg
    if any(k in lower for k in ["rfp", "tco", "roi", "proposal", "báo giá", "compliance"]):
        return "ai3", msg
    return "ai2", msg


async def _handle_whatsapp_text(sender: str, text: str) -> dict:
    route_target, clean_query = _route_command(text)
    _log_wa("inbound", sender, route_target, text)

    if route_target == "system_status":
        tele = get_token_telemetry()
        reply = (
            f"📊 *Pre-Sales AI Status*\n"
            f"• Tổng lượt gọi: {tele['total_calls']}\n"
            f"• Token đã dùng: {tele['total_used_tokens']:,}\n"
            f"• Token tiết kiệm (Cache + Nén): {tele['total_saved_tokens']:,} ({tele['savings_percent']}%)"
        )
        _log_wa("outbound", "PreSales-AI-Bot", "status", reply)
        return {"route": "status", "reply": reply}

    res = await execute_single_agent(agent_key=route_target, raw_prompt=clean_query)
    badge = "⚡ CACHE HIT (0 token)" if res["cache_hit"] else f"🪙 {res['prompt_tokens'] + res['completion_tokens']} tok"
    reply = f"*[{res['agent_name']}]* ({res['model_name']} | {badge})\n\n{res['output']}"
    _log_wa("outbound", "PreSales-AI-Bot", route_target, reply)
    return {"route": route_target, "reply": reply, "meta": res}


@router.get("/webhook")
def verify_meta_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    """Official Meta WhatsApp Cloud API Webhook Verification Endpoint."""
    if hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token, settings.whatsapp_verify_token):
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="WhatsApp Verify Token không khớp.")


@router.post("/webhook")
async def receive_meta_webhook(request: Request):
    """Receives incoming WhatsApp Cloud API messages with optional HMAC-SHA256 signature verification."""
    raw_body = await request.body()
    if settings.whatsapp_app_secret:
        sig_header = request.headers.get("x-hub-signature-256", "")
        expected_sig = "sha256=" + hmac.new(
            settings.whatsapp_app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected_sig):
            raise HTTPException(status_code=403, detail="Chữ ký X-Hub-Signature-256 không hợp lệ.")

    body = await request.json()
    entries = body.get("entry", [])
    processed = 0
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") == "text":
                    sender = msg.get("from", "unknown")
                    text_body = msg.get("text", {}).get("body", "")
                    if text_body:
                        await _handle_whatsapp_text(sender, text_body)
                        processed += 1
    return {"status": "ok", "processed": processed}


@router.post("/simulate")
async def simulate_whatsapp_message(payload: WhatsAppSimulateRequest, user: dict = Depends(get_current_user)):
    result = await _handle_whatsapp_text(payload.sender, payload.message)
    return {"result": result, "telemetry": get_token_telemetry()}


@router.get("/logs")
def get_whatsapp_logs(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM whatsapp_logs ORDER BY id DESC LIMIT 30").fetchall()
    return {"logs": [dict(r) for r in rows]}
