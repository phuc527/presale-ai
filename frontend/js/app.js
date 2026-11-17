import { initAgentsManager } from "./agents.js";
import { initAuth, loadUsersAdmin } from "./auth.js";
import { initKnowledgeBase } from "./knowledge.js";
import { initPipeline } from "./pipeline.js";
import { initWhatsAppBridge } from "./whatsapp.js";

function setupTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  const panels = document.querySelectorAll(".tab-panel");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const target = document.getElementById(`tab-${tab.dataset.tab}`);
      if (target) target.classList.add("active");
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  await initAuth(async (user) => {
    document.getElementById("current-user-badge").textContent = `${user.full_name} (${user.role.toUpperCase()})`;
    initPipeline();
    await Promise.all([
      initAgentsManager(),
      initKnowledgeBase(),
      initWhatsAppBridge(),
      loadUsersAdmin(user),
    ]);
  });
});
