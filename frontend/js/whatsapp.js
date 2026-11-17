import { apiRequest, showToast, updateTelemetryBar } from "./api.js";

export async function initWhatsAppBridge() {
  const chatBox = document.getElementById("wa-chat-box");
  const logList = document.getElementById("wa-log-list");

  const appendBubble = (text, isInbound) => {
    const div = document.createElement("div");
    div.className = isInbound ? "wa-msg wa-in" : "wa-msg wa-out";
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  };

  const refreshLogs = async () => {
    const data = await apiRequest("/api/whatsapp/logs");
    logList.innerHTML = "";
    data.logs.forEach((l) => {
      const item = document.createElement("div");
      item.className = "doc-item";
      item.textContent = `[${l.direction.toUpperCase()} | ${l.command}] ${l.sender}: ${l.message_text.slice(0, 90)}...`;
      logList.appendChild(item);
    });
  };

  appendBubble("Xin chào! Gõ /research, /opportunity, /rfp, /pitch hoặc /tokens để điều khiển đội AI từ WhatsApp.", false);
  await refreshLogs();

  document.getElementById("wa-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("wa-input");
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    appendBubble(msg, true);

    try {
      const res = await apiRequest("/api/whatsapp/simulate", {
        method: "POST",
        body: JSON.stringify({ message: msg }),
      });
      appendBubble(res.result.reply, false);
      updateTelemetryBar(res.telemetry);
      await refreshLogs();
    } catch (err) {
      appendBubble(`Lỗi: ${err.message}`, false);
      showToast(err.message, true);
    }
  });
}
