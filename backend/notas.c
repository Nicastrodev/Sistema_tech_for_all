#include <stdio.h>
#include <stdlib.h>

typedef struct {
    float atividades[10];
    int total_atividades;
    float exame_final;
} Aluno;

float calcular_media(Aluno a) {
    float soma = 0.0;
    for (int i = 0; i < a.total_atividades; i++) {
        soma += a.atividades[i];
    }
    float media_atividades = (a.total_atividades > 0) ? soma / a.total_atividades : 0.0;

    if (a.exame_final >= 0) {
        return (media_atividades + a.exame_final) / 2.0;
    }
    return media_atividades;
}

const char* situacao(float media) {
    if (media >= 7.0)
        return "Aprovado";
    else if (media >= 5.0)
        return "Recuperação";
    else
        return "Reprovado";
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Uso: %s <notas_separadas_por_virgula> <exame_final>\n", argv[0]);
        return 1;
    }

    Aluno a;
    a.total_atividades = 0;
    a.exame_final = atof(argv[2]);

    char *token = strtok(argv[1], ",");
    while (token && a.total_atividades < 10) {
        a.atividades[a.total_atividades++] = atof(token);
        token = strtok(NULL, ",");
    }

    float media_final = calcular_media(a);
    const char *status = situacao(media_final);

    printf("{\"media\": %.2f, \"situacao\": \"%s\"}\n", media_final, status);
    return 0;
}
