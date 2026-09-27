"""
caminhos.py  --  Auto_PES21

Os caminhos que mudam de um PC para outro (pasta do PES, pasta dos videos)
ficam em caminhos.ini, que NAO vai para o GitHub. Cada um tem o seu.

Na primeira vez que qualquer script roda sem caminhos.ini, ele e criado a
partir de caminhos.exemplo.ini e o script para, pedindo para voce conferir.
"""

import configparser
import shutil
import sys
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO = PASTA_PROJETO / "caminhos.ini"
EXEMPLO = PASTA_PROJETO / "caminhos.exemplo.ini"


def _carregar() -> configparser.SectionProxy:
    if not ARQUIVO.exists():
        shutil.copyfile(EXEMPLO, ARQUIVO)
        print(f"Criei o arquivo de caminhos deste PC:\n  {ARQUIVO}\n"
              "Abra ele, ajuste as pastas para o seu computador e rode de novo.")
        sys.exit(1)
    # interpolation=None: "%" em nome de pasta nao vira variavel.
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ARQUIVO, encoding="utf-8")
    return ini["caminhos"]


_ini = _carregar()


def _pasta(chave: str) -> str:
    valor = _ini.get(chave, "").strip().strip('"')
    if not valor:
        print(f"ERRO: '{chave}' esta vazio em {ARQUIVO}")
        sys.exit(1)
    # "~" vira a pasta do usuario (C:\Users\<nome>), para o exemplo servir
    # em qualquer PC.
    return str(Path(valor).expanduser())


PASTA_PES    = _pasta("pasta_pes")
PASTA_SIDER  = _pasta("pasta_sider")
PASTA_VIDEOS = _pasta("pasta_videos")
