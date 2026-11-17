let csrfToken = "";

export function setCsrfToken(token) {
  csrfToken = token || "";
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : "";
}

export async function apiRequest(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || "GET").toUpperCase();

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = csrfToken || getCookie("presales_csrf");
    if (token) {
      headers.set("X-CSRF-Token", token);
    }
  }

  const response = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: "same-origin",
  });

  if (!response.ok) {
    let errMsg = `HTTP ${response.status}`;
    try {
      const errData = await response.json();
      errMsg = errData.detail || errMsg;
    } catch (_) {}
    throw new Error(errMsg);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

export function showToast(message, isError = false) {
  const toast = document.getElementById("global-toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = isError ? "toast error" : "toast";
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 4500);
}

export function updateTelemetryBar(telemetry) {
  if (!telemetry) return;
  const usedEl = document.getElementById("tele-used");
  const savedEl = document.getElementById("tele-saved");
  const cacheEl = document.getElementById("tele-cache");
  if (usedEl) usedEl.textContent = Number(telemetry.total_used_tokens || 0).toLocaleString();
  if (savedEl) {
    savedEl.textContent = `${Number(telemetry.total_saved_tokens || 0).toLocaleString()} (${telemetry.savings_percent || 0}%)`;
  }
  if (cacheEl) cacheEl.textContent = Number(telemetry.total_cache_hits || 0).toLocaleString();
}
