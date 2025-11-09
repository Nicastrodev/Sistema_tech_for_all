import subprocess
import json
import os

EXEC_PATH = os.path.join(os.getcwd(), "calculos")  # caminho do executável C


def calcular_media_c(notas, exame_final, total_tarefas, entregues):
    """
    Executa o programa em C responsável por calcular:
      - Média final
      - Situação (Aprovado/Reprovado/Recuperação)
      - Frequência (%)
    """
    try:
        # Converter lista de notas em string "7.5,8.0,6.5"
        notas_str = ",".join(str(n) for n in notas)

        result = subprocess.run(
            [EXEC_PATH, notas_str, str(exame_final), str(
                total_tarefas), str(entregues)],
            capture_output=True,
            text=True,
            check=True
        )

        # Tenta converter a saída do C em JSON
        output = result.stdout.strip()
        return json.loads(output)

    except Exception as e:
        print(f"[ERRO] Falha ao executar o programa C: {e}")
        print(f"Saída do programa: {getattr(result, 'stdout', '')}")
        return {"media": 0.0, "situacao": "Erro", "frequencia": 0.0}
