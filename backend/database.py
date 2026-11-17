import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from backend.config import DB_PATH, settings
from backend.security.crypto import encrypt_secret

# Postgres (e.g. Supabase) when set, local SQLite otherwise.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


class _PgConn:
    """Lets the sqlite-style SQL in this codebase (`?` params, executescript) run on Postgres."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        return self._conn.execute(sql.replace("?", "%s"), params or None)

    def executescript(self, sql):
        self._conn.execute(sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY"))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _connect():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        # prepare_threshold=None: Supabase transaction pooler rejects prepared statements.
        return _PgConn(psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None))
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


DEFAULT_AGENTS = [
    {
        "agent_key": "ai1",
        "name": "AI 1 — Tech & Compliance Researcher",
        "short_role": "Nghiên cứu Công nghệ & Tuân thủ Pháp lý",
        "provider": "gemini",
        "model_name": "gemini-2.5-flash",
        "auth_mode": "api_key",
        "base_url": "",
        "vendors": json.dumps(["NetApp", "HPE", "Dell", "IBM", "VMware", "Acronis", "Palo Alto"]),
        "technologies": json.dumps(["Enterprise Storage & NVMe", "Cyber Resilience & Immutable Backup", "HCI & Hybrid Cloud", "Zero Trust Security"]),
        "industries": json.dumps(["Ngân hàng & Tài chính (BFSI)", "Y tế & Bệnh viện", "Sản xuất Công nghiệp", "Chính phủ"]),
        "frameworks": json.dumps(["Nghị định 13/2023/NĐ-CP", "Thông tư 12/2022/TT-BTTTT", "Luật An ninh mạng", "ISO/IEC 27001:2022", "NIST CSF 2.0"]),
        "depth_level": "architect",
        "max_output_tokens": 1600,
        "compression_level": "balanced",
        "cache_enabled": 1,
        "temperature": 0.15,
        "system_prompt": (
            "Bạn là Kiến trúc sư Giải pháp Công nghệ và Chuyên gia Tuân thủ (AI 1). "
            "Nhiệm vụ: Nghiên cứu sâu tài liệu chính hãng (Datasheet, Admin Guide, Whitepaper) và quy định pháp luật/tiêu chuẩn an ninh mạng hiện hành. "
            "Quy tắc: (1) Chỉ trích xuất thông tin xác thực, kèm nguồn [Tên tài liệu / Điều khoản]. "
            "(2) Nếu thiếu thông số hãng, ghi rõ 'Cần xác nhận với Vendor', tuyệt đối không suy đoán. "
            "(3) Trình bày súc tích dạng bảng thông số và ma trận ánh xạ tuân thủ để tối ưu token cho bước sau."
        ),
    },
    {
        "agent_key": "ai2",
        "name": "AI 2 — Discovery & Opportunity Miner",
        "short_role": "Khai thác Khách hàng & Cơ hội Kinh doanh",
        "provider": "gemini",
        "model_name": "gemini-2.5-flash",
        "auth_mode": "api_key",
        "base_url": "",
        "vendors": json.dumps(["Multi-Vendor Assessment", "VMware Replacement", "Backup Modernization"]),
        "technologies": json.dumps(["Infrastructure Audit", "Ransomware Gap Analysis", "Cloud Repatriation", "TCO Optimization"]),
        "industries": json.dumps(["Doanh nghiệp Lớn (Enterprise)", "Ngân hàng", "Bệnh viện", "Nhà máy Sản xuất"]),
        "frameworks": json.dumps(["MEDDIC", "SPIN Selling", "BANT", "Value Engineering"]),
        "depth_level": "architect",
        "max_output_tokens": 1500,
        "compression_level": "balanced",
        "cache_enabled": 1,
        "temperature": 0.3,
        "system_prompt": (
            "Bạn là Chuyên gia Tư vấn Khai thác Nhu cầu và Phát triển Cơ hội Kinh doanh B2B (AI 2). "
            "Nhiệm vụ: Phân tích biên bản họp, email, RFP của khách hàng theo khung MEDDIC. "
            "Quy tắc: (1) Chỉ ra nỗi đau cốt lõi và khoảng trống kiến trúc tiềm ẩn (Single Point of Failure, rủi ro Ransomware, thiếu tuân thủ). "
            "(2) Đề xuất cơ hội bán thêm (Up-sell) và bán chéo (Cross-sell) có tính khả thi cao. "
            "(3) Cung cấp 5 câu hỏi khai thác SPIN sắc bén cho buổi họp kế tiếp."
        ),
    },
    {
        "agent_key": "ai3",
        "name": "AI 3 — Solution & RFP Architect",
        "short_role": "Thiết kế Giải pháp, Compliance Matrix & TCO",
        "provider": "gemini",
        "model_name": "gemini-2.5-pro",
        "auth_mode": "api_key",
        "base_url": "",
        "vendors": json.dumps(["NetApp", "HPE", "Dell", "IBM", "Acronis", "VMware", "Cisco"]),
        "technologies": json.dumps(["High-Level Design (HLD)", "BOM & Sizing", "RFP Compliance Matrix", "3-Year TCO/ROI Model"]),
        "industries": json.dumps(["Đấu thầu Doanh nghiệp", "Tài chính Ngân hàng", "Y tế", "Sản xuất"]),
        "frameworks": json.dumps(["Feature-Advantage-Benefit (FAB)", "RFP Compliance Scoring", "TCO/ROI Financial Modeling"]),
        "depth_level": "deep_engineering",
        "max_output_tokens": 2200,
        "compression_level": "balanced",
        "cache_enabled": 1,
        "temperature": 0.2,
        "system_prompt": (
            "Bạn là Chuyên gia Thiết kế Tài liệu Giải pháp và Hồ sơ Đấu thầu Công nghệ (AI 3). "
            "Nhiệm vụ: Kết hợp thông số kỹ thuật từ AI 1 và phân tích cơ hội từ AI 2 để lập Hồ sơ Giải pháp (Proposal), "
            "Bảng đáp ứng kỹ thuật RFP (Compliance Matrix) và Bảng phân tích TCO/ROI 3 năm. "
            "Quy tắc: Gắn chặt từng tính năng kỹ thuật với giá trị kinh doanh (Feature -> Advantage -> Benefit)."
        ),
    },
    {
        "agent_key": "ai4",
        "name": "AI 4 — Value Pitch & Demo Producer",
        "short_role": "Thuyết trình C-Level, Kịch bản Demo & Voice",
        "provider": "gemini",
        "model_name": "gemini-2.5-flash",
        "auth_mode": "api_key",
        "base_url": "",
        "vendors": json.dumps(["Executive Storytelling", "Technical POC Demo"]),
        "technologies": json.dumps(["C-Level Business Case", "Live POC Demo Flow", "Objection Handling"]),
        "industries": json.dumps(["Ban Giám đốc (CEO/CFO/CIO)", "Giám đốc CNTT (IT Manager)", "Hội đồng Đấu thầu"]),
        "frameworks": json.dumps(["Pyramid Principle", "Executive Value Pitch", "POC Success Criteria"]),
        "depth_level": "executive",
        "max_output_tokens": 1800,
        "compression_level": "balanced",
        "cache_enabled": 1,
        "temperature": 0.45,
        "system_prompt": (
            "Bạn là Chuyên gia Kể chuyện Công nghệ và Thiết kế Thuyết trình Pre-sales (AI 4). "
            "Nhiệm vụ: Chuyển hóa giải pháp từ AI 3 thành bộ Slide thuyết trình (tối đa 40 chữ/slide theo nguyên tắc Kim tự tháp), "
            "kịch bản Demo POC thực tế và lời thoại thuyết trình tự nhiên tách biệt cho C-level và Đội ngũ Kỹ thuật."
        ),
    },
]


def init_db() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'presales',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_configs (
                agent_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                short_role TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'gemini',
                model_name TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
                auth_mode TEXT NOT NULL DEFAULT 'api_key',
                encrypted_api_key TEXT NOT NULL DEFAULT '',
                encrypted_oauth_token TEXT NOT NULL DEFAULT '',
                oauth_account_email TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                vendors TEXT NOT NULL DEFAULT '[]',
                technologies TEXT NOT NULL DEFAULT '[]',
                industries TEXT NOT NULL DEFAULT '[]',
                frameworks TEXT NOT NULL DEFAULT '[]',
                depth_level TEXT NOT NULL DEFAULT 'architect',
                max_output_tokens INTEGER NOT NULL DEFAULT 1600,
                compression_level TEXT NOT NULL DEFAULT 'balanced',
                cache_enabled INTEGER NOT NULL DEFAULT 1,
                temperature REAL NOT NULL DEFAULT 0.2,
                system_prompt TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_scope TEXT NOT NULL DEFAULT 'all',
                title TEXT NOT NULL,
                vendor TEXT NOT NULL DEFAULT '',
                technology TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT '',
                source_filename TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                char_count INTEGER NOT NULL DEFAULT 0,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                agent_scope TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES knowledge_docs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS semantic_cache (
                cache_key TEXT PRIMARY KEY,
                agent_key TEXT NOT NULL,
                response_text TEXT NOT NULL,
                tokens_saved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS token_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_key TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                saved_tokens INTEGER NOT NULL DEFAULT 0,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS whatsapp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT NOT NULL,
                sender TEXT NOT NULL,
                command TEXT NOT NULL,
                message_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        for cfg in DEFAULT_AGENTS:
            existing = conn.execute(
                "SELECT agent_key FROM agent_configs WHERE agent_key = ?", (cfg["agent_key"],)
            ).fetchone()
            if not existing:
                default_enc_key = encrypt_secret(settings.default_gemini_key) if settings.default_gemini_key else ""
                conn.execute(
                    """
                    INSERT INTO agent_configs (
                        agent_key, name, short_role, provider, model_name, auth_mode,
                        encrypted_api_key, base_url, vendors, technologies, industries,
                        frameworks, depth_level, max_output_tokens, compression_level,
                        cache_enabled, temperature, system_prompt, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cfg["agent_key"],
                        cfg["name"],
                        cfg["short_role"],
                        cfg["provider"],
                        cfg["model_name"],
                        cfg["auth_mode"],
                        default_enc_key,
                        cfg["base_url"],
                        cfg["vendors"],
                        cfg["technologies"],
                        cfg["industries"],
                        cfg["frameworks"],
                        cfg["depth_level"],
                        cfg["max_output_tokens"],
                        cfg["compression_level"],
                        cfg["cache_enabled"],
                        cfg["temperature"],
                        cfg["system_prompt"],
                        now_iso,
                    ),
                )

        doc_count = conn.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"]
        if doc_count == 0:
            starter_docs = [
                {
                    "agent_scope": "ai1",
                    "title": "Nghị định 13/2023/NĐ-CP & Thông tư 12/2022/TT-BTTTT (Tóm lược Kỹ thuật)",
                    "vendor": "Gov / Compliance VN",
                    "technology": "Data Privacy & Critical Info Infrastructure",
                    "domain": "Tuân thủ Pháp lý Việt Nam",
                    "filename": "vn_cyber_compliance_reference.md",
                    "chunks": [
                        "[Nghị định 13/2023/NĐ-CP - Điều 24 & 25] Dữ liệu cá nhân nhạy cảm (tài chính, y tế, sinh trắc học) bắt buộc áp dụng biện pháp mã hóa khi lưu trữ và truyền tải, phân quyền truy cập tối thiểu (Least Privilege), ghi nhật ký truy cập bất biến (Audit Log) và đánh giá tác động xử lý dữ liệu cá nhân (DPIA).",
                        "[Thông tư 12/2022/TT-BTTTT - Bảo đảm an toàn hệ thống thông tin theo cấp độ] Hệ thống thông tin từ Cấp độ 3 trở lên yêu cầu tách vùng mạng (DMZ, Core, Management), sao lưu dự phòng ngoại tuyến hoặc bất biến (Immutable/Air-gapped Backup) chống mã độc tống tiền, và giám sát tập trung SIEM/SOC 24/7.",
                    ],
                },
                {
                    "agent_scope": "ai1",
                    "title": "Enterprise Storage & Cyber Resilience Reference Architecture",
                    "vendor": "NetApp / HPE / Veeam / Acronis",
                    "technology": "Immutable Storage & Ransomware Recovery",
                    "domain": "Data Center Infrastructure",
                    "filename": "enterprise_cyber_resilience_ref.md",
                    "chunks": [
                        "[Autonomous Ransomware Protection & SnapLock Compliance] Kiến trúc lưu trữ chống Ransomware cần kết hợp phát hiện bất thường Entropy/IOPS theo thời gian thực trên tầng lưu trữ chính (RPO < 60 giây), tự động kích hoạt bản chụp bất biến (WORM/SnapLock) không thể xóa ngay cả với tài khoản Root/Admin trong thời gian lưu giữ (Retention Lock).",
                        "[3-2-1-1-0 Backup & Cleanroom Recovery] Dữ liệu sao lưu phải duy trì 3 bản sao, trên 2 loại phương tiện khác nhau, 1 bản sao ngoài site chính (Off-site DR), 1 bản sao bất biến/cách ly (Immutable/Air-gapped) và 0 lỗi sau khi kiểm thử khôi phục tự động (Automated Recovery Verification).",
                    ],
                },
            ]
            for sdoc in starter_docs:
                cur = conn.execute(
                    """
                    INSERT INTO knowledge_docs (
                        agent_scope, title, vendor, technology, domain,
                        source_filename, chunk_count, char_count, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
                    """,
                    (
                        sdoc["agent_scope"],
                        sdoc["title"],
                        sdoc["vendor"],
                        sdoc["technology"],
                        sdoc["domain"],
                        sdoc["filename"],
                        len(sdoc["chunks"]),
                        sum(len(c) for c in sdoc["chunks"]),
                        "system",
                        now_iso,
                    ),
                )
                doc_id = cur.fetchone()["id"]
                for idx, chunk_text in enumerate(sdoc["chunks"]):
                    conn.execute(
                        "INSERT INTO knowledge_chunks (doc_id, agent_scope, chunk_index, content) VALUES (?, ?, ?, ?)",
                        (doc_id, sdoc["agent_scope"], idx + 1, chunk_text),
                    )
