"""
capturar_telas.py  --  Auto_PES21 / etapa 2

Ferramenta de captura. Voce joga/navega no PES normalmente e, sempre que
estiver numa tela importante, aperta a tecla de captura. O script salva um
print na pasta "telas/" sem voce precisar sair do jogo.

Nao usa biblioteca nova: le o teclado direto pelo Windows, via ctypes.
"""

# ====================== CONFIGURACOES ======================
PASTA_SAIDA = "telas"      # subpasta do projeto onde os prints vao

# Teclas. Os numeros sao os "virtual key codes" do Windows.
TECLA_CAPTURA = 0x7B       # F12  -> tira o print
TECLA_SAIR    = 0x23       # End  -> encerra o script

NOME_TECLA_CAPTURA = "F12"
NOME_TECLA_SAIR    = "End"

INTERVALO_LEITURA = 0.03   # de quanto em quanto tempo checa o teclado (seg)
# ===========================================================

import ctypes
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from PIL import ImageGrab
except ImportError:
    print("ERRO: falta a biblioteca Pillow.  Rode:  python -m pip install pillow")
    sys.exit(1)

# user32.dll e a parte do Windows que cuida de janelas e teclado.
user32 = ctypes.windll.user32


def tecla_esta_apertada(codigo_tecla: int) -> bool:
    """Pergunta ao Windows se a tecla esta pressionada NESTE instante.

    Funciona mesmo com o PES em foco, porque GetAsyncKeyState le o estado
    global do teclado - nao depende de qual janela esta na frente.
    O 0x8000 isola o bit que significa "pressionada agora".
    """
    return bool(user32.GetAsyncKeyState(codigo_tecla) & 0x8000)


def main() -> int:
    pasta = Path(PASTA_SAIDA)
    pasta.mkdir(exist_ok=True)   # cria a pasta se ainda nao existir

    print("=" * 62)
    print("  CAPTURA DE TELAS  --  Auto_PES21")
    print("=" * 62)
    print(f"\nSalvando em:  {pasta.resolve()}\n")
    print(f"  {NOME_TECLA_CAPTURA:4s} = tirar print da tela atual")
    print(f"  {NOME_TECLA_SAIR:4s} = encerrar\n")
    print("Pode voltar para o PES. Estou escutando o teclado...\n")

    contador = 0
    # Guardo se a tecla ja estava apertada no ciclo anterior. Sem isso, segurar
    # a tecla por meio segundo geraria uns 15 prints iguais.
    captura_ja_estava_apertada = False

    while True:
        if tecla_esta_apertada(TECLA_SAIR):
            break

        apertada_agora = tecla_esta_apertada(TECLA_CAPTURA)

        # So dispara na BORDA: quando passa de "solta" para "apertada".
        if apertada_agora and not captura_ja_estava_apertada:
            contador += 1
            carimbo = datetime.now().strftime("%H%M%S")
            nome = f"tela_{contador:03d}_{carimbo}.png"
            destino = pasta / nome

            imagem = ImageGrab.grab(all_screens=True)
            imagem.save(destino)

            print(f"  [{contador:03d}] salvo: {nome}   ({imagem.size[0]}x{imagem.size[1]})")

        captura_ja_estava_apertada = apertada_agora
        time.sleep(INTERVALO_LEITURA)

    print(f"\nEncerrado. {contador} tela(s) capturada(s) em:\n  {pasta.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
