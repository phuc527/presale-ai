import { apiRequest, showToast, updateTelemetryBar } from "./api.js";

const PRESETS = {
  bank: {
    title: "Ngân hàng TMCP — Nâng cấp Hạ tầng Lưu trữ Bất biến & Tuân thủ NĐ 13",
    vendor: "NetApp / Acronis",
    tech: "Immutable Storage & Ransomware Protection",
    industry: "Tài chính Ngân hàng (BFSI)",
    notes: "Khách hàng vận hành Core Banking & Mobile Banking trên 120 VM, SAN cũ sắp EOSL. CIO yêu cầu chống Ransomware tuyệt đối, đáp ứng Nghị định 13/2023/NĐ-CP và Thông tư 12/2022/TT-BTTTT Cấp độ 3, giảm RTO từ 6 giờ xuống dưới 15 phút.",
  },
  factory: {
    title: "Tập đoàn Sản xuất — Hiện đại hóa HCI & Thay thế Hạ tầng Ảo hóa",
    vendor: "HPE / IBM / KVM",
    tech: "Hyper-Converged Infrastructure (HCI) & DR",
    industry: "Sản xuất Công nghiệp",
    notes: "Nhà máy có 3 chi nhánh đang dùng cụm ảo hóa cũ chi phí gia hạn tăng 250%, hệ thống ERP SAP S/4HANA thiếu cơ chế failover tự động khi mất điện cục bộ.",
  },
  hospital: {
    title: "Bệnh viện Đa khoa Hạng I — Hạ tầng Lưu trữ Bệnh án Điện tử EMR & PACS",
    vendor: "NetApp / Dell / HPE",
    tech: "Tiered NVMe + Object Storage & Data Privacy",
    industry: "Y tế & Chăm sóc sức khỏe",
    notes: "Bệnh viện triển khai EMR không giấy tờ và chẩn đoán hình ảnh PACS tăng trưởng 80TB/năm. Cần lưu trữ dữ liệu y tế nhạy cảm theo Nghị định 13/2023/NĐ-CP và truy xuất ảnh DICOM dưới 1 giây.",
  },
};

export function initPipeline() {
  const state = { ai1: "", ai2: "", ai3: "", ai4: "" };

  document.getElementById("preset-select").addEventListener("change", (e) => {
    const p = PRESETS[e.target.value];
    if (!p) return;
    document.getElementById("deal-title").value = p.title;
    document.getElementById("pipe-vendor").value = p.vendor;
    document.getElementById("pipe-tech").value = p.tech;
    document.getElementById("pipe-industry").value = p.industry;
    document.getElementById("customer-notes").value = p.notes;
  });

  document.getElementById("btn-run-stage1").addEventListener("click", async () => {
    const deal_title = document.getElementById("deal-title").value.trim();
    const customer_notes = document.getElementById("customer-notes").value.trim();
    if (!deal_title || !customer_notes) {
      showToast("Vui lòng nhập tên dự án và thông tin khách hàng.", true);
      return;
    }

    document.getElementById("out-ai1").textContent = "AI 1 đang tra cứu tài liệu hãng & khung pháp lý...";
    document.getElementById("out-ai2").textContent = "AI 2 đang phân tích MEDDIC & cơ hội kinh doanh...";
    document.getElementById("meta-ai1").textContent = "Đang chạy...";
    document.getElementById("meta-ai2").textContent = "Đang chạy...";

    try {
      const res = await apiRequest("/api/pipeline/stage1-discovery", {
        method: "POST",
        body: JSON.stringify({
          deal_title,
          customer_notes,
          focus_vendor: document.getElementById("pipe-vendor").value.trim(),
          focus_technology: document.getElementById("pipe-tech").value.trim(),
          focus_industry: document.getElementById("pipe-industry").value.trim(),
        }),
      });

      state.ai1 = res.ai1.output;
      state.ai2 = res.ai2.output;
      document.getElementById("out-ai1").textContent = state.ai1;
      document.getElementById("out-ai2").textContent = state.ai2;
      document.getElementById("meta-ai1").textContent = `${res.ai1.model_name} • ${res.ai1.prompt_tokens + res.ai1.completion_tokens} tok`;
      document.getElementById("meta-ai2").textContent = `${res.ai2.model_name} • ${res.ai2.prompt_tokens + res.ai2.completion_tokens} tok`;
      updateTelemetryBar(res.telemetry);
      showToast("Hoàn tất Bước 1! Hãy rà soát và bấm Bước 2 để xuất Proposal & Slide.");
    } catch (err) {
      showToast(err.message, true);
    }
  });

  document.getElementById("btn-run-stage2").addEventListener("click", async () => {
    if (!state.ai1 || !state.ai2) {
      showToast("Vui lòng chạy Bước 1 (AI 1 + AI 2) trước.", true);
      return;
    }
    document.getElementById("out-ai3").textContent = "AI 3 đang tổng hợp Technical Proposal, RFP Matrix & TCO...";
    document.getElementById("out-ai4").textContent = "AI 4 đang biên soạn Pitch Deck & Kịch bản Demo...";

    try {
      const res = await apiRequest("/api/pipeline/stage2-synthesize", {
        method: "POST",
        body: JSON.stringify({
          deal_title: document.getElementById("deal-title").value.trim(),
          customer_notes: document.getElementById("customer-notes").value.trim(),
          ai1_output: state.ai1,
          ai2_output: state.ai2,
          architect_approval_notes: document.getElementById("architect-notes").value.trim(),
        }),
      });
      state.ai3 = res.ai3.output;
      state.ai4 = res.ai4.output;
      document.getElementById("out-ai3").textContent = state.ai3;
      document.getElementById("out-ai4").textContent = state.ai4;
      document.getElementById("meta-ai3").textContent = `${res.ai3.model_name} • ${res.ai3.prompt_tokens + res.ai3.completion_tokens} tok`;
      document.getElementById("meta-ai4").textContent = `${res.ai4.model_name} • ${res.ai4.prompt_tokens + res.ai4.completion_tokens} tok`;
      updateTelemetryBar(res.telemetry);
      showToast("Hoàn tất toàn bộ dây chuyền 4 AI!");
    } catch (err) {
      showToast(err.message, true);
    }
  });

  document.querySelectorAll(".export-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fmt = btn.dataset.fmt;
      try {
        const response = await apiRequest(`/api/pipeline/export/${fmt}`, {
          method: "POST",
          body: JSON.stringify({
            deal_title: document.getElementById("deal-title").value.trim(),
            ai1_output: state.ai1,
            ai2_output: state.ai2,
            ai3_output: state.ai3,
            ai4_output: state.ai4,
            architect_notes: document.getElementById("architect-notes").value.trim(),
          }),
        });
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Presales_Deliverable.${fmt}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        showToast(`Đã xuất tệp .${fmt} thành công!`);
      } catch (err) {
        showToast(err.message, true);
      }
    });
  });
}
