"""
diagnostico_lista.py  --  Auto_PES21 / diagnostico

O teste de ancora deu sobreposicao 0.000, e esse numero e ambiguo: pode
significar "nomes completamente diferentes" ou "nao achei texto nenhum".

Este script nao decide nada. Ele so anda pela lista, salva o que esta vendo em
imagens, e mostra os numeros - para eu olhar e descobrir o que esta acontecendo.

Ele salva DUAS coisas em cada passo:
  - o recorte da regiao do nome (para ver se o nome esta la)
  - a tela inteira (para ver se o jogo continua na tela certa)
"""

# ====================== CONFIGURACOES ======================
PAINEL = "casa"
PASTA_SAIDA = "diagnostico"
SEGUNDOS_CONTAGEM = 8

# Bem mais generoso que na calibracao, de proposito: se o problema for
# animacao lenta, isso resolve e o diagnostico mostra.
PAUSA_CURTA = 1.0     # depois de 1 tecla
PAUSA_LONGA = 3.0     # depois de varias teclas seguidas
# ===========================================================

import sys
import time
from pathlib import Path

import teclado
import visao


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def registrar(pasta: Path, rotulo: str, espera: float) -> list:
    """Espera, fotografa, salva os arquivos e devolve a mascara."""
    time.sleep(espera)
    tela = visao.capturar_tela()
    recorte = tela.crop(visao.regiao_do_painel(PAINEL))
    mascara = visao.mascara_texto_verde(recorte)

    recorte.save(pasta / f"{rotulo}_nome.png")
    tela.save(pasta / f"{rotulo}_tela.png")

    pixels = sum(mascara)
    estado = "tem texto" if visao.tem_texto(mascara) else "VAZIA (nada verde)"
    print(f"  {rotulo:24s} {pixels:5d} pixels verdes   -> {estado}")
    return mascara


def main() -> int:
    pasta = Path(PASTA_SAIDA)
    pasta.mkdir(exist_ok=True)

    print("=" * 66)
    print("  DIAGNOSTICO DA LISTA DE TIMES")
    print("=" * 66)
    print(f"\nDeixe o PES na selecao de times, painel '{PAINEL.upper()}' ativo.\n")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    print()
    m_inicial = registrar(pasta, "00_inicial", PAUSA_CURTA)

    teclado.baixo()
    m_baixo1 = registrar(pasta, "01_apos_1_baixo", PAUSA_CURTA)

    teclado.cima()
    m_volta = registrar(pasta, "02_apos_1_cima", PAUSA_CURTA)

    teclado.cima(25)
    m_25cima = registrar(pasta, "03_apos_25_cima", PAUSA_LONGA)

    teclado.cima(3)
    m_mais3 = registrar(pasta, "04_apos_mais_3_cima", PAUSA_LONGA)

    print("\n" + "-" * 66)
    print("COMPARACOES (1.0 = mesmo nome, ~0.2 = nomes diferentes)")
    print("-" * 66)

    def comparar(rotulo, a, b):
        if not visao.tem_texto(a) or not visao.tem_texto(b):
            print(f"  {rotulo:38s} INCONCLUSIVO (alguma mascara vazia)")
            return
        print(f"  {rotulo:38s} {visao.sobreposicao(a, b):.4f}")

    comparar("inicial x apos 1 baixo", m_inicial, m_baixo1)
    comparar("inicial x apos baixo+cima (deve voltar)", m_inicial, m_volta)
    comparar("apos 25 cima x apos mais 3 cima", m_25cima, m_mais3)

    print("\n" + "-" * 66)
    print(f"Imagens salvas em: {pasta.resolve()}")
    print("-" * 66)
    print("Me manda o texto acima. Se puder, olhe tambem os arquivos")
    print("'03_apos_25_cima_tela.png' e '04_apos_mais_3_cima_tela.png' -")
    print("eles mostram em que tela o jogo estava naquele momento.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
