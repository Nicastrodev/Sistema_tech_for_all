const API_BASE_URL = "http://127.0.0.1:5050/api";

/* ------------------- Helpers ------------------- */
function getQueryParam(param) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(param);
}

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

function getSession() {
  return {
    user_id: localStorage.getItem("tf_user_id"),
    role: localStorage.getItem("tf_role"),
    name: localStorage.getItem("tf_name"),
  };
}

/* ------------------- Carregar turma ------------------- */
async function loadTurma() {
  const turmaId = getQueryParam("id");
  if (!turmaId) {
    alert("Turma não especificada.");
    window.location.href = "/dashboard/teacher";
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/turmas/${turmaId}`);
    const data = await res.json();

    if (!data.success) {
      alert(data.message || "Erro ao carregar turma.");
      return;
    }

    const turma = data.turma;
    document.getElementById("breadcrumbClassName").textContent = turma.nome;
    document.getElementById("className").textContent = turma.nome;
    document.getElementById("classNameDetail").textContent = turma.nome;
    document.getElementById("classDescription").textContent =
      turma.descricao || "Sem descrição";
    document.getElementById("classCode").textContent = turma.codigo_acesso;

    // Atualizar estatísticas gerais
    document.getElementById("totalStudents").textContent =
      turma.total_alunos || 0;
    document.getElementById("averageGrade").textContent =
      turma.media_geral?.toFixed(1) || "0.0";
    document.getElementById("averageAttendance").textContent =
      (turma.frequencia_media || 0) + "%";

    loadAlunos(turmaId);
  } catch (err) {
    console.error("Erro ao carregar turma:", err);
    alert("Erro ao conectar com o servidor.");
  }
}

/* ------------------- Carregar alunos ------------------- */
async function loadAlunos(turmaId) {
  const tbody = document.getElementById("studentsTableBody");
  tbody.innerHTML = `
    <tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-secondary)">
      Carregando alunos...
    </td></tr>`;

  try {
    const res = await fetch(`${API_BASE_URL}/turmas/${turmaId}/alunos`);
    const data = await res.json();

    if (!data.success) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:red">${data.message}</td></tr>`;
      return;
    }

    if (!data.alunos || data.alunos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-secondary)">Nenhum aluno encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    let aprovados = 0,
      recuperacao = 0,
      reprovados = 0;

    data.alunos.forEach((aluno) => {
      const tr = document.createElement("tr");
      const frequencia = aluno.frequencia ?? 0;
      const media = aluno.media ?? 0;
      let status = "";

      if (media >= 7) {
        status = "success";
        aprovados++;
      } else if (media >= 5) {
        status = "warning";
        recuperacao++;
      } else {
        status = "danger";
        reprovados++;
      }

      tr.innerHTML = `
        <td>${escapeHtml(aluno.nome)}</td>
        <td>${escapeHtml(aluno.email)}</td>
        <td>${frequencia}%</td>
        <td class="${status}">${media.toFixed(1)}</td>
        <td>
          <button class="btn-outline-small" onclick="viewStudent(${
            aluno.id
          })">Ver</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Atualiza contadores laterais
    document.getElementById("approvedCount").textContent = aprovados;
    document.getElementById("recoveryCount").textContent = recuperacao;
    document.getElementById("failedCount").textContent = reprovados;
  } catch (err) {
    console.error("Erro ao carregar alunos:", err);
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:red">Erro ao conectar com o servidor.</td></tr>`;
  }
}

/* ------------------- Filtros e Ações ------------------- */
function filterStudents() {
  const query = document
    .getElementById("searchStudent")
    .value.toLowerCase()
    .trim();
  const rows = document.querySelectorAll("#studentsTableBody tr");

  rows.forEach((row) => {
    const name = row.children[0]?.textContent.toLowerCase() || "";
    row.style.display = name.includes(query) ? "" : "none";
  });
}

function copyCode() {
  const code = document.getElementById("classCode").textContent.trim();
  navigator.clipboard.writeText(code);
  alert(`Código "${code}" copiado!`);
}

/* ------------------- Relatórios e Exportação ------------------- */
async function generateReport() {
  const turmaId = getQueryParam("id");
  try {
    const res = await fetch(`${API_BASE_URL}/relatorios/turma/${turmaId}`);
    const data = await res.json();
    if (!data.success) throw new Error(data.message);

    const reportText = `
📊 Relatório da Turma: ${data.nome_turma}
👥 Alunos: ${data.alunos}
📚 Atividades: ${data.atividades}
🏆 Média Geral: ${data.media_geral}
📈 Frequência Média: ${data.frequencia_media}%
    `;
    alert(reportText);
  } catch (err) {
    console.error("Erro gerar relatório:", err);
    alert("Erro ao gerar relatório.");
  }
}

function exportStudents() {
  const rows = [["Nome", "Email", "Frequência", "Média"]];
  document.querySelectorAll("#studentsTableBody tr").forEach((tr) => {
    const cols = Array.from(tr.children)
      .slice(0, 4)
      .map((td) => td.textContent);
    rows.push(cols);
  });
  const csvContent = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "alunos_turma.csv";
  link.click();
}

/* ------------------- Placeholders (ações futuras) ------------------- */
function addStudent() {
  alert("Funcionalidade de adicionar aluno será implementada em breve.");
}

function editClass() {
  alert("Edição de turma ainda em desenvolvimento.");
}

function viewStudent(id) {
  alert(`Visualizar perfil do aluno ID: ${id}`);
}

/* ------------------- Init ------------------- */
document.addEventListener("DOMContentLoaded", loadTurma);