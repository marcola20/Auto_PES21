"""
teclado.py  --  Auto_PES21

Envio de teclas para o jogo. Tudo que apertar tecla passa por aqui.

Uso pydirectinput e nao pyautogui porque jogos em DirectX costumam ignorar as
teclas do pyautogui: ele usa uma API antiga do Windows que o jogo nao escuta.
"""

import sys
import time

try:
    import pydirectinput
except ImportError:
    print("ERRO: falta a biblioteca 'pydirectinput'.")
    print("Rode:  python -m pip install pydirectinput")
    sys.exit(1)

# Pausa que o pydirectinput coloca sozinho depois de cada comando.
pydirectinput.PAUSE = 0.05
# Desliga a trava que aborta o script se o mouse for ao canto da tela.
pydirectinput.FAILSAFE = False

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

# Teclas dos menus do PES. Ajuste se o seu jogo usar outras.
TECLA_CIMA     = "up"
TECLA_BAIXO    = "down"
TECLA_ESQUERDA = "left"
TECLA_DIREITA  = "right"
TECLA_CONFIRMA = "enter"
TECLA_VOLTAR   = "esc"        # medido no jogo, nao chutado

# L1 / R1 trocam a aba no painel de fim de jogo e de intervalo.
# Deixe como None ate descobrir a tecla certa (teste_r1.py, ou o proprio
# jogo em Configuracoes -> Controles). Com None, o script pula essa etapa
# em vez de apertar uma tecla qualquer e fazer besteira.
TECLA_R1 = "e"    # medido com teste_r1.py: trocou a aba (0.230)
TECLA_L1 = "q"    # informado pelo usuario; nao passou por teste

# Espera depois de cada tecla de menu. Se o jogo perder teclas, aumente.
PAUSA_ENTRE_TECLAS = 0.15

# Pausas do Alt+F9 (atalho de gravar da NVIDIA).
PAUSA_DEPOIS_ALT_DOWN = 0.20
PAUSA_F9_PRESSIONADO  = 0.10
PAUSA_ANTES_ALT_UP    = 0.20

# ==========================================================================


def apertar(tecla: str, vezes: int = 1, pausa: float = None) -> None:
    """Aperta uma tecla, opcionalmente varias vezes seguidas."""
    if pausa is None:
        pausa = PAUSA_ENTRE_TECLAS
    for _ in range(vezes):
        pydirectinput.press(tecla)
        time.sleep(pausa)


def cima(vezes: int = 1) -> None:
    apertar(TECLA_CIMA, vezes)


def baixo(vezes: int = 1) -> None:
    apertar(TECLA_BAIXO, vezes)


def esquerda(vezes: int = 1) -> None:
    apertar(TECLA_ESQUERDA, vezes)


def direita(vezes: int = 1) -> None:
    apertar(TECLA_DIREITA, vezes)


def confirmar(vezes: int = 1) -> None:
    apertar(TECLA_CONFIRMA, vezes)


def voltar(vezes: int = 1) -> None:
    apertar(TECLA_VOLTAR, vezes)


def alternar_gravacao() -> None:
    """Envia Alt+F9, o atalho que LIGA e DESLIGA a gravacao da NVIDIA.

    Os tres passos separados sao de proposito: o overlay da NVIDIA le o estado
    real das teclas, e se o Alt e o F9 chegam no mesmo instante ele as vezes
    enxerga so o F9 e ignora o atalho.
    """
    pydirectinput.keyDown("alt")
    time.sleep(PAUSA_DEPOIS_ALT_DOWN)

    pydirectinput.keyDown("f9")
    time.sleep(PAUSA_F9_PRESSIONADO)
    pydirectinput.keyUp("f9")

    time.sleep(PAUSA_ANTES_ALT_UP)
    pydirectinput.keyUp("alt")
