// ================== COMMON.JS - UTILITÁRIOS GLOBAIS ==================

/* ==========================
   CONFIGURAÇÃO BASE
========================== */
// 🔧 Define a base da API globalmente, apenas se ainda não existir
if (typeof window.API_BASE_URL === "undefined") {
  window.API_BASE_URL = `${window.location.origin}/api`;
}

/* ==========================
   SESSÃO E AUTENTICAÇÃO
========================== */
function getSession() {
  return {
    user_id: localStorage.getItem("tf_user_id"),
    role: localStorage.getItem("tf_role"),
    name: localStorage.getItem("tf_name"),
  };
}

function clearSession() {
  ["tf_user_id", "tf_role", "tf_name"].forEach((key) =>
    localStorage.removeItem(key)
  );
}

/* ==========================
   VERIFICAÇÃO DE LOGIN
========================== */
function checkAuth() {
  const s = getSession();
  const path = window.location.pathname;

  // Páginas públicas (sem login)
  const publicPages = ["/", "/index.html"];
  const isPublic = publicPages.some((p) => path.endsWith(p) || path === p);

  // Bloqueia acesso a áreas restritas
  if (!s.user_id && !isPublic) {
    console.warn("Acesso negado - redirecionando para login...");
    window.location.href = "/";
    return false;
  }

  // Controle por tipo de usuário
  if (path.includes("/dashboard/teacher") && s.role !== "teacher") {
    console.warn("Somente professores podem acessar esta página.");
    window.location.href = "/";
    return false;
  }

  if (path.includes("/dashboard/student") && s.role !== "student") {
    console.warn("Somente alunos podem acessar esta página.");
    window.location.href = "/";
    return false;
  }

  return true;
}

/* ==========================
   LOGOUT GLOBAL
========================== */
function logout() {
  if (!confirm("Deseja realmente sair da sua conta?")) return;
  clearSession();
  window.location.href = "/";
}

/* ==========================
   TOAST BONITO
========================== */
function showToast(msg, type = "info") {
  let box = document.querySelector(".toast-box");
  if (!box) {
    box = document.createElement("div");
    box.className = "toast-box";
    document.body.appendChild(box);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  box.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 400);
  }, 2500);
}

/* ==========================
   API REQUEST UNIVERSAL
========================== */
async function apiRequest(
  path,
  method = "GET",
  body = null,
  includeAuth = true
) {
  const headers = { "Content-Type": "application/json" };

  if (includeAuth) {
    const s = getSession();
    if (s.user_id) headers["X-User-Id"] = s.user_id;
    if (s.role) headers["X-User-Role"] = s.role;
  }

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  // ✅ Remove / duplicadas
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;

  try {
    const res = await fetch(`${window.API_BASE_URL}/${cleanPath}`, opts);
    if (!res.ok) {
      console.error("Erro HTTP:", res.status);
      return { success: false, message: `Erro HTTP ${res.status}` };
    }

    const data = await res.json().catch(() => ({}));
    return data;
  } catch (e) {
    console.error("Erro API:", e);
    return { success: false, message: "Erro ao conectar com o servidor." };
  }
}

/* ==========================
   HELPERS
========================== */
function escapeHtml(text) {
  if (!text) return "";
  return String(text).replace(/[&<>"'`=\/]/g, (s) => {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
      "/": "&#x2F;",
      "`": "&#x60;",
      "=": "&#x3D;",
    }[s];
  });
}

function formatDate(dateString) {
  if (!dateString) return "";
  const d = new Date(dateString + "T00:00:00");
  return d.toLocaleDateString("pt-BR");
}

/* ==========================
   EXECUÇÃO AUTOMÁTICA
========================== */
document.addEventListener("DOMContentLoaded", () => {
  const s = getSession();

  // Bloqueia acesso não autorizado
  checkAuth();

  // Se for visitante, não continua
  if (!s.user_id) return;

  // Atualiza informações do topo
  const roleBadge = document.getElementById("currentRole");
  if (roleBadge) {
    roleBadge.textContent =
      s.role === "teacher"
        ? "Professor"
        : s.role === "student"
        ? "Aluno"
        : "Visitante";
  }

  const welcomeEl = document.getElementById("welcomeName");
  if (welcomeEl) welcomeEl.textContent = `Olá, ${s.name || "Usuário"} 👋`;

  const welcomeEl2 = document.getElementById("welcomeNameStudent");
  if (welcomeEl2) welcomeEl2.textContent = `Olá, ${s.name || "Usuário"} 👋`;
});

/* ==========================
   EXPORTAÇÃO GLOBAL
========================== */
window.getSession = getSession;
window.clearSession = clearSession;
window.checkAuth = checkAuth;
window.logout = logout;
window.showToast = showToast;
window.apiRequest = apiRequest;
window.escapeHtml = escapeHtml;
window.formatDate = formatDate;
