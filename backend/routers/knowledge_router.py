from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pypdf import PdfReader
from backend.database import get_db
from backend.security.auth import get_current_user
from backend.services.rag_engine import chunk_document, retrieve_relevant_chunks

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base (RAG)"])

ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _extract_text_from_upload(filename: str, raw_bytes: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()
    return raw_bytes.decode("utf-8", errors="replace").strip()


@router.get("")
def list_knowledge(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, agent_scope, title, vendor, technology, domain,
                   source_filename, chunk_count, char_count, created_by, created_at
            FROM knowledge_docs
            ORDER BY id DESC
            """
        ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@router.post("/upload")
async def upload_knowledge_doc(
    agent_scope: str = Form("ai1"),
    title: str = Form(...),
    vendor: str = Form(""),
    technology: str = Form(""),
    domain: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if agent_scope not in {"all", "ai1", "ai2", "ai3", "ai4"}:
        raise HTTPException(status_code=400, detail="Phạm vi AI không hợp lệ.")

    safe_name = Path(file.filename or "document.txt").name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng tệp không hỗ trợ ({ext}). Chỉ chấp nhận: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dung lượng tệp vượt quá giới hạn an toàn 10MB.")

    extracted_text = _extract_text_from_upload(safe_name, raw_bytes)
    if len(extracted_text) < 20:
        raise HTTPException(status_code=400, detail="Không trích xuất được nội dung văn bản hợp lệ từ tệp.")

    chunks = chunk_document(extracted_text, chunk_size=650, overlap=80)
    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO knowledge_docs (
                agent_scope, title, vendor, technology, domain,
                source_filename, chunk_count, char_count, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
            """,
            (
                agent_scope,
                title.strip()[:150],
                vendor.strip()[:80],
                technology.strip()[:80],
                domain.strip()[:80],
                safe_name[:120],
                len(chunks),
                len(extracted_text),
                user["username"],
                now_iso,
            ),
        )
        doc_id = cur.fetchone()["id"]
        for idx, chunk_text in enumerate(chunks, start=1):
            conn.execute(
                "INSERT INTO knowledge_chunks (doc_id, agent_scope, chunk_index, content) VALUES (?, ?, ?, ?)",
                (doc_id, agent_scope, idx, chunk_text),
            )

    return {
        "message": f"Đã nạp '{title.strip()}' ({len(chunks)} phân đoạn chỉ mục RAG) cho {agent_scope.upper()}.",
        "doc_id": doc_id,
        "chunk_count": len(chunks),
    }


@router.delete("/{doc_id}")
def delete_knowledge_doc(doc_id: int, user: dict = Depends(get_current_user)):
    with get_db() as conn:
        conn.execute("DELETE FROM knowledge_docs WHERE id = ?", (doc_id,))
    return {"message": "Đã xóa tài liệu khỏi kho tri thức."}


@router.get("/search")
def test_rag_search(agent_key: str = "ai1", q: str = "", user: dict = Depends(get_current_user)):
    chunks = retrieve_relevant_chunks(agent_key=agent_key, query=q, top_k=4)
    return {"matches": chunks}
