"""
calibrar_times.py  --  Auto_PES21 / etapa 3

Monta sozinho a "ficha de identidade" visual de cada time, andando pela lista
e fotografando o nome em cada posicao.

Ele faz tres coisas, nessa ordem:

  1. TESTA A TECLA   - confirma que o jogo responde as setas do teclado.
  2. TESTA A ANCORA  - descobre se a lista DA A VOLTA quando chega no topo.
                       Isso decide se da para navegar contando teclas.
  3. FOTOGRAFA TUDO  - anda de cima para baixo salvando o nome de cada time.

Por que isso e necessario: voce me disse que o cursor as vezes reabre numa
posicao diferente da esperada. Entao o script nunca pode contar teclas "a
partir de onde esta" - precisa primeiro ir ate um ponto conhecido (o topo) e
depois conferir POR IMAGEM que chegou no time certo.
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

PAINEL_PADRAO = "casa"   # usado se voce rodar sem argumento

PASTA_TEMPLATES = "templates/times"

SEGUNDOS_CONTAGEM = 8    # tempo para voltar ao PES
TECLAS_PARA_ANCORAR = 25 # quantos "Cima" para garantir que chegou no topo
PAUSA_APOS_MOVER   = 0.6   # espera a animacao depois de UMA tecla
PAUSA_APOS_RAJADA  = 2.5   # espera depois de VARIAS teclas seguidas.
                           # Precisa ser bem maior: 25 teclas enfileiram
                           # uma rolagem longa, e fotografar no meio dela
                           # foi exatamente o que quebrou a 1a versao.

# ==========================================================================

import sys
import time
from pathlib import Path

import teclado
import times
import visao

# Permite escolher o painel pela linha de comando:
#     python calibrar_times.py fora
# Sem argumento, usa o PAINEL_PADRAO definido la em cima.
PAINEL = sys.argv[1].strip().lower() if len(sys.argv) > 1 else PAINEL_PADRAO
if PAINEL not in ("casa", "fora"):
    print(f"ERRO: painel deve ser 'casa' ou 'fora', recebi '{PAINEL}'.")
    sys.exit(1)


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def fotografar_nome(espera: float = None):
    """Espera a animacao, fotografa a regiao do nome e devolve (recorte, mascara)."""
    time.sleep(PAUSA_APOS_MOVER if espera is None else espera)
    tela = visao.capturar_tela()
    recorte = tela.crop(visao.regiao_do_painel(PAINEL))
    return recorte, visao.mascara_texto_verde(recorte)


def testar_tecla() -> bool:
    """Confirma que o jogo responde as setas.

    Aperto Baixo e vejo se o nome mudou. Se nao mudou, pode ser que o cursor ja
    estivesse no ultimo item - entao tento Cima. Se nenhum dos dois muda nada,
    a tecla nao esta chegando no jogo.
    """
    print("\n[1/3] Testando se o jogo responde as setas...")
    _, antes = fotografar_nome()

    # Sem esta checagem, duas leituras VAZIAS dariam sobreposicao 0.0 e o teste
    # "passaria" sem nunca ter enxergado nada na tela. Foi esse o erro que fez a
    # primeira versao concluir que a lista dava a volta.
    if not visao.tem_texto(antes):
        print(f"      FALHOU - nao achei nome de time na regiao "
              f"{visao.regiao_do_painel(PAINEL)}.")
        print("      O painel certo esta ativo? O jogo esta em 1920x1080?")
        return False

    teclado.baixo()
    _, depois = fotografar_nome()
    if visao.sobreposicao(antes, depois) < visao.LIMIAR_NOME_TIME:
        print("      OK - o jogo respondeu ao 'Baixo'.")
        return True

    print("      'Baixo' nao mudou nada (o cursor pode estar no fim). Tentando 'Cima'...")
    teclado.cima()
    _, depois = fotografar_nome()
    if visao.sobreposicao(antes, depois) < visao.LIMIAR_NOME_TIME:
        print("      OK - o jogo respondeu ao 'Cima'.")
        return True

    print("      FALHOU - o nome nao mudou com nenhuma das duas setas.")
    return False


def testar_ancora() -> bool:
    """Descobre se da para usar o topo da lista como ponto de partida confiavel.

    Mando muitos 'Cima' para grudar no topo e fotografo. Depois mando mais
    alguns 'Cima' e fotografo de novo. Se a lista NAO da a volta, o cursor fica
    parado no primeiro item e as duas fotos sao iguais. Se ela DA a volta, o
    cursor continua andando e as fotos ficam diferentes.
    """
    print(f"\n[2/3] Testando a ancora ({TECLAS_PARA_ANCORAR}x 'Cima' para grudar no topo)...")
    teclado.cima(TECLAS_PARA_ANCORAR)
    _, no_topo = fotografar_nome(PAUSA_APOS_RAJADA)

    teclado.cima(3)
    _, ainda_no_topo = fotografar_nome(PAUSA_APOS_RAJADA)

    if not visao.tem_texto(no_topo) or not visao.tem_texto(ainda_no_topo):
        print("      INCONCLUSIVO - leitura vazia, o menu ainda devia estar rolando.")
        print(f"      Aumente PAUSA_APOS_RAJADA (esta em {PAUSA_APOS_RAJADA}s).")
        return False

    parecenca = visao.sobreposicao(no_topo, ainda_no_topo)
    if parecenca >= visao.LIMIAR_NOME_TIME:
        print(f"      OK - a lista PARA no topo (sobreposicao {parecenca:.3f}).")
        print("      Da para ancorar e contar teclas com seguranca.")
        return True

    print(f"      A lista DA A VOLTA (sobreposicao {parecenca:.3f}).")
    print("      Ancorar pelo topo nao funciona - vou precisar de outra estrategia.")
    return False


def fotografar_lista() -> list:
    """Anda do topo ate o fim, guardando a foto do nome em cada posicao."""
    print(f"\n[3/3] Fotografando os {len(times.TIMES)} times, de cima para baixo...")
    capturas = []

    recorte, mascara = fotografar_nome()
    capturas.append((recorte, mascara))
    print(f"      [ 0] {times.TIMES[0]}")

    for i in range(1, len(times.TIMES)):
        teclado.baixo()
        recorte, mascara = fotografar_nome()
        capturas.append((recorte, mascara))
        pixels = sum(mascara)
        if not visao.tem_texto(mascara):
            print(f"      [{i:2d}] LEITURA VAZIA - aumente PAUSA_APOS_MOVER.")
            raise SystemExit(1)
        print(f"      [{i:2d}] {times.TIMES[i]:14s}  ({pixels} pixels de texto)")

    return capturas


def conferir_distintos(capturas: list) -> bool:
    """Confere que nao ha duas posicoes com o mesmo nome.

    Se duas baterem, ou a lista tem menos times do que eu pensava, ou o cursor
    travou em algum ponto e parou de andar. Nos dois casos e erro.
    """
    print("\nConferindo que os 12 nomes sao mesmo diferentes entre si...")
    problemas = []
    for i in range(len(capturas)):
        for j in range(i + 1, len(capturas)):
            s = visao.sobreposicao(capturas[i][1], capturas[j][1])
            if s >= visao.LIMIAR_NOME_TIME:
                problemas.append((i, j, s))

    if problemas:
        for i, j, s in problemas:
            print(f"  PROBLEMA: posicao {i} ({times.TIMES[i]}) e {j} "
                  f"({times.TIMES[j]}) parecem o MESMO nome (sobreposicao {s:.3f})")
        return False

    print("  OK - todos diferentes.")
    return True


def salvar(capturas: list) -> None:
    pasta = Path(PASTA_TEMPLATES)
    pasta.mkdir(parents=True, exist_ok=True)
    for time_nome, (recorte, _) in zip(times.TIMES, capturas):
        destino = pasta / f"{PAINEL}_{times.apelido(time_nome)}.png"
        recorte.save(destino)
    print(f"\n{len(capturas)} template(s) salvos em: {pasta.resolve()}")


def main() -> int:
    print("=" * 66)
    print(f"  CALIBRACAO DOS TIMES  --  painel '{PAINEL}'")
    print("=" * 66)
    print(f"\nDeixe o PES na tela de selecao de times, com o painel"
          f" '{PAINEL.upper()}' ativo\ne a lista do Brasileirao Serie A aberta.\n")

    contagem_regressiva(SEGUNDOS_CONTAGEM)

    if not testar_tecla():
        print("\n" + "-" * 66)
        print("PAROU: o jogo nao respondeu as setas.")
        print("-" * 66)
        print("  - O PES estava mesmo em foco durante a contagem?")
        print("  - Rode o terminal como Administrador.")
        print("  - Se o seu PES usa outras teclas, mude TECLA_CIMA/TECLA_BAIXO")
        print("    no arquivo teclado.py.")
        return 1

    if not testar_ancora():
        print("\n" + "-" * 66)
        print("PAROU: a lista da a volta, entao ancorar no topo nao serve.")
        print("-" * 66)
        print("Me avise que eu troco a estrategia de navegacao.")
        return 1

    capturas = fotografar_lista()

    if not conferir_distintos(capturas):
        print("\n" + "-" * 66)
        print("PAROU: as fotos nao batem com uma lista de 12 times distintos.")
        print("-" * 66)
        print("  - A lista aberta era mesmo a do Brasileirao Serie A?")
        print("  - Aumente PAUSA_APOS_MOVER (o menu pode estar animando devagar).")
        return 1

    salvar(capturas)
    print("-" * 66)
    print("RESULTADO: OK - calibracao concluida.")
    print("-" * 66)
    print("Abra a pasta e confira se cada arquivo mostra o time do nome dele.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
