import subprocess
import json
import os

def calcular_media_notas(notas, exame_final=-1):
    """
    notas: lista de floats
    exame_final: float (ou -1 se não tiver)
    """
    notas_str = ",".join([str(n) for n in notas])
    exec_path = os.path.join(os.path.dirname(__file__), "notas.exe")

    try:
        result = subprocess.run(
            [exec_path, notas_str, str(exame_final)],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print("Erro ao executar módulo C:", e)
        return {"media": 0.0, "situacao": "Erro"}
