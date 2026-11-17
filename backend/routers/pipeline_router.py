import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from backend.models.schemas import ExportRequest, PipelineDiscoveryRequest, PipelineSynthesizeRequest
from backend.security.auth import api_rate_limiter, get_current_user
from backend.services.export_service import (
    export_excel_deliverable,
    export_pptx_deck,
    export_word_proposal,
)
from backend.services.orchestrator import execute_single_agent
from backend.services.token_optimizer import get_token_telemetry

router = APIRouter(prefix="/api/pipeline", tags=["Multi-Agent Pipeline"])


@router.post("/stage1-discovery")
async def run_stage1_discovery(payload: PipelineDiscoveryRequest, user: dict = Depends(get_current_user)):
    """
    Stage 1 (Parallel Execution):
    - AI 1 researches vendor specs & legal compliance relevant to the customer's scenario.
    - AI 2 extracts customer pain points, MEDDIC gaps & expansion opportunities.
    Pauses at the Human-in-the-Loop Architect Gate before generating final deliverables.
    """
    api_rate_limiter.check(f"pipeline:{user['username']}")

    prompt_ai1 = (
        f"Dự án: {payload.deal_title}\n"
        f"Yêu cầu: Đối chiếu thông số kỹ thuật chính hãng và các quy định tuân thủ an ninh mạng "
        f"(Nghị định 13/2023/NĐ-CP, Thông tư 12/2022/TT-BTTTT, ISO 27001, NIST) phù hợp với bối cảnh sau:\n"
        f"{payload.customer_notes}"
    )
    prompt_ai2 = (
        f"Dự án: {payload.deal_title}\n"
        f"Yêu cầu: Phân tích MEDDIC, lỗ hổng hạ tầng, cơ hội bán thêm/bán chéo và bộ câu hỏi SPIN từ thông tin khách hàng:\n"
        f"{payload.customer_notes}"
    )

    ai1_res, ai2_res = await asyncio.gather(
        execute_single_agent(
            agent_key="ai1",
            raw_prompt=prompt_ai1,
            focus_vendor=payload.focus_vendor or "",
            focus_technology=payload.focus_technology or "",
            focus_industry=payload.focus_industry or "",
        ),
        execute_single_agent(
            agent_key="ai2",
            raw_prompt=prompt_ai2,
            focus_vendor=payload.focus_vendor or "",
            focus_technology=payload.focus_technology or "",
            focus_industry=payload.focus_industry or "",
        ),
    )

    return {
        "ai1": ai1_res,
        "ai2": ai2_res,
        "telemetry": get_token_telemetry(),
    }


@router.post("/stage2-synthesize")
async def run_stage2_synthesize(payload: PipelineSynthesizeRequest, user: dict = Depends(get_current_user)):
    """
    Stage 2 (Post Human-in-the-Loop Approval):
    - AI 3 builds the Technical Proposal, RFP Compliance Matrix & 3-Year TCO/ROI.
    - AI 4 builds the Executive/Technical Pitch Deck & POC Demo Script from AI 3's output.
    """
    api_rate_limiter.check(f"pipeline:{user['username']}")

    approval_note = payload.architect_approval_notes.strip() or "Kiến trúc sư giải pháp đã phê duyệt phương án kỹ thuật."

    prompt_ai3 = (
        f"Dự án: {payload.deal_title}\n"
        f"[ĐỊNH HƯỚNG DUYỆT CỦA KIẾN TRÚC SƯ]: {approval_note}\n\n"
        f"[DỮ LIỆU KỸ THUẬT & TUÂN THỦ TỪ AI 1]:\n{payload.ai1_output}\n\n"
        f"[PHÂN TÍCH KHÁCH HÀNG & CƠ HỘI TỪ AI 2]:\n{payload.ai2_output}\n\n"
        f"Hãy lập: (1) Kiến trúc giải pháp đề xuất (FAB), (2) Bảng đáp ứng RFP Compliance Matrix, và (3) Phân tích TCO/ROI 3 năm."
    )
    ai3_res = await execute_single_agent(agent_key="ai3", raw_prompt=prompt_ai3)

    prompt_ai4 = (
        f"Dự án: {payload.deal_title}\n"
        f"Dựa trên Hồ sơ Giải pháp của AI 3 dưới đây, hãy tạo:\n"
        f"(1) Dàn ý 5 Slide thuyết trình C-Level (tối đa 40 chữ/slide)\n"
        f"(2) Kịch bản Demo POC 15 phút\n"
        f"(3) Lời thoại thuyết trình tự nhiên (Voice Script) cho buổi họp khách hàng.\n\n"
        f"[HỒ SƠ GIẢI PHÁP TỪ AI 3]:\n{ai3_res['output']}"
    )
    ai4_res = await execute_single_agent(agent_key="ai4", raw_prompt=prompt_ai4)

    return {
        "ai3": ai3_res,
        "ai4": ai4_res,
        "telemetry": get_token_telemetry(),
    }


@router.post("/export/{fmt}")
def export_deliverable(fmt: str, payload: ExportRequest, user: dict = Depends(get_current_user)):
    if fmt == "xlsx":
        out_path = export_excel_deliverable(
            payload.deal_title, payload.ai1_output, payload.ai2_output, payload.ai3_output, payload.architect_notes
        )
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "docx":
        out_path = export_word_proposal(
            payload.deal_title, payload.ai1_output, payload.ai2_output, payload.ai3_output, payload.architect_notes
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "pptx":
        out_path = export_pptx_deck(
            payload.deal_title, payload.ai2_output, payload.ai3_output, payload.ai4_output
        )
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        raise HTTPException(status_code=400, detail="Định dạng xuất không hỗ trợ (chọn xlsx, docx, hoặc pptx).")

    return FileResponse(path=str(out_path), filename=out_path.name, media_type=media_type)
