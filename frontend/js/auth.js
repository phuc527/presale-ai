import { apiRequest, setCsrfToken, showToast } from "./api.js";

export async function initAuth(onAuthenticated) {
  const statusData = await apiRequest("/api/auth/status");
  const authScreen = document.getElementById("auth-screen");
  const appShell = document.getElementById("app-shell");
  const setupFullnameGroup = document.getElementById("setup-fullname-group");
  const authSubtitle = document.getElementById("auth-subtitle");
  const authSubmitBtn = document.getElementById("auth-submit-btn");
  const authAlert = document.getElementById("auth-alert");

  let isFirstTimeSetup = !statusData.initialized;

  if (statusData.authenticated && statusData.user) {
    setCsrfToken(statusData.user.csrf_token);
    authScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    onAuthenticated(statusData.user);
    return;
  }

  authScreen.classList.remove("hidden");
  appShell.classList.add("hidden");

  if (isFirstTimeSetup) {
    setupFullnameGroup.classList.remove("hidden");
    authSubtitle.textContent = "Khởi tạo tài khoản Quản trị viên (Admin) đầu tiên cho hệ thống cục bộ.";
    authSubmitBtn.textContent = "Tạo tài khoản Admin & Vào hệ thống";
  }

  const form = document.getElementById("auth-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    authAlert.classList.add("hidden");
    const username = document.getElementById("auth-username").value.trim();
    const password = document.getElementById("auth-password").value;
    const fullName = document.getElementById("auth-fullname").value.trim() || username;

    try {
      const endpoint = isFirstTimeSetup ? "/api/auth/setup" : "/api/auth/login";
      const payload = isFirstTimeSetup
        ? { username, full_name: fullName, password, role: "admin" }
        : { username, password };

      const res = await apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setCsrfToken(res.user.csrf_token);
      authScreen.classList.add("hidden");
      appShell.classList.remove("hidden");
      onAuthenticated(res.user);
    } catch (err) {
      authAlert.textContent = err.message;
      authAlert.className = "alert error";
    }
  });

  document.getElementById("btn-logout").addEventListener("click", async () => {
    await apiRequest("/api/auth/logout", { method: "POST" });
    window.location.reload();
  });

  document.getElementById("change-pw-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const current_password = document.getElementById("pw-current").value;
      const new_password = document.getElementById("pw-new").value;
      const res = await apiRequest("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password, new_password }),
      });
      e.target.reset();
      showToast(res.message);
    } catch (err) {
      showToast(err.message, true);
    }
  });
}

export async function loadUsersAdmin(currentUser) {
  const adminCard = document.getElementById("admin-user-card");
  if (currentUser.role !== "admin") {
    adminCard.classList.add("hidden");
    return;
  }
  const userList = document.getElementById("user-list");
  const refreshUsers = async () => {
    const data = await apiRequest("/api/auth/users");
    userList.innerHTML = "";
    data.users.forEach((u) => {
      const div = document.createElement("div");
      div.className = "doc-item";
      const left = document.createElement("div");
      left.textContent = `${u.full_name} (@${u.username}) — Vai trò: ${u.role.toUpperCase()}`;
      const right = document.createElement("span");
      right.className = "badge";
      right.textContent = u.is_active ? "Đang hoạt động" : "Khóa";
      div.append(left, right);
      userList.appendChild(div);
    });
  };
  await refreshUsers();

  document.getElementById("create-user-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const username = document.getElementById("new-username").value.trim();
      const full_name = document.getElementById("new-fullname").value.trim();
      const password = document.getElementById("new-userpass").value;
      const res = await apiRequest("/api/auth/users", {
        method: "POST",
        body: JSON.stringify({ username, full_name, password, role: "presales" }),
      });
      e.target.reset();
      showToast(res.message);
      await refreshUsers();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}
