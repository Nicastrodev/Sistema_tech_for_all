/* ==========================
   CONFIGURAÇÃO BASE
========================== */
const API_BASE_URL = window.API_BASE_URL || `${window.location.origin}/api`;

/* ==========================
   HELPERS
========================== */
// (getSession, escapeHtml, showToast, apiRequest, logout — vêm de common.js)
function getQueryParam(param) {
  return new URLSearchParams(window.location.search).get(param);
}

/* ==========================
   CARREGAR TURMA (CORRIGIDA)
========================== */
async function loadTurma() {
  const turmaId = getQueryParam("id") || localStorage.getItem("last_turma_id");
  const s = getSession();

  if (!turmaId) {
    showToast("Nenhuma turma encontrada. Redirecionando...", "error");
    return setTimeout(() => {
      window.location.href =
        s?.role === "student" ? "/dashboard/student" : "/dashboard/teacher";
    }, 2000);
  }

  localStorage.setItem("last_turma_id", turmaId);

  try {
    const data = await apiRequest(`turmas/${turmaId}`, "GET");

    if (!data.success || !data.turma) {
      console.warn("Erro ao carregar turma:", data);
      showToast(data.message || "Erro ao carregar turma.", "error");
      return;
    }

    const turma = data.turma;

    // Função auxiliar para evitar erro caso o elemento não exista
    const setText = (id, text) => {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    };

    setText("breadcrumbClassName", turma.nome);
    setText("className", turma.nome);
    setText("classNameDetail", turma.nome);
    setText("classDescription", turma.descricao || "Sem descrição");
    setText("classCode", turma.codigo_acesso || "-----");

    // Atualiza dados estatísticos
    const total = turma.total_alunos || 0;
    setText("totalStudents", total);
    setText("averageGrade", (turma.media_geral || 0).toFixed(1));
    setText("averageAttendance", (turma.frequencia_media || 0) + "%");

    // Atualiza papel no header
    const roleBadge = document.getElementById("currentRole");
    if (roleBadge) {
      roleBadge.textContent =
        s?.role === "teacher"
          ? "Professor"
          : s?.role === "student"
          ? "Aluno"
          : "Visitante";
    }

    // Carrega alunos da turma
    await loadAlunos(turmaId);
  } catch (err) {
    console.error("Erro ao carregar turma:", err);
    showToast("Erro ao conectar com o servidor.", "error");
  }
}

/* ==========================
   CARREGAR ALUNOS
========================== */
async function loadAlunos(turmaId) {
  const tbody = document.getElementById("studentsTableBody");
  if (!tbody) return;
  tbody.innerHTML = `
    <tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-secondary)">
      Carregando alunos...
    </td></tr>`;

  try {
    const data = await apiRequest(`turmas/${turmaId}/alunos`, "GET");
    const s = getSession();
    const isTeacher = s && s.role === "teacher";

    if (!data.success) {
      tbody.innerHTML = `<tr><td colspan="5" style="color:red;text-align:center;">${data.message}</td></tr>`;
      return;
    }

    if (!data.alunos || data.alunos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-secondary)">
        Nenhum aluno encontrado nesta turma.
      </td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    let aprovados = 0,
      recuperacao = 0,
      reprovados = 0;

    data.alunos.forEach((a) => {
      const media = a.media ?? 0;
      const frequencia = a.frequencia ?? 0;

      let status = "danger";
      if (media >= 7) {
        status = "success";
        aprovados++;
      } else if (media >= 5) {
        status = "warning";
        recuperacao++;
      } else {
        reprovados++;
      }

      const tr = document.createElement("tr");

      // 🔒 Se for aluno, não mostra botão "Remover"
      const actionsColumn = isTeacher
        ? `<td><button class="btn-outline-small danger" onclick="removeAluno(${a.id})">Remover</button></td>`
        : "";

      tr.innerHTML = `
        <td>${escapeHtml(a.nome)}</td>
        <td>${escapeHtml(a.email)}</td>
        <td>${frequencia}%</td>
        <td class="${status}">${media.toFixed(1)}</td>
        ${actionsColumn}`;
      tbody.appendChild(tr);
    });

    // Atualiza estatísticas apenas se professor
    if (isTeacher) {
      const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
      };
      setText("approvedCount", aprovados);
      setText("recoveryCount", recuperacao);
      setText("failedCount", reprovados);
    }
  } catch (err) {
    console.error("Erro ao carregar alunos:", err);
    tbody.innerHTML = `<tr><td colspan="5" style="color:red;text-align:center;">
      Erro ao carregar alunos.
    </td></tr>`;
  }
}

/* ==========================
   AÇÕES DE PROFESSOR
========================== */
async function addStudent() {
  const s = getSession();
  if (!s || s.role !== "teacher") {
    return showToast("Apenas professores podem adicionar alunos.", "error");
  }

  const turmaId = localStorage.getItem("last_turma_id");
  const alunoId = prompt("Digite o ID do aluno para adicionar:");
  if (!alunoId) return;

  const data = await apiRequest(`turmas/${turmaId}/adicionar_aluno`, "POST", {
    alunoId,
  });

  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => loadAlunos(turmaId), 1000);
}

async function removeAluno(alunoId) {
  const s = getSession();
  if (!s || s.role !== "teacher") {
    return showToast("Apenas professores podem remover alunos.", "error");
  }

  const turmaId = localStorage.getItem("last_turma_id");
  if (!confirm("Deseja remover este aluno da turma?")) return;

  const data = await apiRequest(`turmas/${turmaId}/aluno/${alunoId}`, "DELETE");
  showToast(data.message, data.success ? "success" : "error");
  if (data.success) setTimeout(() => loadAlunos(turmaId), 1000);
}

function editClass() {
  const s = getSession();
  if (!s) {
    return showToast("Sessão expirada. Faça login novamente.", "error");
  }

  const turmaId = localStorage.getItem("last_turma_id");
  if (!turmaId) {
    return showToast("Nenhuma turma ativa encontrada.", "error");
  }

  // ✅ Redireciona diretamente para a página de edição
  window.location.href = `/create_class?id=${turmaId}`;
}

async function deleteClass() {
  const s = getSession();
  if (!s || s.role !== "teacher") {
    return showToast("Apenas professores podem excluir turmas.", "error");
  }

  const turmaId = localStorage.getItem("last_turma_id");
  if (!turmaId) return showToast("Nenhuma turma ativa.", "error");

  if (
    !confirm(
      "Tem certeza que deseja excluir esta turma? Essa ação não pode ser desfeita."
    )
  )
    return;

  const data = await apiRequest(`turmas/${turmaId}`, "DELETE", {
    userId: s.user_id,
    role: s.role,
  });

  if (data.success) {
    showToast("Turma excluída com sucesso!", "success");
    localStorage.removeItem("last_turma_id");
    setTimeout(() => (window.location.href = "/dashboard/teacher"), 1500);
  } else {
    console.warn("Erro ao excluir turma:", data);
    showToast(data.message || "Erro ao excluir turma.", "error");
  }
}

/* ==========================
   RELATÓRIO / EXPORTAÇÃO
========================== */
async function generateReport() {
  const s = getSession();
  if (!s || s.role !== "teacher") {
    return showToast("Apenas professores podem gerar relatórios.", "error");
  }

  const turmaId = localStorage.getItem("last_turma_id");
  if (!turmaId) return showToast("Nenhuma turma ativa.", "error");

  showToast("Gerando relatório...", "info");
  try {
    const data = await apiRequest(`relatorios/turma/${turmaId}/pdf`, "GET");
    if (data.success && data.pdf_url) {
      showToast("Relatório gerado com sucesso!", "success");
      window.open(data.pdf_url, "_blank");
    } else {
      showToast(data.message || "Erro ao gerar relatório.", "error");
    }
  } catch (err) {
    console.error("Erro ao gerar relatório:", err);
    showToast("Erro ao gerar relatório. Verifique o servidor.", "error");
  }
}

function exportStudents() {
  const s = getSession();
  if (!s || s.role !== "teacher") {
    return showToast("Apenas professores podem exportar listas.", "error");
  }

  const rows = [["Nome", "Email", "Frequência", "Média"]];
  document.querySelectorAll("#studentsTableBody tr").forEach((tr) => {
    const cols = Array.from(tr.children)
      .slice(0, 4)
      .map((td) => td.textContent.trim());
    if (cols.length) rows.push(cols);
  });

  const csv = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "alunos_turma.csv";
  a.click();

  showToast("Lista exportada com sucesso!", "success");
}

/* ==========================
   FILTRO / CÓDIGO / OUTROS
========================== */
function filterStudents() {
  const query =
    document.getElementById("searchStudent")?.value.toLowerCase().trim() || "";
  document.querySelectorAll("#studentsTableBody tr").forEach((row) => {
    const name = row.cells[0]?.textContent.toLowerCase() || "";
    row.style.display = name.includes(query) ? "" : "none";
  });
}

function copyCode() {
  const code = document.getElementById("classCode")?.textContent.trim();
  if (!code) return;
  navigator.clipboard.writeText(code);
  showToast(`Código "${code}" copiado!`, "success");
}

/* ==========================
   ATUALIZAÇÃO AUTOMÁTICA
========================== */
setInterval(() => {
  const turmaId = localStorage.getItem("last_turma_id");
  if (turmaId) loadAlunos(turmaId);
}, 15000); // Atualiza a lista de alunos a cada 15 segundos

/* ==========================
   INICIALIZAÇÃO
========================== */
document.addEventListener("DOMContentLoaded", loadTurma);

/* ==========================
   EXPORTAÇÕES GLOBAIS
========================== */
window.addStudent = addStudent;
window.removeAluno = removeAluno;
window.editClass = editClass;
window.deleteClass = deleteClass;
window.exportStudents = exportStudents;
window.generateReport = generateReport;
window.filterStudents = filterStudents;
window.copyCode = copyCode;
