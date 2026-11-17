import math
import re
from collections import Counter
from typing import List
from backend.database import get_db


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9À-ỹ_-]{2,}", text.lower())


def chunk_document(text: str, chunk_size: int = 650, overlap: int = 80) -> List[str]:
    """Splits technical documents cleanly along paragraph/sentence boundaries."""
    clean_text = re.sub(r"\r\n?", "\n", text).strip()
    if not clean_text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean_text) if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) <= chunk_size:
                current = para
            else:
                step = max(100, chunk_size - overlap)
                for i in range(0, len(para), step):
                    chunks.append(para[i : i + chunk_size].strip())
                current = ""
    if current:
        chunks.append(current)
    return chunks


def retrieve_relevant_chunks(
    agent_key: str,
    query: str,
    vendor_filter: str = "",
    tech_filter: str = "",
    top_k: int = 4,
) -> List[dict]:
    """
    Pure-Python BM25 lexical + metadata-boosted retriever.
    Injects only the top-K most relevant knowledge chunks into the AI prompt,
    preventing context bloat and saving up to 70% input tokens.
    """
    query_terms = _tokenize(f"{query} {vendor_filter} {tech_filter}")
    if not query_terms:
        return []

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.chunk_index, c.content, d.title, d.vendor, d.technology, d.domain
            FROM knowledge_chunks c
            JOIN knowledge_docs d ON d.id = c.doc_id
            WHERE c.agent_scope IN (?, 'all')
            """,
            (agent_key,),
        ).fetchall()

    if not rows:
        return []

    docs_tokens = [_tokenize(f"{r['title']} {r['vendor']} {r['technology']} {r['content']}") for r in rows]
    num_docs = len(docs_tokens)
    avgdl = sum(len(t) for t in docs_tokens) / max(1, num_docs)

    df = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] += 1

    k1 = 1.5
    b = 0.75
    scored = []

    for row, tokens in zip(rows, docs_tokens):
        tf = Counter(tokens)
        doc_len = len(tokens)
        score = 0.0
        for q_term in query_terms:
            if q_term not in tf:
                continue
            idf = math.log((num_docs - df[q_term] + 0.5) / (df[q_term] + 0.5) + 1.0)
            freq = tf[q_term]
            score += idf * ((freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / max(1.0, avgdl)))))

        if vendor_filter and vendor_filter.lower() in (row["vendor"] or "").lower():
            score *= 1.35
        if tech_filter and tech_filter.lower() in (row["technology"] or "").lower():
            score *= 1.25

        if score > 0:
            scored.append(
                {
                    "score": round(score, 3),
                    "title": row["title"],
                    "vendor": row["vendor"],
                    "technology": row["technology"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
