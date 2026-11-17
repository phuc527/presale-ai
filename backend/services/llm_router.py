import os
import subprocess
import time
from pathlib import Path
from typing import Optional
import httpx
from fastapi import HTTPException
from backend.config import settings
from backend.security.crypto import decrypt_secret


def detect_local_google_adc_token() -> tuple[Optional[str], Optional[str]]:
    """
    Convenient Direct-Login bridge: detects if the user has already signed in locally via
    `gcloud auth application-default login` on their workstation, allowing seamless Gemini
    calls using their Google account without manually creating an API key.
    """
    adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    if os.name == "nt":
        appdata = os.getenv("APPDATA", "")
        if appdata:
            adc_path = Path(appdata) / "gcloud" / "application_default_credentials.json"

    if not adc_path.exists():
        return None, None

    try:
        res = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        token = res.stdout.strip()
        if res.returncode == 0 and token.startswith("ya29."):
            return token, "Google ADC Local Session"
    except Exception:
        pass
    return None, None


async def invoke_llm(
    agent_cfg: dict,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, int, int, int]:
    """
    Unified Multi-Provider Router supporting:
      - Google Gemini (API Key OR OAuth 2.0 / ADC Direct Login Bearer Token)
      - OpenAI (API Key OR Web Session Bearer Token)
      - Anthropic Claude (API Key OR Session Token)
      - Local Ollama / vLLM (100% Offline, zero external calls)
    Returns (response_text, prompt_tokens, completion_tokens, latency_ms).
    """
    provider = agent_cfg["provider"]
    model_name = agent_cfg["model_name"]
    auth_mode = agent_cfg["auth_mode"]
    max_tokens = int(agent_cfg.get("max_output_tokens", 1600))
    temperature = float(agent_cfg.get("temperature", 0.2))
    base_url = (agent_cfg.get("base_url") or "").strip().rstrip("/")

    api_key = decrypt_secret(agent_cfg.get("encrypted_api_key", ""))
    oauth_token = decrypt_secret(agent_cfg.get("encrypted_oauth_token", ""))

    if not api_key and provider == "gemini" and settings.default_gemini_key:
        api_key = settings.default_gemini_key
    elif not api_key and provider == "openai" and settings.default_openai_key:
        api_key = settings.default_openai_key
    elif not api_key and provider == "anthropic" and settings.default_anthropic_key:
        api_key = settings.default_anthropic_key

    if provider == "gemini" and auth_mode == "oauth_login" and not oauth_token:
        adc_token, _ = detect_local_google_adc_token()
        if adc_token:
            oauth_token = adc_token

    start_ts = time.perf_counter()

    async with httpx.AsyncClient(timeout=90.0) as client:
        if provider == "gemini":
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {}

            if auth_mode == "oauth_login":
                if not oauth_token:
                    raise HTTPException(
                        status_code=400,
                        detail=f"[{agent_cfg['name']}] Chưa có phiên đăng nhập Google OAuth/ADC. Vui lòng bấm 'Đồng bộ Đăng nhập Google' hoặc chuyển sang API Key.",
                    )
                headers["Authorization"] = f"Bearer {oauth_token}"
            else:
                if not api_key:
                    raise HTTPException(
                        status_code=400,
                        detail=f"[{agent_cfg['name']}] Chưa cấu hình Gemini API Key. Vui lòng nhập API Key hoặc dùng chế độ Đăng nhập trực tiếp.",
                    )
                params["key"] = api_key

            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            resp = await client.post(endpoint, headers=headers, params=params, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Gemini API lỗi ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            usage = data.get("usageMetadata", {})
            p_tok = int(usage.get("promptTokenCount", 0))
            c_tok = int(usage.get("candidatesTokenCount", 0))

        elif provider == "openai":
            token = oauth_token if auth_mode == "oauth_login" else api_key
            if not token:
                raise HTTPException(
                    status_code=400,
                    detail=f"[{agent_cfg['name']}] Chưa cấu hình OpenAI API Key hoặc Session Token.",
                )
            url = f"{base_url or 'https://api.openai.com/v1'}/chat/completions"
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"OpenAI API lỗi ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            p_tok = int(usage.get("prompt_tokens", 0))
            c_tok = int(usage.get("completion_tokens", 0))

        elif provider == "anthropic":
            token = oauth_token if auth_mode == "oauth_login" else api_key
            if not token:
                raise HTTPException(
                    status_code=400,
                    detail=f"[{agent_cfg['name']}] Chưa cấu hình Anthropic API Key hoặc Session Token.",
                )
            url = f"{base_url or 'https://api.anthropic.com/v1'}/messages"
            headers = {
                "x-api-key": token,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            if auth_mode == "oauth_login" and token.startswith("Bearer "):
                headers.pop("x-api-key", None)
                headers["Authorization"] = token
            payload = {
                "model": model_name,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Anthropic API lỗi ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            text = data.get("content", [{}])[0].get("text", "")
            usage = data.get("usage", {})
            p_tok = int(usage.get("input_tokens", 0))
            c_tok = int(usage.get("output_tokens", 0))

        elif provider == "ollama":
            ollama_url = f"{base_url or settings.ollama_base_url}/api/chat"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
            try:
                resp = await client.post(ollama_url, json=payload)
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Không thể kết nối Local Ollama tại {ollama_url}: {exc}",
                )
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Ollama lỗi ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            p_tok = int(data.get("prompt_eval_count", 0))
            c_tok = int(data.get("eval_count", 0))

        else:
            raise HTTPException(status_code=400, detail=f"Provider không được hỗ trợ: {provider}")

    latency_ms = int((time.perf_counter() - start_ts) * 1000)
    return text.strip(), p_tok, c_tok, latency_ms
