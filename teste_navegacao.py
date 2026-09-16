"""
teste_navegacao.py  --  Auto_PES21 / etapa 4 (teste)

Testa a navegacao ate varios times, SEM confirmar nada e sem iniciar partida.
So mexe o cursor e confere se chegou no lugar certo.

Escolhi propositalmente times espalhados pela lista: o primeiro, o ultimo, um
do meio e um vizinho de outro. Assim o teste cobre o caso facil (posicao 0, que
nem precisa andar) e o mais longo (posicao 11), alem de dois nomes parecidos
(Coritiba e Corinthians), que e onde a comparacao por imagem mais poderia errar.
"""

# ====================== CONFIGURACOES ======================
PAINEL = "casa"           # mude para "fora" ou passe como argumento
SEGUNDOS_CONTAGEM = 8

TIMES_DO_TESTE = [
    "Botafogo",      # posicao 0  - nao precisa andar depois de ancorar
    "Vasco",         # posicao 11 - o percurso mais longo
    "Corinthians",   # posicao 1  - nome parecido com o proximo
    "Coritiba",      # posicao 2  - "Corinthians" x "Coritiba" comecam igual
    "Grêmio",        # posicao 6  - meio da lista, com acento
]
# ===========================================================

import sys
import time

import navegar
import times
import visao

if len(sys.argv) > 1:
    PAINEL = sys.argv[1].strip().lower()
if PAINEL not in ("casa", "fora"):
    print(f"ERRO: painel deve ser 'casa' ou 'fora', recebi '{PAINEL}'.")
    sys.exit(1)


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def main() -> int:
    print("=" * 66)
    print(f"  TESTE DE NAVEGACAO  --  painel '{PAINEL}'")
    print("=" * 66)
    print(f"\nDeixe o PES na selecao de times, painel '{PAINEL.upper()}' ativo.")
    print("O script SO move o cursor - nao confirma nada.\n")

    # Falha cedo e com mensagem clara se a calibracao nao foi feita.
    try:
        for nome in TIMES_DO_TESTE:
            navegar.mascara_do_template(PAINEL, nome)
    except FileNotFoundError as erro:
        print(f"ERRO: {erro}")
        return 1

    contagem_regressiva(SEGUNDOS_CONTAGEM)

    resultados = []
    for nome in TIMES_DO_TESTE:
        print()
        inicio = time.time()
        ok = navegar.ir_para_time(PAINEL, nome)
        resultados.append((nome, ok, time.time() - inicio))

    print("\n" + "-" * 66)
    print("RESUMO")
    print("-" * 66)
    for nome, ok, segundos in resultados:
        marca = "OK    " if ok else "FALHOU"
        print(f"  {marca}  {nome:14s} (posicao {times.indice_do_time(nome):2d})"
              f"  {segundos:5.1f}s")

    falhas = sum(1 for _, ok, _ in resultados if not ok)
    media = sum(s for _, _, s in resultados) / len(resultados)
    print("-" * 66)
    print(f"  tempo medio por time: {media:.1f}s")

    if falhas:
        print(f"\nRESULTADO: {falhas} de {len(resultados)} falharam.")
        print("Se o cursor parou no time errado, me diga em qual - o numero da")
        print("semelhanca acima ajuda a saber se foi tecla perdida ou leitura ruim.")
        return 1

    print(f"\nRESULTADO: OK - os {len(resultados)} times foram alcancados e conferidos.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
