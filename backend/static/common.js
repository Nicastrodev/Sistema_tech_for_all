// ================== COMMON.JS - UTILITÁRIOS GLOBAIS ==================

// ------------------ SESSÃO E AUTENTICAÇÃO ------------------
function getSession() {
  return {
    user_id: localStorage.getItem("tf_user_id"),
    role: localStorage.getItem("tf_role"),
    name: localStorage.getItem("tf_name"),
  };
}

function clearSession() {
  localStorage.removeItem("tf_user_id");
  localStorage.removeItem("tf_role");
  localStorage.removeItem("tf_name");
}

// ------------------ VERIFICAÇÃO DE LOGIN ------------------
function checkAuth() {
  const s = getSession();
  const path = window.location.pathname;

  // páginas públicas (não exigem login)
  const publicPages = ["/", "/index.html"];
  const isPublic = publicPages.some((p) => path.endsWith(p) || path === p);

  // se não estiver logado e não for página pública → redireciona
  if (!s.user_id && !isPublic) {
    console.warn("Acesso negado - redirecionando para login...");
    window.location.href = "/";
    return false;
  }

  // controle de acesso por role
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

// ------------------ LOGOUT GLOBAL ------------------
function logout() {
  if (!confirm("Deseja realmente sair da sua conta?")) return;
  clearSession();
  window.location.href = "/";
}

// ------------------ HELPERS ------------------
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

// ------------------ EXECUÇÃO AUTOMÁTICA ------------------
document.addEventListener("DOMContentLoaded", () => {
  // bloqueia acesso não autorizado
  checkAuth();

  // insere nome do usuário no topo, se disponível
  const s = getSession();
  const roleBadge = document.getElementById("currentRole");
  if (roleBadge) {
    if (s.role === "teacher") roleBadge.textContent = "Professor";
    else if (s.role === "student") roleBadge.textContent = "Aluno";
    else roleBadge.textContent = "Visitante";
  }

  const welcomeEl = document.getElementById("welcomeName");
  if (welcomeEl) welcomeEl.textContent = `Olá, ${s.name || "Usuário"} 👋`;

  const welcomeEl2 = document.getElementById("welcomeNameStudent");
  if (welcomeEl2) welcomeEl2.textContent = `Olá, ${s.name || "Usuário"} 👋`;
});

// ------------------ EXPORTAÇÃO GLOBAL ------------------
window.getSession = getSession;
window.clearSession = clearSession;
window.checkAuth = checkAuth;
window.logout = logout;
window.escapeHtml = escapeHtml;
window.formatDate = formatDate;
