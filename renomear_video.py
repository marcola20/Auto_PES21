"""
renomear_video.py  --  Auto_PES21

Renomeia UM video ja gravado para "Casa vs Fora", usando a mesma funcao do
loop (rodar_jogos.renomear_video). Serve para dois usos:
  - testar a renomeacao num video real antes de confiar nela no loop;
  - corrigir na mao um video que o loop nao conseguiu renomear.

Uso (o nome do arquivo e o da pasta de gravacoes, entre aspas):
  python renomear_video.py "eFootball PES 2021 2026.09.16 - 11.07.14.13.mp4" Corinthians Gremio

Time com espaco no nome tambem vai entre aspas: "Sao Paulo".
Jogo fora da liga: um quarto argumento com a competicao, ex. Supercopa.
"""

import sys
from pathlib import Path

import rodar_jogos
import times


def main() -> int:
    if len(sys.argv) not in (4, 5):
        print(__doc__)
        return 1
    arquivo, casa, fora = sys.argv[1:4]
    competicao = sys.argv[4] if len(sys.argv) == 5 else None

    caminho = Path(rodar_jogos.PASTA_GRAVACOES) / arquivo
    if not caminho.is_file():
        print(f"ERRO: nao achei o video:\n  {caminho}")
        return 1
    try:
        times.indice_do_time(casa)
        times.indice_do_time(fora)
    except ValueError as erro:
        print(f"ERRO: {erro}")
        return 1

    novo = rodar_jogos.renomear_video(caminho, casa, fora, competicao)
    if novo is None:
        return 1
    print(f"OK:\n  {caminho.name}\n  -> {novo.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
