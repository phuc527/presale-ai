import { apiRequest, showToast, updateTelemetryBar } from "./api.js";

export async function initAgentsManager() {
  const container = document.getElementById("agent-config-list");

  const renderAgents = async () => {
    const data = await apiRequest("/api/agents");
    updateTelemetryBar(data.telemetry);
    const catalog = data.catalog;
    container.innerHTML = "";

    data.agents.forEach((agent) => {
      const card = document.createElement("div");
      card.className = "card";

      const header = document.createElement("div");
      header.className = "card-header";
      const h3 = document.createElement("h3");
      h3.textContent = agent.name;
      const badge = document.createElement("span");
      badge.className = "badge badge-success";
      badge.textContent = `${agent.provider.toUpperCase()} • ${agent.model_name}`;
      header.append(h3, badge);

      const form = document.createElement("form");
      form.innerHTML = `
        <div class="grid-3">
          <div class="form-group">
            <label>Nhà cung cấp AI</label>
            <select name="provider">
              <option value="gemini" ${agent.provider === "gemini" ? "selected" : ""}>Google Gemini</option>
              <option value="openai" ${agent.provider === "openai" ? "selected" : ""}>OpenAI</option>
              <option value="anthropic" ${agent.provider === "anthropic" ? "selected" : ""}>Anthropic Claude</option>
              <option value="ollama" ${agent.provider === "ollama" ? "selected" : ""}>Local Ollama (Offline)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Model AI</label>
            <input type="text" name="model_name" list="models-${agent.agent_key}" value="${agent.model_name}" required />
            <datalist id="models-${agent.agent_key}">
              ${(catalog[agent.provider] || []).map((m) => `<option value="${m}"></option>`).join("")}
            </datalist>
          </div>
          <div class="form-group">
            <label>Cách kết nối</label>
            <select name="auth_mode">
              <option value="api_key" ${agent.auth_mode === "api_key" ? "selected" : ""}>Dùng API Key (Mã hóa AES)</option>
              <option value="oauth_login" ${agent.auth_mode === "oauth_login" ? "selected" : ""}>Đăng nhập trực tiếp (OAuth/ADC)</option>
              <option value="local_none" ${agent.auth_mode === "local_none" ? "selected" : ""}>Local không cần khóa</option>
            </select>
          </div>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label>API Key mới ${agent.has_api_key ? `(Đã lưu: ${agent.masked_api_key})` : "(Chưa lưu)"}</label>
            <input type="password" name="api_key" placeholder="Nhập để cập nhật khóa mới..." autocomplete="off" />
          </div>
          <div class="form-group">
            <label>OAuth / Session Token ${agent.has_oauth_token ? `(${agent.oauth_account_email || "Đã kết nối"})` : ""}</label>
            <input type="password" name="oauth_token" placeholder="Dán token phiên hoặc bấm Đồng bộ Google..." autocomplete="off" />
          </div>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label>Hãng công nghệ chuyên sâu (phân tách dấu phẩy)</label>
            <input type="text" name="vendors" value="${agent.vendors.join(", ")}" />
          </div>
          <div class="form-group">
            <label>Mảng công nghệ đào sâu (phân tách dấu phẩy)</label>
            <input type="text" name="technologies" value="${agent.technologies.join(", ")}" />
          </div>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label>Lĩnh vực / Ngành nghề mục tiêu</label>
            <input type="text" name="industries" value="${agent.industries.join(", ")}" />
          </div>
          <div class="form-group">
            <label>Khung tuân thủ / Phương pháp luận</label>
            <input type="text" name="frameworks" value="${agent.frameworks.join(", ")}" />
          </div>
        </div>

        <div class="grid-3">
          <div class="form-group">
            <label>Mức độ đào sâu mặc định</label>
            <select name="depth_level">
              <option value="executive" ${agent.depth_level === "executive" ? "selected" : ""}>Executive Brief</option>
              <option value="architect" ${agent.depth_level === "architect" ? "selected" : ""}>Solution Architect (HLD)</option>
              <option value="deep_engineering" ${agent.depth_level === "deep_engineering" ? "selected" : ""}>Deep Engineering & Audit</option>
            </select>
          </div>
          <div class="form-group">
            <label>Nén ngữ cảnh (Tiết kiệm Token)</label>
            <select name="compression_level">
              <option value="off" ${agent.compression_level === "off" ? "selected" : ""}>Tắt nén</option>
              <option value="balanced" ${agent.compression_level === "balanced" ? "selected" : ""}>Cân bằng (Giữ nguyên số liệu)</option>
              <option value="aggressive" ${agent.compression_level === "aggressive" ? "selected" : ""}>Tối đa (Tiết kiệm 45%+)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Giới hạn Output Tokens</label>
            <input type="number" name="max_output_tokens" min="256" max="8192" value="${agent.max_output_tokens}" />
          </div>
        </div>

        <div class="form-group">
          <label>System Prompt cốt lõi</label>
          <textarea name="system_prompt" rows="3" required>${agent.system_prompt}</textarea>
        </div>

        <div class="btn-row">
          <button type="submit" class="btn btn-primary btn-sm">Lưu cấu hình ${agent.agent_key.toUpperCase()}</button>
          <button type="button" class="btn btn-outline btn-sm btn-sync-google">Đồng bộ Đăng nhập Google (ADC)</button>
          <label class="checkbox-inline">
            <input type="checkbox" name="cache_enabled" ${agent.cache_enabled ? "checked" : ""} /> Bật Semantic Cache (0 token khi lặp lại)
          </label>
        </div>
      `;

      form.querySelector(".btn-sync-google").addEventListener("click", async () => {
        try {
          const res = await apiRequest(`/api/agents/${agent.agent_key}/sync-local-login`, { method: "POST" });
          showToast(res.message);
          await renderAgents();
        } catch (err) {
          showToast(err.message, true);
        }
      });

      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const splitCsv = (val) => String(val || "").split(",").map((s) => s.trim()).filter(Boolean);
        const payload = {
          provider: fd.get("provider"),
          model_name: fd.get("model_name"),
          auth_mode: fd.get("auth_mode"),
          api_key: fd.get("api_key") || null,
          oauth_token: fd.get("oauth_token") || null,
          vendors: splitCsv(fd.get("vendors")),
          technologies: splitCsv(fd.get("technologies")),
          industries: splitCsv(fd.get("industries")),
          frameworks: splitCsv(fd.get("frameworks")),
          depth_level: fd.get("depth_level"),
          compression_level: fd.get("compression_level"),
          max_output_tokens: Number(fd.get("max_output_tokens") || 1600),
          cache_enabled: form.querySelector('input[name="cache_enabled"]').checked,
          temperature: agent.temperature,
          system_prompt: fd.get("system_prompt"),
        };

        try {
          const res = await apiRequest(`/api/agents/${agent.agent_key}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast(res.message);
          await renderAgents();
        } catch (err) {
          showToast(err.message, true);
        }
      });

      card.append(header, form);
      container.appendChild(card);
    });
  };

  await renderAgents();

  document.getElementById("btn-run-standalone").addEventListener("click", async () => {
    const agentKey = document.getElementById("sa-agent").value;
    const prompt = document.getElementById("sa-prompt").value.trim();
    if (!prompt) {
      showToast("Vui lòng nhập nội dung câu hỏi hoặc yêu cầu.", true);
      return;
    }
    const outBox = document.getElementById("sa-output");
    const metaChip = document.getElementById("sa-meta");
    outBox.textContent = "Đang xử lý truy vấn với bộ tối ưu Token & Local RAG...";
    metaChip.textContent = "Đang chạy...";

    try {
      const data = await apiRequest(`/api/agents/${agentKey}/run`, {
        method: "POST",
        body: JSON.stringify({
          prompt,
          focus_vendor: document.getElementById("sa-vendor").value.trim(),
          focus_technology: document.getElementById("sa-tech").value.trim(),
          depth_override: document.getElementById("sa-depth").value,
          bypass_cache: document.getElementById("sa-bypass-cache").checked,
        }),
      });
      const r = data.result;
      outBox.textContent = r.output;
      metaChip.textContent = r.cache_hit
        ? `CACHE HIT • 0 token • ${r.latency_ms}ms`
        : `${r.model_name} • ${r.prompt_tokens + r.completion_tokens} tok (tiết kiệm ${r.saved_tokens}) • ${r.latency_ms}ms`;
      updateTelemetryBar(data.telemetry);
    } catch (err) {
      outBox.textContent = `Lỗi: ${err.message}`;
      metaChip.textContent = "Lỗi thực thi";
      showToast(err.message, true);
    }
  });
}
