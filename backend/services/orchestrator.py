import json
from backend.database import get_db
from backend.services.llm_router import invoke_llm
from backend.services.rag_engine import retrieve_relevant_chunks
from backend.services.token_optimizer import (
    build_cache_key,
    compress_context,
    estimate_tokens,
    get_cached_response,
    log_token_usage,
    set_cached_response,
)

DEPTH_DIRECTIVES = {
    "executive": (
        "MỨC ĐỘ ĐÀO SÂU: EXECUTIVE BRIEF — Tóm tắt tác động kinh doanh, chi phí/rủi ro, "
        "lợi thế cạnh tranh và quyết định chiến lược cho C-Level. Ngắn gọn, súc tích."
    ),
    "architect": (
        "MỨC ĐỘ ĐÀO SÂU: SOLUTION ARCHITECT (HLD) — Phân tích kiến trúc tổng thể, luồng dữ liệu, "
        "khả năng tích hợp, tính sẵn sàng cao (HA/DR), bảo mật và ánh xạ tiêu chuẩn tuân thủ."
    ),
    "deep_engineering": (
        "MỨC ĐỘ ĐÀO SÂU: DEEP ENGINEERING & SIZING — Đi sâu vào thông số kỹ thuật chi tiết, "
        "cơ chế hoạt động nội tại (protocol, RPO/RTO, IOPS/throughput, licensing), cấu hình tham chiếu, "
        "điểm nghẽn cần lưu ý và đối chiếu từng điều khoản tuân thủ."
    ),
}


def get_agent_config(agent_key: str) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agent_configs WHERE agent_key = ?", (agent_key,)).fetchone()
    if not row:
        raise ValueError(f"Unknown agent: {agent_key}")
    cfg = dict(row)
    cfg["vendors_list"] = json.loads(cfg.get("vendors") or "[]")
    cfg["technologies_list"] = json.loads(cfg.get("technologies") or "[]")
    cfg["industries_list"] = json.loads(cfg.get("industries") or "[]")
    cfg["frameworks_list"] = json.loads(cfg.get("frameworks") or "[]")
    return cfg


def build_specialized_system_prompt(
    cfg: dict,
    focus_vendor: str = "",
    focus_technology: str = "",
    focus_industry: str = "",
    depth_override: str = "",
) -> str:
    vendors = focus_vendor.strip() or ", ".join(cfg["vendors_list"]) or "Đa hãng (Vendor-Agnostic)"
    techs = focus_technology.strip() or ", ".join(cfg["technologies_list"]) or "Hạ tầng CNTT & An ninh mạng"
    industries = focus_industry.strip() or ", ".join(cfg["industries_list"]) or "Doanh nghiệp B2B"
    frameworks = ", ".join(cfg["frameworks_list"]) or "ISO 27001, NIST CSF"
    depth_key = depth_override.strip() or cfg.get("depth_level", "architect")
    depth_instruction = DEPTH_DIRECTIVES.get(depth_key, DEPTH_DIRECTIVES["architect"])

    specialization_block = (
        f"\n\n=== PHẠM VI CHUYÊN SÂU ĐƯỢC CẤU HÌNH ===\n"
        f"- Hãng công nghệ trọng tâm: {vendors}\n"
        f"- Mảng công nghệ chuyên sâu: {techs}\n"
        f"- Lĩnh vực / Ngành nghề mục tiêu: {industries}\n"
        f"- Khung tuân thủ / Phương pháp luận: {frameworks}\n"
        f"- {depth_instruction}\n"
        f"- Nguyên tắc tiết kiệm token: Trả lời trực diện, không mở đầu/kết luận sáo rỗng, ưu tiên bảng biểu và gạch đầu dòng giàu thông tin."
    )
    return cfg["system_prompt"].strip() + specialization_block


async def execute_single_agent(
    agent_key: str,
    raw_prompt: str,
    focus_vendor: str = "",
    focus_technology: str = "",
    focus_industry: str = "",
    depth_override: str = "",
    bypass_cache: bool = False,
) -> dict:
    cfg = get_agent_config(agent_key)
    compression_level = cfg.get("compression_level", "balanced")

    compressed_prompt, saved_input_tokens = compress_context(raw_prompt, compression_level)

    rag_chunks = retrieve_relevant_chunks(
        agent_key=agent_key,
        query=compressed_prompt,
        vendor_filter=focus_vendor,
        tech_filter=focus_technology,
        top_k=4,
    )
    rag_context = ""
    if rag_chunks:
        rag_lines = ["=== TÀI LIỆU NỘI BỘ ĐÃ XÁC THỰC (TRÍCH DẪN NGUỒN KHI DÙNG) ==="]
        for idx, ch in enumerate(rag_chunks, start=1):
            rag_lines.append(f"[{idx}] ({ch['title']} | {ch['vendor']}): {ch['content']}")
        rag_context = "\n".join(rag_lines)

    effective_system = build_specialized_system_prompt(
        cfg, focus_vendor, focus_technology, focus_industry, depth_override
    )
    full_user_payload = f"{rag_context}\n\n=== YÊU CẦU XỬ LÝ ===\n{compressed_prompt}".strip()

    cache_key = build_cache_key(agent_key, cfg["model_name"], effective_system, full_user_payload)
    if cfg.get("cache_enabled") and not bypass_cache:
        cached = get_cached_response(cache_key)
        if cached:
            saved_total = estimate_tokens(effective_system + full_user_payload) + estimate_tokens(cached)
            log_token_usage(
                agent_key=agent_key,
                provider=cfg["provider"],
                model_name=cfg["model_name"],
                prompt_tokens=0,
                completion_tokens=0,
                saved_tokens=saved_total,
                cache_hit=True,
                latency_ms=3,
            )
            return {
                "agent_key": agent_key,
                "agent_name": cfg["name"],
                "provider": cfg["provider"],
                "model_name": cfg["model_name"],
                "output": cached,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "saved_tokens": saved_total,
                "cache_hit": True,
                "latency_ms": 3,
                "rag_sources": [c["title"] for c in rag_chunks],
            }

    output_text, p_tok, c_tok, latency_ms = await invoke_llm(
        agent_cfg=cfg,
        system_prompt=effective_system,
        user_prompt=full_user_payload,
    )
    if p_tok == 0:
        p_tok = estimate_tokens(effective_system + full_user_payload)
    if c_tok == 0:
        c_tok = estimate_tokens(output_text)

    if cfg.get("cache_enabled"):
        set_cached_response(cache_key, agent_key, output_text, saved_input_tokens)

    log_token_usage(
        agent_key=agent_key,
        provider=cfg["provider"],
        model_name=cfg["model_name"],
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        saved_tokens=saved_input_tokens,
        cache_hit=False,
        latency_ms=latency_ms,
    )

    return {
        "agent_key": agent_key,
        "agent_name": cfg["name"],
        "provider": cfg["provider"],
        "model_name": cfg["model_name"],
        "output": output_text,
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "saved_tokens": saved_input_tokens,
        "cache_hit": False,
        "latency_ms": latency_ms,
        "rag_sources": [c["title"] for c in rag_chunks],
    }
