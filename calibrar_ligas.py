"""
calibrar_ligas.py  --  Auto_PES21

Refaz o template da liga destacada (Brasileirao Serie A) para um dos paineis.

Por que existe separado do calibrar_times.py: o loop precisa conferir a LIGA em
dois momentos - ao confirmar o time da casa (o foco cai na lista de ligas do
painel fora) e quando o menu reabre num nivel acima do esperado. Os dois usam
um template que, como todos, guarda o formato das letras - e por isso quebra
quando o tema visual do jogo muda.

Este script nao precisa de print manual: ele descobre em que nivel o painel
esta. Se ja estiver na lista de LIGAS, so fotografa. Se estiver na lista de
TIMES, sobe com o Voltar, fotografa e desce de novo com o Confirmar - deixando
o jogo no mesmo estado em que o encontrou.

COMO USAR:
    python calibrar_ligas.py casa
    python calibrar_ligas.py fora

O painel correspondente precisa estar ATIVO com a liga certa em destaque.
Tanto faz ele estar na lista de TIMES ou ja na lista de LIGAS: o script
descobre em que nivel esta e navega so se precisar.
"""

# ====================== CONFIGURACOES ======================
PAINEL_PADRAO = "casa"
SEGUNDOS_CONTAGEM = 8
PAUSA_APOS_TECLA = 1.5
# ===========================================================

import sys
import time
from pathlib import Path

import navegar
import teclado
import visao

PAINEL = sys.argv[1].strip().lower() if len(sys.argv) > 1 else PAINEL_PADRAO
if PAINEL not in ("casa", "fora"):
    print(f"ERRO: painel deve ser 'casa' ou 'fora', recebi '{PAINEL}'.")
    sys.exit(1)

DESTINO = Path(f"templates/liga_{PAINEL}_brasileirao.png")


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def main() -> int:
    print("=" * 66)
    print(f"  CALIBRACAO DA LIGA  --  painel '{PAINEL}'")
    print("=" * 66)
    print(f"\nDeixe o painel '{PAINEL.upper()}' ATIVO, com o Brasileirao Serie A")
    print("em destaque. Tanto faz estar na lista de TIMES ou na de LIGAS.\n")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # 1) Descobrir em que nivel o painel esta. Aceito os DOIS pontos de partida:
    #    se ja estou na lista de ligas, nao ha nada a navegar - so fotografar.
    print("\n[1/3] Vendo em que nivel o painel esta...")
    nome, s = navegar.qual_time_esta_selecionado(PAINEL)
    veio_da_lista_de_times = nome is not None

    if veio_da_lista_de_times:
        print(f"      estou na lista de TIMES (vejo '{nome}', {s:.3f})")
    else:
        print("      nao vejo nome de time - devo ja estar na lista de LIGAS")

    # 2) Se preciso, subo um nivel: lista de times -> lista de ligas.
    if veio_da_lista_de_times:
        print("\n[2/3] Voltando para a lista de ligas...")
        teclado.voltar()
        time.sleep(PAUSA_APOS_TECLA)

        ainda, _ = navegar.qual_time_esta_selecionado(PAINEL)
        if ainda is not None:
            print(f"      FALHOU - ainda vejo o time '{ainda}', o Voltar nao subiu.")
            print(f"      Confira TECLA_VOLTAR em teclado.py (esta como "
                  f"'{teclado.TECLA_VOLTAR}').")
            return 1
        print("      OK - nao vejo mais nome de time, entao subi de nivel")
    else:
        print("\n[2/3] Nada a navegar - ja estou no nivel certo.")

    recorte = visao.capturar_tela().crop(visao.regiao_do_painel(PAINEL))
    marcados = sum(visao.mascara_texto_verde(recorte))
    if marcados < 100:
        print(f"      FALHOU - so {marcados} pixels de texto na regiao.")
        print("      Nao ha nada destacado ali para virar template.")
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    recorte.save(DESTINO)
    print(f"      template salvo ({marcados} pixels de texto)")

    # 3) Devolver o jogo ao estado em que estava - mas so se eu o tirei de la.
    #    Se o painel ja estava na lista de ligas quando comecei, deixo como
    #    esta: mexer a mais so criaria um estado que ninguem pediu.
    if not veio_da_lista_de_times:
        print("\n[3/3] Deixando a tela como estava (nao mexi na navegacao).")
    else:
        print("\n[3/3] Voltando para a lista de times...")
        teclado.confirmar()
        time.sleep(PAUSA_APOS_TECLA)

        nome, s = navegar.qual_time_esta_selecionado(PAINEL)
        if nome is None:
            print("      AVISO - nao consegui voltar para a lista de times.")
            print("      O template FOI salvo; so ajuste a tela na mao antes de")
            print("      rodar o proximo comando.")
        else:
            print(f"      OK - de volta na lista de times, em '{nome}' ({s:.3f})")

    print("\n" + "-" * 66)
    print(f"RESULTADO: OK - template salvo em {DESTINO}")
    print("-" * 66)
    print("ABRA esse arquivo e confirme que ele mostra 'Brasileirao Serie A'.")
    print("O script sabe em que nivel esta, mas nao sabe LER o que capturou -")
    print("se outra liga estivesse em destaque, ele salvaria ela sem reclamar.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
