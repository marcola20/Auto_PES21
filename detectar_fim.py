"""
detectar_fim.py  --  Auto_PES21 / etapa 2

Fica olhando a tela e avisa quando a partida terminar.

Como funciona: a tela de fim de jogo do PES sempre desenha o texto "Fim de jogo"
no MESMO lugar, dentro de um painel opaco. Entao eu guardei um recorte daquela
regiao (templates/fim_de_jogo.png) e, de tempos em tempos, comparo aquele mesmo
pedaco da tela com o recorte guardado. Se forem quase iguais, a partida acabou.

Nao precisa de OpenCV nem de pyautogui: como a posicao e fixa, basta comparar
pixel a pixel.
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

CAMINHO_TEMPLATE = "templates/fim_de_jogo.png"

# Regiao da tela onde fica o texto "Fim de jogo", em pixels: (x1, y1, x2, y2).
# Medido em 1920x1080. Se voce mudar a resolucao do jogo, isso muda.
REGIAO = (855, 70, 1065, 115)

# Quao parecido precisa ser para valer como "achei".
# 0 = identico. Nos testes: telas de fim deram 0 a 5, e a tela mais parecida
# que NAO era fim deu 47. Entao 15 fica bem no meio do vazio.
LIMIAR = 15

INTERVALO_CHECAGEM = 2.0     # de quantos em quantos segundos olhar a tela
SEGUNDOS_CONTAGEM  = 8       # tempo para voltar ao PES antes de comecar
MINUTOS_LIMITE     = 30      # desiste depois disso e avisa que deu errado

MOSTRAR_PROGRESSO = True     # imprime a diferenca a cada checagem

# ==========================================================================

import sys
import time
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageGrab
except ImportError:
    print("ERRO: falta a biblioteca Pillow.  Rode:  python -m pip install pillow")
    sys.exit(1)


def carregar_template(caminho: str) -> Image.Image:
    """Le o recorte de referencia do disco."""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(
            f"Nao achei o template em '{arquivo.resolve()}'.\n"
            "Ele e gerado a partir de um print da tela de fim de jogo."
        )
    return Image.open(arquivo).convert("RGB")


def diferenca_da_tela(template: Image.Image, regiao=REGIAO) -> float:
    """Tira um print, recorta a regiao e devolve o quanto ela difere do template.

    O numero e a media da diferenca de brilho pixel a pixel:
    0 = as duas imagens sao identicas, quanto maior, mais diferentes.
    """
    tela = ImageGrab.grab(all_screens=True).convert("RGB").crop(regiao)

    # Se o recorte da tela e o template nao tem o mesmo tamanho, algo esta
    # errado (resolucao diferente da esperada) - melhor avisar do que fingir.
    if tela.size != template.size:
        raise ValueError(
            f"Tamanho incompativel: a tela deu {tela.size} e o template e "
            f"{template.size}. O jogo esta em outra resolucao?"
        )

    dif = ImageChops.difference(tela, template).convert("L")
    pixels = list(dif.get_flattened_data())
    return sum(pixels) / len(pixels)


def fim_de_jogo_na_tela(template: Image.Image, limiar: float = LIMIAR) -> bool:
    """Devolve True se a tela de fim de jogo estiver aparecendo agora."""
    return diferenca_da_tela(template) < limiar


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Monitorando!                    ")


def esperar_fim_de_jogo(template: Image.Image,
                        minutos_limite: float = MINUTOS_LIMITE) -> bool:
    """Fica checando ate achar o fim de jogo ou estourar o tempo limite.

    Devolve True se achou, False se desistiu por tempo.
    """
    inicio = time.time()
    limite = inicio + minutos_limite * 60
    checagens = 0

    while time.time() < limite:
        dif = diferenca_da_tela(template)
        checagens += 1

        if dif < LIMIAR:
            decorrido = time.time() - inicio
            print(" " * 70, end="\r")
            print(f"\n>>> FIM DE JOGO detectado!  (diferenca = {dif:.2f})")
            print(f"    Levou {decorrido/60:.1f} min e {checagens} checagens.")
            return True

        if MOSTRAR_PROGRESSO:
            decorrido = time.time() - inicio
            print(f"  [{decorrido/60:5.1f} min]  diferenca = {dif:6.2f}  "
                  f"(precisa ficar abaixo de {LIMIAR})", end="\r", flush=True)

        time.sleep(INTERVALO_CHECAGEM)

    print(" " * 70, end="\r")
    print(f"\n>>> DESISTI: passaram {minutos_limite} min sem achar o fim de jogo.")
    return False


def main() -> int:
    print("=" * 66)
    print("  DETECTOR DE FIM DE PARTIDA  --  Auto_PES21 / etapa 2")
    print("=" * 66)

    try:
        template = carregar_template(CAMINHO_TEMPLATE)
    except FileNotFoundError as erro:
        print(f"\nERRO: {erro}")
        return 1

    print(f"\nTemplate  : {CAMINHO_TEMPLATE}  ({template.size[0]}x{template.size[1]} px)")
    print(f"Regiao    : {REGIAO}")
    print(f"Limiar    : {LIMIAR}")
    print(f"Checando  : a cada {INTERVALO_CHECAGEM}s, por ate {MINUTOS_LIMITE} min\n")

    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # Uma checagem imediata so para confirmar que a leitura da tela funciona.
    try:
        dif_inicial = diferenca_da_tela(template)
    except ValueError as erro:
        print(f"\nERRO: {erro}")
        return 1
    print(f"  Leitura inicial da tela: diferenca = {dif_inicial:.2f}")
    if dif_inicial < LIMIAR:
        print("  (a tela de fim de jogo JA esta na tela agora)")

    print()
    achou = esperar_fim_de_jogo(template)

    print("-" * 66)
    if achou:
        print("RESULTADO: OK - a deteccao funcionou.")
        return 0
    print("RESULTADO: FALHOU - nao detectou o fim da partida.")
    print("-" * 66)
    print("O que conferir:")
    print("  - A partida chegou mesmo ao fim de jogo?")
    print("  - O jogo esta em 1920x1080? (a REGIAO depende disso)")
    print("  - Veja o valor da diferenca: se ficou perto de 20-40 na tela de")
    print("    fim de jogo, e so aumentar o LIMIAR.")
    return 1


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
