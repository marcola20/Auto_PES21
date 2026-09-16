"""
teste_captura.py  --  Auto_PES21 / teste rapido

Descobre se o Python consegue TIRAR PRINT da tela com o PES aberto.
Se a imagem vier toda preta, o reconhecimento de imagem nao vai funcionar
nesse modo de tela, e precisamos trocar para modo Janela.
"""

# ====================== CONFIGURACOES ======================
SEGUNDOS_CONTAGEM = 8              # tempo para voltar pro PES
ARQUIVO_SAIDA     = "print_teste.png"   # onde o print sera salvo
# ===========================================================

import sys
import time
from pathlib import Path

try:
    from PIL import ImageGrab
except ImportError:
    print("ERRO: falta a biblioteca Pillow.")
    print("Rode:  python -m pip install pillow")
    sys.exit(1)


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Tirando o print!               ")


def main() -> int:
    print("=" * 62)
    print("  TESTE DE CAPTURA DE TELA  --  Auto_PES21")
    print("=" * 62)
    print(f"\nVoce tem {SEGUNDOS_CONTAGEM}s para deixar o PES em foco.\n")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # Tira o print da tela inteira. all_screens=True pega monitores multiplos.
    imagem = ImageGrab.grab(all_screens=True)

    largura, altura = imagem.size
    print(f"\nResolucao capturada: {largura} x {altura}")

    # Converte para tons de cinza e olha o brilho. Uma tela preta tem
    # brilho medio perto de 0 e pouquissimas cores diferentes.
    cinza = imagem.convert("L")
    pixels = list(cinza.getdata())
    brilho_medio = sum(pixels) / len(pixels)
    tons_distintos = len(set(pixels))

    print(f"Brilho medio (0=preto, 255=branco): {brilho_medio:.1f}")
    print(f"Tons de cinza distintos na imagem : {tons_distintos}")

    caminho = Path(ARQUIVO_SAIDA).resolve()
    imagem.save(caminho)
    print(f"\nPrint salvo em:\n  {caminho}")

    print("\n" + "-" * 62)
    if brilho_medio < 3 or tons_distintos < 5:
        print("RESULTADO: FALHOU  -  a captura veio praticamente PRETA.")
        print("-" * 62)
        print("O modo de tela atual bloqueia o screenshot.")
        print("Solucao: mude o PES para modo JANELA e rode este teste de novo.")
        return 1

    print("RESULTADO: OK  -  a captura tem imagem de verdade.")
    print("-" * 62)
    print("ABRA o arquivo print_teste.png e confirme que voce ve o PES nele.")
    print("(o teste automatico nao sabe se o que apareceu foi o jogo ou o desktop)")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
