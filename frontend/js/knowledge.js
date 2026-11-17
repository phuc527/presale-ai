import { apiRequest, showToast } from "./api.js";

export async function initKnowledgeBase() {
  const docList = document.getElementById("kb-doc-list");

  const renderDocs = async () => {
    const data = await apiRequest("/api/knowledge");
    docList.innerHTML = "";
    if (!data.documents.length) {
      docList.innerHTML = '<div class="muted">Chưa có tài liệu nào trong kho tri thức.</div>';
      return;
    }
    data.documents.forEach((doc) => {
      const item = document.createElement("div");
      item.className = "doc-item";

      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `[${doc.agent_scope.toUpperCase()}] ${doc.title}`;
      const sub = document.createElement("div");
      sub.className = "muted";
      sub.textContent = `Hãng: ${doc.vendor || "Chung"} | Công nghệ: ${doc.technology || "Chung"} | ${doc.chunk_count} đoạn RAG (${doc.source_filename})`;
      info.append(title, sub);

      const delBtn = document.createElement("button");
      delBtn.className = "btn btn-danger btn-sm";
      delBtn.textContent = "Xóa";
      delBtn.addEventListener("click", async () => {
        await apiRequest(`/api/knowledge/${doc.id}`, { method: "DELETE" });
        showToast("Đã xóa tài liệu.");
        await renderDocs();
      });

      item.append(info, delBtn);
      docList.appendChild(item);
    });
  };

  await renderDocs();

  document.getElementById("kb-upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("kb-file");
    if (!fileInput.files.length) return;

    const fd = new FormData();
    fd.append("agent_scope", document.getElementById("kb-scope").value);
    fd.append("title", document.getElementById("kb-title").value.trim());
    fd.append("vendor", document.getElementById("kb-vendor").value.trim());
    fd.append("technology", document.getElementById("kb-tech").value.trim());
    fd.append("domain", document.getElementById("kb-domain").value.trim());
    fd.append("file", fileInput.files[0]);

    try {
      const res = await apiRequest("/api/knowledge/upload", {
        method: "POST",
        body: fd,
      });
      e.target.reset();
      showToast(res.message);
      await renderDocs();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}
