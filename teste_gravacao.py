"""
teste_gravacao.py  --  Etapa 1 do projeto Auto_PES21

Objetivo deste script: provar que o Python consegue apertar Alt+F9 e que a
NVIDIA realmente comeca e para de gravar, gerando um arquivo novo na pasta.

Ele NAO mexe em menu nenhum do PES ainda. E so um teste do "gatilho".
"""

# ==========================================================================
# CONFIGURACOES  --  mude so aqui em cima
# ==========================================================================

# Pasta onde a NVIDIA salva os videos. O "r" antes das aspas faz o Python
# tratar a \ como barra normal, e nao como caractere especial.
PASTA_GRAVACOES = r"C:\Users\Marcola\Videos\NVIDIA\eFootball PES 2021"

# Extensoes que contam como "video". Em minusculo, com o ponto.
EXTENSOES_VIDEO = (".mp4", ".mkv", ".mov", ".avi")

SEGUNDOS_CONTAGEM   = 10   # tempo para voce clicar na janela do PES
SEGUNDOS_GRAVANDO   = 15   # quanto tempo a gravacao de teste vai durar
SEGUNDOS_SALVANDO   = 8    # espera depois do stop, para a NVIDIA fechar o arquivo
SEGUNDOS_EXTRA_BUSCA = 20  # se o arquivo demorar, procura por ate mais esse tanto

# Pausas dentro do Alt+F9. Se a NVIDIA nao responder, aumente um pouco.
PAUSA_DEPOIS_ALT_DOWN = 0.20   # depois de segurar o Alt
PAUSA_F9_PRESSIONADO  = 0.10   # com o F9 apertado
PAUSA_ANTES_ALT_UP    = 0.20   # antes de soltar o Alt

# ==========================================================================
# Daqui para baixo e o codigo. Nao precisa mexer.
# ==========================================================================

import sys
import time
from pathlib import Path

try:
    import pydirectinput
except ImportError:
    print("ERRO: a biblioteca 'pydirectinput' nao esta instalada.")
    print("Rode no terminal:  python -m pip install pydirectinput")
    sys.exit(1)

# O pydirectinput coloca uma pausa automatica depois de CADA comando.
# Deixo explicito aqui para o tempo do Alt+F9 ficar previsivel.
pydirectinput.PAUSE = 0.05
# Desliga a "trava de seguranca" que aborta se o mouse for pro canto da tela.
pydirectinput.FAILSAFE = False


def listar_videos(pasta: Path) -> dict:
    """Varre a pasta e TODAS as subpastas e devolve os videos encontrados.

    Devolve um dicionario no formato {caminho_do_arquivo: tamanho_em_bytes}.
    Uso dicionario em vez de lista porque assim, alem de saber quais arquivos
    existem, eu tambem sei o tamanho de cada um - util para detectar um
    arquivo que ainda esta sendo escrito.
    """
    encontrados = {}
    # rglob("*") = tudo que esta dentro da pasta, recursivamente.
    for caminho in pasta.rglob("*"):
        if caminho.is_file() and caminho.suffix.lower() in EXTENSOES_VIDEO:
            try:
                encontrados[caminho] = caminho.stat().st_size
            except OSError:
                # Arquivo sumiu ou esta travado bem nesse instante. Ignora.
                pass
    return encontrados


def apertar_alt_f9() -> None:
    """Envia Alt+F9 segurando o Alt, apertando F9 e so depois soltando o Alt.

    Fazer em 3 passos separados (em vez de um atalho pronto) e mais confiavel
    com overlays de jogo, que costumam ler o estado real das teclas.
    """
    pydirectinput.keyDown("alt")
    time.sleep(PAUSA_DEPOIS_ALT_DOWN)

    pydirectinput.keyDown("f9")
    time.sleep(PAUSA_F9_PRESSIONADO)
    pydirectinput.keyUp("f9")

    time.sleep(PAUSA_ANTES_ALT_UP)
    pydirectinput.keyUp("alt")


def contagem_regressiva(segundos: int) -> None:
    """Conta de 'segundos' ate 0 escrevendo tudo na mesma linha do terminal."""
    for restante in range(segundos, 0, -1):
        # end="" impede a quebra de linha; \r volta o cursor para o inicio.
        print(f"  Clique na janela do PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando agora!                     ")


def esperar_arquivo_estabilizar(caminho: Path, tentativas: int = 10) -> bool:
    """Espera o tamanho do arquivo parar de crescer (= NVIDIA terminou de salvar)."""
    tamanho_anterior = -1
    for _ in range(tentativas):
        try:
            tamanho_atual = caminho.stat().st_size
        except OSError:
            return False
        if tamanho_atual == tamanho_anterior and tamanho_atual > 0:
            return True
        tamanho_anterior = tamanho_atual
        time.sleep(1)
    return False


def main() -> int:
    """Roda o teste inteiro. Devolve 0 se deu certo, 1 se deu errado."""
    print("=" * 62)
    print("  TESTE DE GRAVACAO  --  Auto_PES21 / etapa 1")
    print("=" * 62)

    pasta = Path(PASTA_GRAVACOES)
    if not pasta.is_dir():
        print(f"\nERRO: a pasta abaixo nao existe:\n  {pasta}")
        print("Confira o caminho em PASTA_GRAVACOES, la no topo do script.")
        return 1

    print(f"\nPasta monitorada:\n  {pasta}\n")

    # --- Passo 1: contagem regressiva -------------------------------------
    print(f"[1/6] Voce tem {SEGUNDOS_CONTAGEM}s para deixar o PES em foco.")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    # --- Passo 2: fotografia do "antes" -----------------------------------
    antes = listar_videos(pasta)
    print(f"\n[2/6] Videos que ja existiam na pasta: {len(antes)}")

    # --- Passo 3: iniciar gravacao ----------------------------------------
    print("[3/6] Enviando Alt+F9 (INICIAR gravacao)...")
    apertar_alt_f9()

    # --- Passo 4: esperar ---------------------------------------------------
    print(f"[4/6] Gravando por {SEGUNDOS_GRAVANDO}s...")
    contagem_regressiva(SEGUNDOS_GRAVANDO)

    # --- Passo 5: parar gravacao -------------------------------------------
    print("[5/6] Enviando Alt+F9 (PARAR gravacao)...")
    apertar_alt_f9()

    # --- Passo 6: conferir se nasceu arquivo novo --------------------------
    print(f"[6/6] Esperando {SEGUNDOS_SALVANDO}s para a NVIDIA salvar o arquivo...")
    time.sleep(SEGUNDOS_SALVANDO)

    novos = []
    limite = time.time() + SEGUNDOS_EXTRA_BUSCA
    while True:
        depois = listar_videos(pasta)
        # Um arquivo e "novo" se o caminho dele nao existia na fotografia inicial.
        novos = [c for c in depois if c not in antes]
        if novos or time.time() > limite:
            break
        print("  ...ainda nao apareceu, procurando de novo", end="\r", flush=True)
        time.sleep(2)

    print(" " * 60, end="\r")
    print("\n" + "-" * 62)

    if not novos:
        print("RESULTADO: FALHOU  -  nenhum video novo apareceu.")
        print("-" * 62)
        print("Possiveis causas (veja a lista de diagnostico no chat):")
        print("  - O PES nao estava em foco quando o Alt+F9 foi enviado.")
        print("  - O script precisa rodar como Administrador.")
        print("  - O atalho Alt+F9 esta diferente na NVIDIA App.")
        print("  - A gravacao ja estava LIGADA antes do teste (ficou dessincronizada).")
        return 1

    print(f"RESULTADO: OK  -  {len(novos)} arquivo(s) novo(s) encontrado(s):")
    for caminho in novos:
        esperar_arquivo_estabilizar(caminho)
        tamanho_mb = caminho.stat().st_size / (1024 * 1024)
        print(f"  - {caminho.name}")
        print(f"      pasta : {caminho.parent}")
        print(f"      tamanho: {tamanho_mb:.1f} MB")
    print("-" * 62)
    print("Abra o video e confira se ele tem mesmo ~{}s de duracao.".format(SEGUNDOS_GRAVANDO))
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
