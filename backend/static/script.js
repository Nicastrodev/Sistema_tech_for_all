/* ==========================
   CONFIGURAÇÃO BASE
========================== */
const API_BASE_URL = `${window.location.origin}/api`;

/* ==========================
   SESSÃO / AUTH
========================== */
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

/* ==========================
   LOGIN
========================== */
async function doLogin(event) {
  event.preventDefault();
  const email = document.getElementById("email")?.value.trim();
  const password = document.getElementById("password")?.value.trim();
  const role = document.getElementById("roleSelect")?.value;

  if (!email || !password || !role)
    return showToast("Preencha todos os campos.", "error");

  try {
    const res = await fetch(`${API_BASE_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role }),
    });
    const data = await res.json();

    if (data.success) {
      setSessionFromLogin(data);
      showToast("Login realizado com sucesso!", "success");

      if (data.role === "teacher")
        window.location.href = "/dashboard_teacher.html";
      else window.location.href = "/dashboard_student.html";
    } else showToast(data.message || "Credenciais inválidas", "error");
  } catch (err) {
    console.error("Erro no login:", err);
    showToast("Erro ao conectar com o servidor.", "error");
  }
}

/* ==========================
   LOGOUT
========================== */
function logout() {
  if (!confirm("Deseja realmente sair?")) return;
  clearSession();
  window.location.href = "/";
}

/* ==========================
   HELPER UNIVERSAL DE FETCH
========================== */
async function apiRequest(path, method = "GET", body = null) {
  const s = getSession();
  const headers = {
    "Content-Type": "application/json",
    "X-User-Id": s.user_id,
    "X-User-Role": s.role,
  };
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, opts);
    return await res.json();
  } catch (e) {
    console.error("Erro API:", e);
    return { success: false, message: "Erro ao conectar com servidor." };
  }
}

/* ==========================
   CRIAR TURMA (PROFESSOR)
========================== */
async function saveClass(event) {
  event.preventDefault();
  const nome = document.getElementById("className").value.trim();
  const desc = document.getElementById("classDesc").value.trim();

  if (!nome) return showToast("Preencha o nome da turma.", "error");

  const s = getSession();
  if (!s.user_id) return showToast("Sessão expirada.", "error");

  const data = await apiRequest("/turmas", "POST", {
    className: nome,
    classDesc: desc,
    userId: s.user_id,
    role: s.role,
  });

  if (data.success) {
    showToast(`Turma criada! Código: ${data.codigo_acesso}`, "success");
    setTimeout(() => (window.location.href = "/dashboard_teacher.html"), 1000);
  } else showToast(data.message, "error");
}

/* ==========================
   ENTRAR EM TURMA (ALUNO)
========================== */
async function joinClassByCode() {
  const code = prompt("Digite o código da turma (5 caracteres):");
  if (!code) return;

  const s = getSession();
  const data = await apiRequest("/turmas/entrar", "POST", {
    codigo: code,
    userId: s.user_id,
    role: s.role,
  });

  if (data.success) {
    showToast(data.message, "success");
    setTimeout(() => window.location.reload(), 800);
  } else showToast(data.message, "error");
}

/* ==========================
   ADICIONAR / REMOVER ALUNO
========================== */
async function addStudentToClass(turmaId) {
  const alunoId = prompt("Digite o ID do aluno a adicionar:");
  if (!alunoId) return;

  const s = getSession();
  const data = await apiRequest(`/turmas/${turmaId}/matricular`, "POST", {
    alunoId,
    userId: s.user_id,
    role: s.role,
  });

  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => window.location.reload(), 800);
}

async function removeStudentFromClass(turmaId, alunoId) {
  if (!confirm("Remover este aluno da turma?")) return;
  const data = await apiRequest(
    `/turmas/${turmaId}/alunos/${alunoId}`,
    "DELETE"
  );
  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => window.location.reload(), 800);
}

/* ==========================
   EXCLUIR TURMA / TAREFA
========================== */
async function deleteClass(turmaId) {
  if (!confirm("Excluir esta turma permanentemente?")) return;
  const data = await apiRequest(`/turmas/${turmaId}`, "DELETE");
  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => window.location.reload(), 800);
}

async function deleteTask(taskId) {
  if (!confirm("Excluir esta tarefa?")) return;
  const data = await apiRequest(`/tarefas/${taskId}`, "DELETE");
  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => window.location.reload(), 800);
}

/* ==========================
   LISTAR TURMAS
========================== */
async function loadClasses() {
  const s = getSession();
  const data = await apiRequest(`/turmas?userId=${s.user_id}&role=${s.role}`);
  const list =
    document.querySelector(".class-list") ||
    document.getElementById("classList");
  if (!list) return;

  list.innerHTML = "";
  if (!data.success || !data.turmas?.length)
    return (list.innerHTML =
      "<p style='padding:20px;color:gray;'>Nenhuma turma encontrada.</p>");

  data.turmas.forEach((t) => {
    const div = document.createElement("div");
    div.className = "class-item";
    div.innerHTML = `
      <div class="class-info">
        <h4>${escapeHtml(t.nome)}</h4>
        <p>${escapeHtml(t.descricao || "Sem descrição")}</p>
        <small><b>Código:</b> ${t.codigo_acesso}</small>
      </div>
      <div class="class-actions">
        ${
          s.role === "teacher"
            ? `
          <button class="btn-outline-small" onclick="addStudentToClass(${t.id})">👥 Adicionar</button>
          <button class="btn-outline-small danger" onclick="deleteClass(${t.id})">🗑️ Excluir</button>`
            : `
          <button class="btn-outline-small" onclick="window.location.href='/turma.html?id=${t.id}'">Abrir</button>
        `
        }
      </div>
    `;
    list.appendChild(div);
  });
}

/* ==========================
   TOAST (alert estilizado)
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
   ESCAPE HTML
========================== */
function escapeHtml(str) {
  if (!str) return "";
  return str.replace(
    /[&<>"']/g,
    (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[
        m
      ])
  );
}

/* ==========================
   INICIALIZAÇÃO
========================== */
document.addEventListener("DOMContentLoaded", () => {
  const s = getSession();
  const path = window.location.pathname;

  if (path.includes("dashboard_teacher") && s.role === "teacher") loadClasses();
  else if (path.includes("dashboard_student") && s.role === "student")
    loadClasses();
});

/* ==========================
   EXPORTAÇÃO GLOBAL
========================== */
window.doLogin = doLogin;
window.logout = logout;
window.saveClass = saveClass;
window.joinClassByCode = joinClassByCode;
window.addStudentToClass = addStudentToClass;
window.removeStudentFromClass = removeStudentFromClass;
window.deleteClass = deleteClass;
window.deleteTask = deleteTask;
