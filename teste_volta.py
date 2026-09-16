"""
teste_volta.py  --  Auto_PES21 / descobrir a tecla "Voltar"

O passo [7] do loop falhou porque a tecla de Voltar em teclado.py era um CHUTE
meu (backspace) que nunca passou por teste. Todas as outras teclas se provaram
no teste de navegacao; essa nao.

Este script aperta cada candidata e pergunta algo simples depois de cada uma:
"ainda estou vendo um nome de time no painel 'Em casa'?". Se o Voltar
funcionou, o painel trocou para a lista de LIGAS e a resposta e nao.

E uma pergunta de sim ou nao, sem limiar. A primeira versao comparava pixels e
reprovou o 'esc', que funcionava de verdade: ele mudou a tela em 27.2 e o
limiar, inflado por duas margens de seguranca empilhadas, estava em 34.4.

COMO USAR:
  Deixe o PES na tela de SELECAO DE TIMES, com o painel "Em casa" ATIVO na
  lista de times (a mesma tela em que voce roda a calibracao).
  Se a tecla certa for encontrada, o painel vai voltar para a lista de LIGAS.
"""

# ====================== CONFIGURACOES ======================
SEGUNDOS_CONTAGEM = 8

# Candidatas, em ordem de suspeita. A lista e curta de proposito: sao teclas
# que em menu costumam significar "voltar", e nao teclas que possam disparar
# outra coisa no jogo.
CANDIDATAS = ["esc", "backspace", "delete", "x", "z"]

# Regiao do painel "Em casa" inteiro. Se o Voltar funcionar, este painel troca
# da lista de TIMES para a lista de LIGAS - uma mudanca visual grande.
REGIAO_PAINEL_CASA = (180, 40, 890, 950)

PAUSA_APOS_TECLA = 1.5
# ===========================================================

import statistics
import sys
import time
from pathlib import Path

from PIL import ImageChops

import navegar
import teclado
import visao

PASTA_SAIDA = Path("diagnostico_volta")


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def foto():
    return visao.capturar_tela().crop(REGIAO_PAINEL_CASA)


def quanto_mudou(antes, depois) -> float:
    dif = ImageChops.difference(antes, depois).convert("L")
    return statistics.mean(list(dif.get_flattened_data()))


def ainda_ve_um_time() -> tuple:
    """O painel 'Em casa' ainda esta mostrando um time reconhecivel?

    Este e o sinal que decide o teste, e ele e SEMANTICO, nao estatistico:
    na lista de times a regiao mostra um nome que bate com um dos 12 templates;
    na lista de ligas mostra "Brasileirao Serie A", que nao bate com nenhum.

    A primeira versao deste script comparava pixels e exigia que a mudanca
    passasse de 5x o maior ruido medido. O 'esc' funcionou de verdade e mesmo
    assim foi reprovado: mudou 27.2, e o limiar inflado estava em 34.4.
    Empilhar margem sobre margem afogou o sinal. Uma pergunta de sim ou nao -
    "ainda vejo um time?" - nao precisa de limiar nenhum.
    """
    nome, semelhanca = navegar.qual_time_esta_selecionado("casa")
    return nome is not None, nome, semelhanca


def testar_candidatas():
    print("\n[2/2] Testando as candidatas.\n")

    for tecla in CANDIDATAS:
        antes = foto()
        teclado.apertar(tecla)
        time.sleep(PAUSA_APOS_TECLA)
        depois = foto()

        mudanca = quanto_mudou(antes, depois)
        ve_time, nome, semelhanca = ainda_ve_um_time()

        antes.save(PASTA_SAIDA / f"antes_{tecla}.png")
        depois.save(PASTA_SAIDA / f"depois_{tecla}.png")

        if ve_time:
            print(f"      {tecla:10s} pixels mudaram {mudanca:6.2f}  |  "
                  f"ainda vejo o time '{nome}' ({semelhanca:.3f}) -> nao voltou")
            continue

        print(f"      {tecla:10s} pixels mudaram {mudanca:6.2f}  |  "
              f"NAO vejo mais time nenhum  <<< ESTA E A TECLA")
        # Para na hora. A versao anterior seguia testando depois de achar a
        # tecla certa, e as teclas seguintes deixavam o jogo numa tela
        # inesperada - foi o que travou o teste da vez passada.
        return tecla

    return None


def main() -> int:
    PASTA_SAIDA.mkdir(exist_ok=True)

    print("=" * 70)
    print("  DESCOBRIR A TECLA 'VOLTAR'")
    print("=" * 70)
    print("\nDeixe o PES na SELECAO DE TIMES, painel 'Em casa' ATIVO na lista")
    print("de times (a mesma tela da calibracao).\n")

    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # Confere o ponto de partida antes de apertar qualquer coisa: se eu ja nao
    # estou vendo um time, o teste inteiro nao faz sentido.
    print("\n[1/2] Conferindo o ponto de partida...")
    ve_time, nome, semelhanca = ainda_ve_um_time()
    if not ve_time:
        print("      FALHOU - nao vejo nenhum time no painel 'Em casa'.")
        print("      O PES precisa estar na LISTA DE TIMES, painel esquerdo ativo.")
        return 1
    print(f"      OK - vejo o time '{nome}' ({semelhanca:.3f})")

    tecla = testar_candidatas()

    print("\n" + "-" * 70)
    if tecla is None:
        print("RESULTADO: nenhuma das candidatas voltou para a lista de ligas.")
        print("-" * 70)
        print("Descubra na mao: com o PES nessa tela, aperte teclas ate o painel")
        print("voltar para a lista de LIGAS, e me diga qual funcionou.")
        print("Pode ser tambem que o PES use outra tecla configurada nas opcoes")
        print("do proprio jogo (Configuracoes -> Controles).")
        return 1

    print(f"RESULTADO: a tecla de Voltar e '{tecla}'")
    print("-" * 70)
    print("Confira nos prints em diagnostico_volta/ que o painel 'Em casa'")
    print("voltou da lista de TIMES para a lista de LIGAS.")
    print(f"\nSe estiver certo, edite teclado.py:")
    print(f'    TECLA_VOLTAR   = "{tecla}"')
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
