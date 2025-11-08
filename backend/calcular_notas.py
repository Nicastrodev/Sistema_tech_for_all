import os


def calcular_media_notas(notas, exame_final=-1):
    """
    notas: lista de floats (pode estar vazia)
    exame_final: float (ou -1 se não tiver)

    Lógica recriada em Python puro para remover a dependência do notas.exe
    e garantir portabilidade (Linux/macOS/Windows).
    """

    # 1. Calcular média das atividades
    media_atividades = 0.0
    if notas and len(notas) > 0:
        soma = sum(notas)
        media_atividades = soma / len(notas)

    # 2. Calcular média final (com ou sem exame)
    media_final = media_atividades
    if exame_final >= 0:
        media_final = (media_atividades + exame_final) / 2.0

    # 3. Definir situação
    situacao = "Reprovado"
    if media_final >= 7.0:
        situacao = "Aprovado"
    elif media_final >= 5.0:
        situacao = "Recuperação"

    # 4. Retornar o JSON esperado
    return {"media": round(media_final, 2), "situacao": situacao}
