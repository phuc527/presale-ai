import re
from datetime import datetime
from pathlib import Path
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from docx import Document
from pptx import Presentation
from pptx.util import Pt
from backend.config import EXPORTS_DIR


def _safe_slug(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip())[:50].strip("_")
    return slug or "Presales_Deliverable"


def export_excel_deliverable(
    deal_title: str,
    ai1_output: str,
    ai2_output: str,
    ai3_output: str,
    architect_notes: str,
) -> Path:
    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "RFP_Compliance_Matrix"
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["STT", "Hạng mục Kỹ thuật / Tuân thủ", "Mức độ Đáp ứng", "Giải pháp & Tham chiếu Tài liệu", "Ghi chú Kiến trúc sư"]
    ws1.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    lines = [ln.strip("-*# ").strip() for ln in (ai3_output or ai1_output).splitlines() if len(ln.strip()) > 12][:20]
    if not lines:
        lines = [
            "Kiến trúc High Availability & Zero-RPO Replication",
            "Sao lưu bất biến Immutable WORM chống Ransomware",
            "Tuân thủ Nghị định 13/2023/NĐ-CP & Thông tư 12/2022/TT-BTTTT",
        ]

    for idx, line in enumerate(lines, start=1):
        ws1.append([idx, line[:120], "Đáp ứng hoàn toàn (Fully Comply)", line, architect_notes[:100] or "Đã thẩm định bởi Pre-sales"])

    for col, width in zip(["A", "B", "C", "D", "E"], [8, 42, 26, 55, 32]):
        ws1.column_dimensions[col].width = width

    ws2 = wb.create_sheet(title="TCO_ROI_3_Years")
    ws2.append(["Hạng mục Chi phí / Lợi ích (USD)", "Hệ thống Hiện tại (Legacy)", "Giải pháp Đề xuất", "Chênh lệch Tiết kiệm"])
    for col_idx in range(1, 5):
        c = ws2.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font

    rows_data = [
        ("Đầu tư Phần cứng & Bản quyền (CAPEX - Năm 1)", 140000, 165000),
        ("Chi phí Vận hành, Điện năng & Rack (OPEX - 3 năm)", 96000, 54000),
        ("Chi phí Bảo trì & Gia hạn Support (Năm 2-3)", 68000, 42000),
        ("Rủi ro Gián đoạn & Khắc phục Sự cố (Ước tính 3 năm)", 120000, 15000),
    ]
    for r_idx, (label, legacy_val, new_val) in enumerate(rows_data, start=2):
        ws2.append([label, legacy_val, new_val, f"=B{r_idx}-C{r_idx}"])

    ws2.append(["TỔNG CHI PHÍ SỞ HỮU 3 NĂM (3-YEAR TCO)", "=SUM(B2:B5)", "=SUM(C2:C5)", "=B6-C6"])
    for col_idx in range(1, 5):
        ws2.cell(row=6, column=col_idx).font = Font(bold=True)
    for row_num in range(2, 7):
        for col_num in range(2, 5):
            ws2.cell(row=row_num, column=col_num).number_format = "#,##0"

    for col, width in zip(["A", "B", "C", "D"], [48, 24, 24, 24]):
        ws2.column_dimensions[col].width = width

    ws3 = wb.create_sheet(title="MEDDIC_Discovery")
    ws3.append(["Phân tích Hiện trạng & Cơ hội Mở rộng (AI 2)"])
    ws3.cell(row=1, column=1).font = Font(bold=True, size=12)
    ws3.append([ai2_output or "Chưa có dữ liệu phân tích."])
    ws3.column_dimensions["A"].width = 100

    filename = f"{_safe_slug(deal_title)}_Compliance_TCO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    out_path = EXPORTS_DIR / filename
    wb.save(out_path)
    return out_path


def export_word_proposal(
    deal_title: str,
    ai1_output: str,
    ai2_output: str,
    ai3_output: str,
    architect_notes: str,
) -> Path:
    doc = Document()
    doc.add_heading(f"ĐỀ XUẤT GIẢI PHÁP KỸ THUẬT: {deal_title}", level=0)
    doc.add_paragraph(f"Ngày lập: {datetime.now().strftime('%d/%m/%Y')} | Tài liệu Pre-sales Giải pháp Doanh nghiệp")

    doc.add_heading("1. Tóm tắt Bài toán & Cơ hội Kinh doanh (Discovery & MEDDIC)", level=1)
    doc.add_paragraph(ai2_output or "Đang cập nhật phân tích hiện trạng.")

    doc.add_heading("2. Cơ sở Kỹ thuật & Tuân thủ Pháp lý (Tech & Compliance)", level=1)
    doc.add_paragraph(ai1_output or "Đang cập nhật thông số kỹ thuật.")

    if architect_notes.strip():
        doc.add_heading("3. Định hướng Chốt duyệt của Kiến trúc sư Giải pháp", level=1)
        doc.add_paragraph(architect_notes.strip())

    doc.add_heading("4. Kiến trúc Giải pháp Đề xuất, Đáp ứng RFP & Hiệu quả Đầu tư", level=1)
    doc.add_paragraph(ai3_output or "Đang cập nhật chi tiết giải pháp.")

    filename = f"{_safe_slug(deal_title)}_Technical_Proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    out_path = EXPORTS_DIR / filename
    doc.save(out_path)
    return out_path


def export_pptx_deck(
    deal_title: str,
    ai2_output: str,
    ai3_output: str,
    ai4_output: str,
) -> Path:
    prs = Presentation()
    title_slide_layout = prs.slide_layouts[0]
    bullet_layout = prs.slide_layouts[1]

    s1 = prs.slides.add_slide(title_slide_layout)
    s1.shapes.title.text = deal_title
    s1.placeholders[1].text = "Giải pháp Hạ tầng, An ninh mạng & Tuân thủ Doanh nghiệp\nExecutive & Technical Pitch Deck"

    sections = [
        ("Thách thức Hiện trạng & Rủi ro Kinh doanh", ai2_output),
        ("Kiến trúc Giải pháp & Lợi ích Định lượng (ROI)", ai3_output),
        ("Thông điệp Giá trị C-Level & Lộ trình POC/Demo", ai4_output),
    ]
    for heading, body in sections:
        slide = prs.slides.add_slide(bullet_layout)
        slide.shapes.title.text = heading
        tf = slide.placeholders[1].text_frame
        tf.clear()
        clean_lines = [ln.strip("-*# ").strip() for ln in (body or "").splitlines() if ln.strip()][:6]
        if not clean_lines:
            clean_lines = ["Đang tổng hợp nội dung trình bày."]
        for idx, line in enumerate(clean_lines):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.text = line[:160]
            p.font.size = Pt(16)

    filename = f"{_safe_slug(deal_title)}_Pitch_Deck_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
    out_path = EXPORTS_DIR / filename
    prs.save(out_path)
    return out_path
