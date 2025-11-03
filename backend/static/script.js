// ================== CONFIGURAÇÃO DA API ==================
const API_BASE_URL = `${window.location.origin}/api`;

/* ================== UTIL / AUTH ================== */
function setSessionFromLogin(apiResponse) {
  localStorage.setItem("tf_user_id", apiResponse.user_id);
  localStorage.setItem("tf_role", apiResponse.role);
  localStorage.setItem("tf_name", apiResponse.name);
}

function clearSession() {
  localStorage.removeItem("tf_user_id");
  localStorage.removeItem("tf_role");
  localStorage.removeItem("tf_name");
}

function getSession() {
  return {
    user_id: localStorage.getItem("tf_user_id"),
    role: localStorage.getItem("tf_role"),
    name: localStorage.getItem("tf_name"),
  };
}

/* ================== LOGIN ================== */
async function doLogin(event) {
  event.preventDefault();
  const emailEl = document.getElementById("email");
  const passwordEl = document.getElementById("password");
  const roleEl = document.getElementById("roleSelect");

  const email = emailEl?.value.trim();
  const password = passwordEl?.value.trim();
  const role = roleEl?.value;

  if (!email || !password || !role) {
    alert("Por favor, preencha todos os campos.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role }),
    });
    const data = await res.json();

    if (data.success) {
      setSessionFromLogin(data);

      // redirecionar para a página correta
      if (data.role === "teacher") window.location.href = "/dashboard/teacher";
      else window.location.href = "/dashboard/student";
    } else {
      alert(data.message || "Credenciais inválidas");
    }
  } catch (err) {
    console.error("Erro no login:", err);
    alert("Erro ao conectar com o servidor.");
  }
}

function presetDemo() {
  document.getElementById("email").value = "demo@techforall.com";
  document.getElementById("password").value = "123456";
}

/* ================== LOGOUT ================== */
function logout() {
  if (!confirm("Deseja realmente sair?")) return;
  clearSession();
  window.location.href = "/";
}

/* ================== HELPERS ================== */
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

/* ================== TURMAS ================== */
async function fetchTurmasApi(userId, role) {
  try {
    const res = await fetch(
      `${API_BASE_URL}/turmas?userId=${userId}&role=${role}`
    );
    if (!res.ok) return { success: false, turmas: [] };
    return await res.json();
  } catch (err) {
    console.error("Erro fetchTurmasApi:", err);
    return { success: false, turmas: [] };
  }
}

async function loadTurmasTeacher() {
  const s = getSession();
  const container = document.querySelector(".class-list");
  if (!container) return;
  container.innerHTML = "";

  if (s.user_id && s.role) {
    const data = await fetchTurmasApi(s.user_id, s.role);
    if (data?.success && data.turmas?.length > 0) {
      data.turmas.forEach((t) => {
        const wrap = document.createElement("div");
        wrap.className = "class-item";
        wrap.innerHTML = `
          <div class="class-info">
            <h4>${escapeHtml(t.nome)}</h4>
            <p>${escapeHtml(
              t.descricao || "Ver alunos • Diário • Atividades"
            )}</p>
          </div>
          <button class="btn-outline-small" onclick="openClass('${
            t.nome
          }')">Abrir</button>
        `;
        container.appendChild(wrap);
      });
      return;
    }
  }

  // fallback (demo)
  ["7º A", "8º B"].forEach((nome) => {
    const wrap = document.createElement("div");
    wrap.className = "class-item";
    wrap.innerHTML = `
      <div class="class-info">
        <h4>${nome}</h4>
        <p>Ver alunos • Diário • Atividades</p>
      </div>
      <button class="btn-outline-small">Abrir</button>
    `;
    container.appendChild(wrap);
  });
}

async function loadTurmasStudent() {
  const s = getSession();
  const container = document.querySelector(".class-list");
  if (!container) return;
  container.innerHTML = "";

  if (s.user_id && s.role) {
    const data = await fetchTurmasApi(s.user_id, s.role);
    if (data?.success && data.turmas?.length > 0) {
      data.turmas.forEach((t) => {
        const wrap = document.createElement("div");
        wrap.className = "class-item";
        wrap.innerHTML = `
          <div class="class-info">
            <h4>${escapeHtml(t.nome)}</h4>
            <p>Ver aulas • Atividades</p>
          </div>
          <button class="btn-outline-small" onclick="openClassStudent('${
            t.nome
          }')">Abrir</button>
        `;
        container.appendChild(wrap);
      });
      return;
    }
  }

  // fallback demo
  ["Português", "Matemática"].forEach((nome) => {
    const wrap = document.createElement("div");
    wrap.className = "class-item";
    wrap.innerHTML = `
      <div class="class-info">
        <h4>${nome}</h4>
        <p>Ver aulas • Atividades</p>
      </div>
      <button class="btn-outline-small">Abrir</button>
    `;
    container.appendChild(wrap);
  });
}

/* ================== CRIAÇÃO DE TURMA ================== */
async function saveClass(event) {
  event.preventDefault();
  const nome = document.getElementById("className")?.value.trim();
  const desc = document.getElementById("classDesc")?.value.trim();

  if (!nome) {
    alert("Por favor, preencha o nome da turma.");
    return;
  }

  const s = getSession();
  if (!s.user_id) {
    alert("Usuário não autenticado.");
    return;
  }

  try {
    const body = { className: nome, classDesc: desc, professorId: s.user_id };
    const res = await fetch(`${API_BASE_URL}/turmas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.success) {
      alert(`Turma "${nome}" criada! Código: ${data.codigo_acesso}`);
      window.location.href = "/dashboard/teacher";
    } else {
      alert(data.message || "Erro ao criar turma.");
    }
  } catch (err) {
    console.error("Erro criar turma:", err);
    alert("Erro ao conectar com o servidor.");
  }
}

/* ================== CHAT IA ================== */
let firstChat = sessionStorage.getItem("firstChat") !== "false";

async function sendChat() {
  const chatInput = document.getElementById("chatInput");
  const chatWindow = document.getElementById("chatWindow");
  const message = (chatInput?.value || "").trim();
  if (!message) return;

  const session = getSession();
  const userName = session.name || "Usuário";

  const userMessage = document.createElement("div");
  userMessage.className = "chat-message";
  userMessage.innerHTML = `<strong>Você:</strong> ${escapeHtml(message)}`;
  chatWindow.appendChild(userMessage);
  chatInput.value = "";

  const typingIndicator = document.createElement("div");
  typingIndicator.className = "chat-message";
  typingIndicator.innerHTML = `<strong>Assistente IA:</strong> <em>Digitando...</em>`;
  chatWindow.appendChild(typingIndicator);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  try {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        user_name: userName,
        first_message: firstChat,
      }),
    });
    const data = await res.json();

    typingIndicator.remove();
    const aiMessage = document.createElement("div");
    aiMessage.className = "chat-message";
    aiMessage.innerHTML = `<strong>Assistente IA:</strong> ${escapeHtml(
      data.response || "⚠️ Erro ao processar resposta."
    )}`;
    chatWindow.appendChild(aiMessage);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    firstChat = false;
    sessionStorage.setItem("firstChat", "false");
  } catch (err) {
    console.error("Erro no chat:", err);
    typingIndicator.remove();
    const errorMessage = document.createElement("div");
    errorMessage.className = "chat-message";
    errorMessage.innerHTML =
      "<strong>Assistente IA:</strong> ⚠️ Erro ao conectar com o servidor.";
    chatWindow.appendChild(errorMessage);
  }
}

/* ================== PLACEHOLDERS ================== */
function openClass(className) {
  alert(`Abrindo painel da turma: ${className} (em breve)`);
}
function openClassStudent(className) {
  alert(`Abrindo turma: ${className} (em breve)`);
}

/* ================== INICIALIZAÇÃO ================== */
document.addEventListener("DOMContentLoaded", () => {
  const s = getSession();
  const path = window.location.pathname;

  // controle de acesso por página
  if (path.includes("/dashboard/teacher")) {
    if (s.role !== "teacher") return (window.location.href = "/");
    loadTurmasTeacher();
  } else if (path.includes("/dashboard/student")) {
    if (s.role !== "student") return (window.location.href = "/");
    loadTurmasStudent();
  }

  const chatInput = document.getElementById("chatInput");
  if (chatInput)
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendChat();
    });
});

/* ================== EXPORTAÇÃO GLOBAL ================== */
window.doLogin = doLogin;
window.presetDemo = presetDemo;
window.logout = logout;
window.saveClass = saveClass;
window.sendChat = sendChat;
