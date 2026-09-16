"""
calibrar_painel.py  --  Auto_PES21

Refaz os templates dos paineis que aparecem DENTRO da partida. Eles tambem
seguem o tema visual do jogo, entao trocaram junto com os menus.

Cada um so pode ser capturado quando esta na tela, e eles aparecem em momentos
diferentes da partida. Por isso o script captura UM por vez, e voce roda cada
comando no momento em que aquela tela estiver aberta:

    python calibrar_painel.py intervalo   (no painel escuro do INTERVALO)
    python calibrar_painel.py fim         (no painel escuro de FIM DE JOGO)
    python calibrar_painel.py replay      (durante um replay, com a caixa de
                                           informacao na tela)
    python calibrar_painel.py formacao    (na tela de FORMACAO/escalacao, com
                                           o quadro ja parado de animar)

Depois de capturar intervalo E fim, o script compara os dois e diz se da para
diferenciar um do outro - que e a conta que faz a deteccao funcionar.
"""

# ====================== CONFIGURACOES ======================
SEGUNDOS_CONTAGEM = 8
# ===========================================================

import sys
import time
from pathlib import Path

import visao

# Cada painel: (arquivo do template, regiao da tela, se o texto e branco)
PAINEIS = {
    "intervalo": ("templates/intervalo_escuro.png", visao.REGIAO_FIM_DE_JOGO, True),
    "fim":       ("templates/fim_de_jogo.png",      visao.REGIAO_FIM_DE_JOGO, True),
    "replay":    ("templates/replay_caixa.png",     visao.REGIAO_REPLAY,      False),
    # A formacao usa False porque suas letras sao cinza, nao brancas: ali a
    # conferencia e de CONTRASTE, so para nao salvar um retangulo liso.
    "formacao":  ("templates/formacao.png",         visao.REGIAO_FORMACAO,    False),
}

ALVO = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""
if ALVO not in PAINEIS:
    print("ERRO: diga qual painel capturar.")
    print("\nUso:")
    print("  python calibrar_painel.py intervalo   (no painel escuro do INTERVALO)")
    print("  python calibrar_painel.py fim         (no painel escuro de FIM DE JOGO)")
    print("  python calibrar_painel.py replay      (durante um replay)")
    print("  python calibrar_painel.py formacao    (na tela de FORMACAO,")
    print("                                         com o quadro ja parado)")
    sys.exit(1)

CAMINHO, REGIAO, TEM_TEXTO_BRANCO = PAINEIS[ALVO]


def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Capturando!                      ")


def comparar_intervalo_e_fim() -> None:
    """Confere que os dois paineis dao para ser diferenciados.

    Eles ficam na MESMA posicao da tela e so mudam a palavra do titulo, entao
    esta e a conta que sustenta a deteccao inteira. No tema antigo a diferenca
    era 47.6, com o limiar em 15.
    """
    a = Path(PAINEIS["intervalo"][0])
    b = Path(PAINEIS["fim"][0])
    if not (a.is_file() and b.is_file()):
        return

    dif = visao.diferenca_de_pixels(
        visao.carregar_template(a), visao.carregar_template(b))
    print("\n" + "-" * 66)
    print(f"Intervalo x Fim de jogo: diferenca {dif:.2f}  "
          f"(limiar de deteccao: {visao.LIMIAR_FIM_DE_JOGO})")
    if dif > visao.LIMIAR_FIM_DE_JOGO * 2:
        print("OK - bem separados, a deteccao consegue distinguir os dois.")
    else:
        print("ATENCAO - MUITO parecidos. Um pode ser confundido com o outro.")
        print("Confira se voce capturou as duas telas certas, e nao a mesma")
        print("tela duas vezes.")


def main() -> int:
    print("=" * 66)
    print(f"  CALIBRACAO DE PAINEL  --  '{ALVO}'")
    print("=" * 66)
    print(f"\nDeixe o PES na tela do painel '{ALVO}'.")
    print(f"Regiao que vou recortar: {REGIAO}\n")
    contagem_regressiva(SEGUNDOS_CONTAGEM)

    tela = visao.capturar_tela()
    recorte = tela.crop(REGIAO)

    # Confere que ha CONTEUDO ali, para nao salvar um retangulo vazio como
    # template - isso passaria despercebido e so quebraria na proxima partida.
    if TEM_TEXTO_BRANCO:
        marcados = sum(visao.mascara_texto_branco(recorte))
        if marcados < 100:
            print(f"\nFALHOU - so {marcados} pixels de texto branco na regiao.")
            print("O painel esta mesmo na tela? O jogo esta em 1920x1080?")
            tela.save(f"diagnostico_{ALVO}.png")
            print(f"Salvei a tela inteira em diagnostico_{ALVO}.png para eu ver.")
            return 1
        print(f"\n      {marcados} pixels de texto branco encontrados")

    Path(CAMINHO).parent.mkdir(parents=True, exist_ok=True)
    recorte.save(CAMINHO)
    print(f"      template salvo em {CAMINHO}")

    if ALVO in ("intervalo", "fim"):
        comparar_intervalo_e_fim()

    print("\n" + "-" * 66)
    print(f"RESULTADO: OK - '{ALVO}' capturado.")
    print("-" * 66)
    print(f"ABRA {CAMINHO} e confirme que e mesmo o painel certo.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
