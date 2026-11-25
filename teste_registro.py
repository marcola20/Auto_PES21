"""
teste_registro.py  --  Auto_PES21 / testar o passo do Registro individual

Roda no jogo de verdade o mesmo codigo que o rodar_jogos.py usa depois de cada
partida: entra em "Registro individual de jogo", fotografa cada jogador dos
dois times (Baixo, R1 para o outro time) e sai com Esc.

Antes de deixar o loop rodar sozinho, isto confere o que so da para ver no
jogo: se o titulo da tela e reconhecido na captura ao vivo (o modelo saiu de
um video), se o R1 troca de time, se os reservas entram nas fotos e se o Esc
deixa o cursor no botao do Registro.

COMO USAR:
  Deixe o PES parado no MENU DE FIM DE JOGO, com "Jogar novamente" marcado
  (como fica logo depois de uma partida). De preferencia uma partida que
  teve substituicao, para os reservas aparecerem.
  Rode, volte para o jogo durante a contagem e nao mexa em nada.

  Ao final, confira no jogo se o cursor esta em "Registro individual de
  jogo", e abra a pasta das fotos para ver se tem todos os jogadores.
  O teste NAO volta para a selecao de times e nao confirma nada no menu.
"""

# ====================== CONFIGURACOES ======================
SEGUNDOS_CONTAGEM = 8
PASTA_SAIDA = "teste_registro_fotos"
# ===========================================================

import json
import shutil
import sys
import time
from pathlib import Path

import rodar_jogos
import visao


def main() -> int:
    pasta = Path(PASTA_SAIDA)
    if pasta.exists():
        shutil.rmtree(pasta)

    print(__doc__.split("COMO USAR:")[1].split("Ao final")[0])
    rodar_jogos.contagem_regressiva(SEGUNDOS_CONTAGEM)

    # A medida que decide se a tela foi reconhecida, para calibrar se precisar.
    original = rodar_jogos.ler_registro

    def ler_e_medir():
        tela = visao.capturar_tela()
        modelo = visao.mascara_texto_branco(
            visao.carregar_template(rodar_jogos.TEMPLATE_REGISTRO))
        titulo = visao.mascara_texto_branco(
            tela.crop(visao.REGIAO_TITULO_REGISTRO))
        print(f"      (titulo {visao.sobreposicao(titulo, modelo):.3f}, "
              f"linha selecionada "
              f"{visao.linha_selecionada_no_registro(tela)})")
        return original()

    rodar_jogos.ler_registro = ler_e_medir
    ok = rodar_jogos.registrar_jogadores(pasta, {"teste": True})
    rodar_jogos.ler_registro = original

    print()
    resumo = pasta / "jogadores.json"
    if resumo.exists():
        for t in json.loads(resumo.read_text(encoding="utf-8"))["times"]:
            print(f"  time {t['numero']}: {len(t['fotos'])} fotos")
    else:
        print("  nenhuma foto salva")
    print(f"  fotos em: {pasta.resolve()}")
    if ok:
        print("  Saiu do Registro. Confira no jogo: o cursor deve estar em")
        print("  'Registro individual de jogo'.")
    else:
        print("  FALHOU - a tela ficou presa no Registro.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
