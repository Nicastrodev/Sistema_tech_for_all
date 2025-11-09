/* ==========================
   CONFIGURAÇÃO BASE
========================== */
// Usa a configuração global do common.js
const API_BASE = window.API_BASE_URL;

/* ==========================
   LOGIN
========================== */
async function doLogin(event) {
  event.preventDefault();
  const email = document.getElementById("email")?.value.trim();
  const password = document.getElementById("password")?.value.trim();
  const role = document.getElementById("roleSelect")?.value;
  const btn = event.target.querySelector("button[type='submit']");

  if (!email || !password || !role)
    return showToast("Preencha todos os campos.", "error");

  btn.disabled = true;
  btn.textContent = "Entrando...";

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role }),
    });
    const data = await res.json();

    if (data.success) {
      localStorage.setItem("tf_user_id", data.user_id);
      localStorage.setItem("tf_role", data.role);
      localStorage.setItem("tf_name", data.name);

      showToast("Login realizado com sucesso!", "success");
      setTimeout(() => {
        if (data.role === "teacher")
          window.location.href = "/dashboard/teacher";
        else window.location.href = "/dashboard/student";
      }, 1000);
    } else {
      showToast(data.message || "Credenciais inválidas", "error");
    }
  } catch (err) {
    console.error("Erro no login:", err);
    showToast("Erro ao conectar com o servidor.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Entrar";
  }
}

/* ==========================
   TURMAS: CRIAR / EDITAR / EXCLUIR
========================== */
async function saveClass(event) {
  event.preventDefault();
  const nome =
    document.getElementById("className")?.value.trim() ||
    document.getElementById("nome")?.value.trim();
  const desc =
    document.getElementById("classDesc")?.value.trim() ||
    document.getElementById("descricao")?.value.trim();
  const turmaId = new URLSearchParams(window.location.search).get("id");

  if (!nome) return showToast("Preencha o nome da turma.", "error");

  const method = turmaId ? "PUT" : "POST";
  const path = turmaId ? `turmas/${turmaId}` : "turmas";

  const data = await apiRequest(path, method, { nome, descricao: desc });
  if (data.success) {
    showToast(
      turmaId ? "Turma atualizada com sucesso!" : "Turma criada com sucesso!",
      "success"
    );
    setTimeout(() => (window.location.href = "/dashboard/teacher"), 1000);
  } else {
    showToast(data.message || "Erro ao salvar turma.", "error");
  }
}

async function deleteClass(turmaId) {
  if (!turmaId) return showToast("Turma inválida.", "error");
  if (!confirm("Tem certeza que deseja excluir esta turma?")) return;

  const data = await apiRequest(`turmas/${turmaId}`, "DELETE");
  if (data.success) {
    showToast("Turma excluída com sucesso!", "success");
    setTimeout(() => window.location.reload(), 1000);
  } else {
    showToast(data.message || "Erro ao excluir turma.", "error");
  }
}

async function editClass() {
  const turmaId = localStorage.getItem("last_turma_id");
  if (!turmaId) return showToast("Nenhuma turma aberta.", "error");
  window.location.href = `/create_class.html?id=${turmaId}`;
}

/* ==========================
   LISTAR TURMAS (Dashboard)
========================== */
async function loadClasses() {
  const s = getSession();
  const list =
    document.querySelector(".class-list") ||
    document.getElementById("teacherClassList") ||
    document.getElementById("classList");

  if (!list) return;

  list.innerHTML =
    "<p style='padding:20px;color:gray;'>Carregando turmas...</p>";

  const data = await apiRequest(`turmas?userId=${s.user_id}&role=${s.role}`);

  if (!data.success) {
    list.innerHTML =
      "<p style='padding:20px;color:red;'>Erro ao carregar turmas.</p>";
    showToast("Erro ao carregar turmas.", "error");
    return;
  }

  if (!data.turmas || !data.turmas.length) {
    list.innerHTML =
      "<p style='padding:20px;color:gray;'>Nenhuma turma encontrada.</p>";
    const total = document.getElementById("totalClasses");
    if (total) total.textContent = "0";
    return;
  }

  list.innerHTML = "";
  const totalClasses = document.getElementById("totalClasses");
  if (totalClasses) totalClasses.textContent = data.turmas.length;

  data.turmas.forEach((t) => {
    const div = document.createElement("div");
    div.className = "class-item";
    div.innerHTML = `
      <div class="class-info" onclick="openClass(${
        t.id
      })" style="cursor:pointer;">
        <h4>${escapeHtml(t.nome)}</h4>
        <p>${escapeHtml(t.descricao || "Sem descrição")}</p>
        <small><b>Código:</b> ${t.codigo_acesso}</small>
      </div>
      <div class="class-actions">
        <button class="btn-outline-small" onclick="openClass(${
          t.id
        })">📂 Abrir</button>
        ${
          s.role === "teacher"
            ? `<button class="btn-outline-small danger" onclick="deleteClass(${t.id})">🗑️ Excluir</button>`
            : ""
        }
      </div>`;
    list.appendChild(div);
  });
}

/* ==========================
   RESUMO DO DASHBOARD PROFESSOR
========================== */
async function loadTeacherDashboardSummary() {
  const s = getSession();
  if (!s || s.role !== "teacher") return;

  try {
    const data = await apiRequest("dashboard/resumo", "GET");
    if (data.success) {
      const elTurmas = document.getElementById("totalTurmas");
      const elAtividades = document.getElementById("totalAtividades");

      if (elTurmas) elTurmas.textContent = data.turmas ?? 0;
      if (elAtividades) elAtividades.textContent = data.atividades ?? 0;
    }
  } catch (err) {
    console.error("Erro ao carregar resumo do dashboard:", err);
  }
}

/* ==========================
   RESUMO DO DASHBOARD ALUNO
========================== */
async function loadStudentDashboardSummary() {
  const s = getSession();
  if (!s || s.role !== "student") return;

  try {
    const data = await apiRequest("dashboard/resumo/aluno", "GET");
    if (data.success) {
      const elPendentes = document.getElementById("atividadesPendentes");
      const elFrequencia = document.getElementById("frequenciaAluno");

      if (elPendentes) elPendentes.textContent = data.pendentes ?? 0;
      if (elFrequencia) elFrequencia.textContent = `${data.frequencia ?? 0}%`;
    }
  } catch (err) {
    console.error("Erro ao carregar resumo do aluno:", err);
  }
}

/* ==========================
   ABRIR TURMA
========================== */
function openClass(turmaId) {
  if (!turmaId) return showToast("ID da turma inválido.", "error");
  localStorage.setItem("last_turma_id", turmaId);
  window.location.href = `/turma.html?id=${turmaId}`;
}

/* ==========================
   INICIALIZAÇÃO AUTOMÁTICA
========================== */
document.addEventListener("DOMContentLoaded", () => {
  const s = getSession();
  const path = window.location.pathname;

  if (path.includes("/dashboard/teacher") && s.role === "teacher") {
    loadClasses();
    loadTeacherDashboardSummary();
  } else if (path.includes("/dashboard/student") && s.role === "student") {
    loadClasses();
    loadStudentDashboardSummary(); // 🔥 exibe frequência e pendências
  }
});

/* ==========================
   EXPORTAÇÃO GLOBAL
========================== */
window.doLogin = doLogin;
window.saveClass = saveClass;
window.deleteClass = deleteClass;
window.editClass = editClass;
window.openClass = openClass;
window.loadClasses = loadClasses;
window.loadTeacherDashboardSummary = loadTeacherDashboardSummary;
window.loadStudentDashboardSummary = loadStudentDashboardSummary;