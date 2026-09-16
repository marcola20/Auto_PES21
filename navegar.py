"""
navegar.py  --  Auto_PES21 / etapa 4

Leva o cursor ate um time especifico na lista, e SO devolve sucesso depois de
conferir na tela que chegou no time certo.

A estrategia tem tres partes:

  ANCORAR   - manda muitos "Cima" para grudar no topo da lista. Como a lista
              nao da a volta (testamos), o cursor para no primeiro time.
              Assim a navegacao nunca depende de onde o cursor estava.

  CONTAR    - manda N "Baixo", onde N e a posicao do time na ordem alfabetica.

  CONFERIR  - le o nome que ficou selecionado e compara com o template daquele
              time. So aqui e que o sucesso e declarado.

Se a conferencia falhar, tenta o caminho inteiro de novo. A falha mais provavel
nao e a logica, e uma tecla que o jogo deixou passar - e isso se resolve
refazendo o percurso. Mas depois de algumas tentativas, desiste e avisa, em vez
de seguir com o time errado.
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

PASTA_TEMPLATES = "templates/times"

TECLAS_PARA_ANCORAR = 25   # "Cima" suficientes para grudar no topo
TENTATIVAS = 3             # quantas vezes refazer o caminho antes de desistir

PAUSA_APOS_MOVER  = 0.6    # depois de UMA tecla
PAUSA_APOS_RAJADA = 2.5    # depois de VARIAS teclas seguidas

VERIFICAR_ANCORA = True    # confere que o topo e mesmo o primeiro time

# ==========================================================================

import time
from pathlib import Path

from PIL import Image

import teclado
import times
import visao


def caminho_do_template(painel: str, nome_do_time: str) -> Path:
    return Path(PASTA_TEMPLATES) / f"{painel}_{times.apelido(nome_do_time)}.png"


def mascara_do_template(painel: str, nome_do_time: str) -> list:
    """Le o template salvo na calibracao e devolve a mascara do texto."""
    caminho = caminho_do_template(painel, nome_do_time)
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Falta o template de '{nome_do_time}' no painel '{painel}'.\n"
            f"Esperado em: {caminho.resolve()}\n"
            f"Rode primeiro:  python calibrar_times.py {painel}"
        )
    return visao.mascara_texto_verde(Image.open(caminho))


def ler_da_tela(painel: str, espera: float) -> list:
    """Espera a animacao terminar e le o nome selecionado agora na tela.

    Usa visao.ler_regiao, que insiste se a captura vier vazia: em teste, o
    ImageGrab devolveu um quadro em branco entre duas leituras sem nenhuma
    tecla no meio. Uma captura ruim nao pode virar "time errado".
    """
    time.sleep(espera)
    return visao.ler_regiao(visao.regiao_do_painel(painel))


def confere(mascara_tela: list, mascara_alvo: list) -> tuple:
    """Compara o que esta na tela com o esperado.

    Devolve (bateu, semelhanca). Leitura vazia nunca conta como sucesso: ela
    significa "nao consegui ler", e nao "e outro time".
    """
    if not visao.tem_texto(mascara_tela):
        return False, 0.0
    semelhanca = visao.sobreposicao(mascara_tela, mascara_alvo)
    return semelhanca >= visao.LIMIAR_NOME_TIME, semelhanca


def ancorar(painel: str, falar=print) -> bool:
    """Leva o cursor ao primeiro time da lista e confirma que chegou la."""
    teclado.cima(TECLAS_PARA_ANCORAR)

    if not VERIFICAR_ANCORA:
        time.sleep(PAUSA_APOS_RAJADA)
        return True

    primeiro = times.TIMES[0]
    na_tela = ler_da_tela(painel, PAUSA_APOS_RAJADA)
    bateu, semelhanca = confere(na_tela, mascara_do_template(painel, primeiro))

    if bateu:
        falar(f"      ancora OK: topo da lista e '{primeiro}' ({semelhanca:.3f})")
        return True

    falar(f"      ancora FALHOU: o topo nao parece '{primeiro}' ({semelhanca:.3f})")
    return False


def ir_para_time(painel: str, nome_do_time: str, falar=print) -> bool:
    """Leva o cursor ate o time pedido. Devolve True so se confirmar na tela."""
    posicao = times.indice_do_time(nome_do_time)      # ja valida o nome
    alvo = mascara_do_template(painel, nome_do_time)

    falar(f"  -> '{nome_do_time}' (posicao {posicao}) no painel '{painel}'")

    for tentativa in range(1, TENTATIVAS + 1):
        if TENTATIVAS > 1:
            falar(f"    tentativa {tentativa}/{TENTATIVAS}")

        if not ancorar(painel, falar):
            continue

        if posicao > 0:
            teclado.baixo(posicao)
            espera = PAUSA_APOS_RAJADA if posicao > 1 else PAUSA_APOS_MOVER
        else:
            espera = PAUSA_APOS_MOVER

        na_tela = ler_da_tela(painel, espera)
        bateu, semelhanca = confere(na_tela, alvo)

        if bateu:
            falar(f"      OK - '{nome_do_time}' selecionado (semelhanca {semelhanca:.3f})")
            return True

        if not visao.tem_texto(na_tela):
            falar("      leitura vazia - o menu ainda devia estar animando")
        else:
            falar(f"      nao bateu (semelhanca {semelhanca:.3f}, "
                  f"precisa de {visao.LIMIAR_NOME_TIME})")

    falar(f"      DESISTI de chegar em '{nome_do_time}' apos {TENTATIVAS} tentativas.")
    return False


def qual_time_esta_selecionado(painel: str) -> tuple:
    """Diz qual time o cursor esta marcando agora, comparando com os 12 templates.

    Devolve (nome, semelhanca) ou (None, 0.0) se nao reconhecer nenhum.
    Util para diagnostico: em vez de so dizer "nao era o esperado", diz o que era.
    """
    na_tela = visao.ler_regiao(visao.regiao_do_painel(painel))
    if not visao.tem_texto(na_tela):
        return None, 0.0

    melhor_nome, melhor_valor = None, 0.0
    for nome in times.TIMES:
        try:
            valor = visao.sobreposicao(na_tela, mascara_do_template(painel, nome))
        except FileNotFoundError:
            continue
        if valor > melhor_valor:
            melhor_nome, melhor_valor = nome, valor

    if melhor_valor < visao.LIMIAR_NOME_TIME:
        return None, melhor_valor
    return melhor_nome, melhor_valor
