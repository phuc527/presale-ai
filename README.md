# Pre-Sales AI Command Center (Local Enterprise Edition)

Ứng dụng web chạy cục bộ (Local-First) dành cho Kỹ sư Giải pháp Pre-sales Công nghệ, tích hợp kiến trúc **4 AI chuyên biệt**, **Tối ưu hóa Token & Semantic Cache**, **Đa mô hình AI (API Key hoặc Đăng nhập trực tiếp OAuth/ADC)**, **Hệ thống đào sâu theo Hãng/Công nghệ/Lĩnh vực + RAG nội bộ**, và **Cổng tích hợp WhatsApp Chat**.

---

## 1. Kiến trúc Hệ thống & Bảo mật (Security-by-Design)

Ứng dụng tuân thủ các tiêu chuẩn bảo mật OWASP dành cho ứng dụng web nội bộ:

1. **Xác thực người dùng & Quản lý phiên (Authentication & Session Hardening):**
   - Màn hình khởi tạo tài khoản Quản trị viên đầu tiên (không sử dụng mật khẩu mặc định gắn cứng trong mã nguồn).
   - Mật khẩu băm bằng thuật toán **PBKDF2-HMAC-SHA256** (310,000 vòng lặp + muối ngẫu nhiên 16 bytes).
   - Cookie phiên thiết lập cờ `HttpOnly`, `SameSite=Strict`, chống đánh cắp qua XSS.
   - Cơ chế chống tấn công **CSRF** (Double-Submit Token `X-CSRF-Token`) trên toàn bộ API ghi dữ liệu.
   - Bộ giới hạn tần suất (**Rate Limiter**) chống dò mật khẩu (Brute-force).
2. **Mã hóa thông tin nhạy cảm khi lưu trữ (Encryption at Rest):**
   - Toàn bộ API Key và OAuth Access Token của từng AI được mã hóa bằng **AES-256 (Fernet)** trước khi lưu vào SQLite.
   - Master Key tự động sinh ngẫu nhiên và lưu tại `data/.master.key` với quyền truy cập hạn chế (`chmod 600`).
   - Giao diện chỉ hiển thị dạng che mờ (`sk-••••••abcd`), không bao giờ ghi lộ khóa vào log.
3. **HTTP Security Headers & Chống tiêm nhiễm:**
   - Thiết lập đầy đủ `Content-Security-Policy (CSP)`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
   - Truy vấn SQL tham số hóa 100% (chống SQL Injection), kiểm tra biên đường dẫn `Path.resolve()` (chống Path Traversal) và thoát ký tự HTML (chống XSS).

---

## 2. Cơ chế Tối ưu Token & Hiệu năng trên từng AI

- **Extractive Context Pruning:** Tự động loại bỏ khoảng trắng thừa, dòng trùng lặp và nhiễu định dạng khi truyền dữ liệu giữa AI 1 → AI 2 → AI 3 → AI 4, giảm **35% – 55%** lượng token đầu vào mà vẫn giữ nguyên thông số kỹ thuật, điều khoản luật và URL.
- **Local Semantic Cache (TTL):** Lưu đệm kết quả tra cứu kỹ thuật và quy định pháp luật theo dấu vân tay ngữ cảnh `SHA-256`. Các truy vấn lặp lại trả về trong `<5ms` với **0 token tiêu thụ**.
- **Hybrid BM25 Local RAG:** Khi nạp tài liệu PDF/DOCX/TXT của hãng vào từng AI, hệ thống chỉ trích xuất Top-K đoạn văn liên quan nhất thay vì đẩy toàn bộ file vào prompt, tiết kiệm tới **70% token**.
- **Per-AI Token Budget & Model Tiering:** Tùy chỉnh giới hạn `max_output_tokens`, mức độ nén (`off`, `balanced`, `aggressive`) và chọn model nhẹ cho tác vụ trích xuất hoặc model suy luận sâu cho kiến trúc/RFP.

---

## 3. Hướng dẫn Chạy Ứng dụng Local

### Cách 1: Chạy trực tiếp bằng Python (Khuyên dùng)
- **Linux / macOS:**
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
- **Windows:**
  Nhấp đúp vào tệp `start.bat` hoặc chạy trong PowerShell:
  ```powershell
  .\start.bat
  ```
Sau đó mở trình duyệt truy cập: **`http://127.0.0.1:8080`**

### Cách 2: Chạy bằng Docker Compose
```bash
docker compose up -d --build
```

---

## 4. Kết nối Model AI (API Key hoặc Đăng nhập trực tiếp)

Mỗi AI (**AI 1**, **AI 2**, **AI 3**, **AI 4**) có thể cấu hình độc lập trong tab **Cấu hình Model & Đăng nhập AI**:
1. **Dùng API Key:** Nhập khóa của **Google Gemini**, **OpenAI**, **Anthropic Claude**, hoặc kết nối **Local Ollama / vLLM** (`http://127.0.0.1:11434`) để chạy offline 100%.
2. **Đăng nhập trực tiếp (Direct Login):**
   - Hỗ trợ **Google Account OAuth 2.0 PKCE** hoặc **Tự động đồng bộ phiên đăng nhập cục bộ (`gcloud auth application-default login`)** để dùng trực tiếp tài khoản Google của bạn mà không cần tạo API Key thủ công.
   - Hỗ trợ nhập nhanh Web Session / Bearer Token cho các cổng AI doanh nghiệp.

---

## 5. Tích hợp WhatsApp Chat thực tế

Ứng dụng cung cấp sẵn endpoint Webhook chính thức tại `/api/whatsapp/webhook` (hỗ trợ xác thực `hub.verify_token` và kiểm tra chữ ký bảo mật `X-Hub-Signature-256` của Meta):
1. Mở đường hầm HTTPS trỏ về cổng local `8080` (ví dụ: `ngrok http 8080` hoặc `cloudflared tunnel --url http://127.0.0.1:8080`).
2. Dán URL `https://<domain-cua-ban>/api/whatsapp/webhook` vào **Meta App Dashboard → WhatsApp → Configuration**.
3. Nhắn tin trực tiếp từ điện thoại với các lệnh: `/research`, `/opportunity`, `/rfp`, `/pitch`, `/status`, `/tokens` hoặc chat tự nhiên.
