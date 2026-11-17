import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.database import get_db


def estimate_tokens(text: str) -> int:
    """Fast, deterministic token estimator (~3.6 chars/token for mixed Vietnamese/English technical text)."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.6))


def compress_context(text: str, level: str = "balanced") -> tuple[str, int]:
    """
    Reduces redundant whitespace, duplicate lines, and verbose markdown filler
    while preserving 100% of numbers, technical specifications, legal citations, and URLs.
    Returns (compressed_text, tokens_saved).
    """
    if not text or level == "off":
        return text, 0

    original_tokens = estimate_tokens(text)

    lines = [line.rstrip() for line in text.splitlines()]
    deduped_lines = []
    seen_boilerplate = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if deduped_lines and deduped_lines[-1] != "":
                deduped_lines.append("")
            continue
        if level == "aggressive" and re.fullmatch(r"[-=*_]{3,}", stripped):
            continue
        norm_key = re.sub(r"\s+", " ", stripped.lower())
        if len(norm_key) > 25:
            if norm_key in seen_boilerplate:
                continue
            seen_boilerplate.add(norm_key)

        compact_line = re.sub(r"[ \t]{2,}", " ", line)
        if level == "aggressive":
            compact_line = re.sub(r"\*\*(.*?)\*\*", r"\1", compact_line)
        deduped_lines.append(compact_line)

    compressed = "\n".join(deduped_lines).strip()
    new_tokens = estimate_tokens(compressed)
    saved = max(0, original_tokens - new_tokens)
    return compressed, saved


def build_cache_key(agent_key: str, model_name: str, prompt: str, context: str) -> str:
    clean_prompt = re.sub(r'\s+', ' ', prompt.strip().lower())
    normalized = f"{agent_key}|{model_name}|{clean_prompt}|{context.strip()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_response(cache_key: str, ttl_hours: int = 24) -> Optional[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=ttl_hours)).isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT response_text, created_at FROM semantic_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        if row["created_at"] < cutoff:
            conn.execute("DELETE FROM semantic_cache WHERE cache_key = ?", (cache_key,))
            return None
        return row["response_text"]


def set_cached_response(cache_key: str, agent_key: str, response_text: str, tokens_saved: int) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO semantic_cache (cache_key, agent_key, response_text, tokens_saved, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_text = excluded.response_text,
                tokens_saved = excluded.tokens_saved,
                created_at = excluded.created_at
            """,
            (cache_key, agent_key, response_text, tokens_saved, now_iso),
        )


def log_token_usage(
    agent_key: str,
    provider: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    saved_tokens: int,
    cache_hit: bool,
    latency_ms: int,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO token_usage_logs (
                agent_key, provider, model_name, prompt_tokens,
                completion_tokens, saved_tokens, cache_hit, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_key,
                provider,
                model_name,
                prompt_tokens,
                completion_tokens,
                saved_tokens,
                1 if cache_hit else 0,
                latency_ms,
                now_iso,
            ),
        )


def get_token_telemetry() -> dict:
    with get_db() as conn:
        totals = conn.execute(
            """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) AS total_prompt,
                COALESCE(SUM(completion_tokens), 0) AS total_completion,
                COALESCE(SUM(saved_tokens), 0) AS total_saved,
                COALESCE(SUM(cache_hit), 0) AS total_cache_hits,
                COUNT(*) AS total_calls
            FROM token_usage_logs
            """
        ).fetchone()

        by_agent = conn.execute(
            """
            SELECT
                agent_key,
                COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS used_tokens,
                COALESCE(SUM(saved_tokens), 0) AS saved_tokens,
                COALESCE(SUM(cache_hit), 0) AS cache_hits,
                COUNT(*) AS calls
            FROM token_usage_logs
            GROUP BY agent_key
            """
        ).fetchall()

    total_used = totals["total_prompt"] + totals["total_completion"]
    total_saved = totals["total_saved"]
    denom = total_used + total_saved
    savings_pct = round((total_saved / denom) * 100, 1) if denom > 0 else 0.0

    return {
        "total_prompt_tokens": totals["total_prompt"],
        "total_completion_tokens": totals["total_completion"],
        "total_used_tokens": total_used,
        "total_saved_tokens": total_saved,
        "savings_percent": savings_pct,
        "total_cache_hits": totals["total_cache_hits"],
        "total_calls": totals["total_calls"],
        "by_agent": [dict(r) for r in by_agent],
    }
