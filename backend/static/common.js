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
   LOGOUT GLOBAL (MODAL BONITO)
========================== */
function logout() {
  showConfirm("Deseja realmente sair da sua conta?", (confirmed) => {
    if (!confirmed) return;
    clearSession();
    showToast("Você saiu da sua conta.", "success");
    setTimeout(() => (window.location.href = "/"), 800);
  });
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
   CONFIRM CUSTOMIZADO BONITO
========================== */
function showConfirm(message, onConfirm) {
  // Evita duplicar
  if (document.querySelector(".confirm-overlay")) return;

  const overlay = document.createElement("div");
  overlay.className = "confirm-overlay";
  overlay.innerHTML = `
    <div class="confirm-box">
      <h3 class="confirm-title">Confirmação</h3>
      <p>${escapeHtml(message)}</p>
      <div class="confirm-actions">
        <button id="confirmYes" class="btn-primary">Sim</button>
        <button id="confirmNo" class="btn-secondary">Cancelar</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  document.getElementById("confirmYes").onclick = () => {
    overlay.remove();
    if (onConfirm) onConfirm(true);
  };
  document.getElementById("confirmNo").onclick = () => {
    overlay.remove();
    if (onConfirm) onConfirm(false);
  };
}

/* ==========================
   ESTILOS DO CONFIRM
========================== */
const confirmStyles = document.createElement("style");
confirmStyles.textContent = `
  .confirm-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .confirm-box {
    background: white;
    padding: 28px 24px;
    border-radius: 14px;
    width: 90%;
    max-width: 360px;
    text-align: center;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.15);
    animation: scaleIn 0.25s ease;
  }
  .confirm-title {
    font-weight: 600;
    color: #4f46e5;
    margin-bottom: 10px;
    font-size: 18px;
  }
  .confirm-box p {
    margin-bottom: 22px;
    color: #333;
    font-size: 15px;
  }
  .confirm-actions {
    display: flex;
    justify-content: center;
    gap: 14px;
  }
  .btn-primary {
    background: #4f46e5;
    color: white;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    cursor: pointer;
    transition: 0.2s;
  }
  .btn-primary:hover {
    background: #4338ca;
    transform: scale(1.05);
  }
  .btn-secondary {
    background: #f3f4f6;
    color: #333;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    cursor: pointer;
    transition: 0.2s;
  }
  .btn-secondary:hover {
    background: #e5e7eb;
    transform: scale(1.05);
  }
  @keyframes scaleIn {
    from { transform: scale(0.9); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }
`;
document.head.appendChild(confirmStyles);

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
window.showConfirm = showConfirm;
