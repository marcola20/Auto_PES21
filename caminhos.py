"""
caminhos.py  --  Auto_PES21

Os caminhos que mudam de um PC para outro (pasta do PES, pasta dos videos)
ficam em caminhos.ini, que NAO vai para o GitHub. Cada um tem o seu. O
endereco e o token do site ([site]) ficam no mesmo arquivo pelo mesmo
motivo: sao deste PC, e o token nao pode ir para o GitHub.

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


def _carregar() -> configparser.ConfigParser:
    if not ARQUIVO.exists():
        shutil.copyfile(EXEMPLO, ARQUIVO)
        print(f"Criei o arquivo de caminhos deste PC:\n  {ARQUIVO}\n"
              "Abra ele, ajuste as pastas para o seu computador e rode de novo.")
        sys.exit(1)
    # interpolation=None: "%" em nome de pasta (ou no token) nao vira variavel.
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ARQUIVO, encoding="utf-8")
    return ini


_arquivo = _carregar()
_ini = _arquivo["caminhos"]


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

# Opcionais: o enviar_resultados.py usa os dois, e avisa se faltarem; o
# extrair_eventos.py usa a url para ler os elencos atuais dos times.
# Um caminhos.ini antigo, sem a secao [site], continua valendo.
SITE_URL   = _arquivo.get("site", "url", fallback="").strip().strip('"')
SITE_TOKEN = _arquivo.get("site", "token", fallback="").strip().strip('"')

# Opcional: base de jogadores do PES que o site usa (pes-jogadores.json.gz).
# O extrair_eventos.py corrige os nomes lidos pelo elenco de cada time; sem
# ela, os nomes ficam como o OCR leu.
_base = _arquivo.get("site", "base_jogadores", fallback="").strip().strip('"')
BASE_JOGADORES = str(Path(_base).expanduser()) if _base else ""
