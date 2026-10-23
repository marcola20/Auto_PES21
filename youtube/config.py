"""
config.py  --  RPA_Youtube

Tudo que voce pode querer trocar sem mexer no codigo.
"""

import configparser
import os
import shutil
import sys
from pathlib import Path

PASTA_PROJETO = Path(__file__).parent

# ==========================================================================
# CAMINHOS DESTE PC
# ==========================================================================

# Pastas que mudam de um computador para outro ficam em caminhos.ini, que NAO
# vai para o GitHub. Sem ele, o arquivo e criado a partir do exemplo e o
# script para, pedindo para conferir.
_ARQ_CAMINHOS = PASTA_PROJETO / "caminhos.ini"
if not _ARQ_CAMINHOS.exists():
    shutil.copyfile(PASTA_PROJETO / "caminhos.exemplo.ini", _ARQ_CAMINHOS)
    print(f"Criei o arquivo de caminhos deste PC:\n  {_ARQ_CAMINHOS}\n"
          "Abra ele, ajuste as pastas para o seu computador e rode de novo.")
    sys.exit(1)
# interpolation=None: "%" em nome de pasta nao vira variavel.
_ini = configparser.ConfigParser(interpolation=None)
_ini.read(_ARQ_CAMINHOS, encoding="utf-8")
_caminhos = _ini["caminhos"]


def _caminho(chave: str) -> str:
    """Valor do caminhos.ini; "~" vira a pasta do usuario. Vazio = ""."""
    valor = _caminhos.get(chave, "").strip().strip('"')
    return str(Path(valor).expanduser()) if valor else ""


def _achar_chrome() -> str:
    """Os lugares onde o instalador do Chrome costuma colocar o .exe."""
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                 os.environ.get("LOCALAPPDATA")):
        if base:
            exe = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if exe.is_file():
                return str(exe)
    return ""

# ==========================================================================
# VIDEOS
# ==========================================================================

# So os videos soltos nesta pasta entram. Subpastas (Copa, Enviados...) ficam
# de fora.
if not _caminho("pasta_videos"):
    sys.exit(f"ERRO: 'pasta_videos' esta vazio em {_ARQ_CAMINHOS}")
PASTA_VIDEOS = Path(_caminho("pasta_videos"))   # definida em caminhos.ini
EXTENSOES_VIDEO = (".mp4", ".mkv", ".mov")

# Depois de programado, o video vai para esta subpasta de PASTA_VIDEOS. Assim
# a proxima rodada nao sobe o mesmo jogo de novo.
SUBPASTA_ENVIADOS = "Enviados"

# Registro de tudo que ja foi programado (arquivo, tamanho, titulo, estreia).
# Serve de segunda trava contra duplicado, caso a mudanca de pasta falhe.
HISTORICO = PASTA_PROJETO / "historico.csv"

# ==========================================================================
# CAMPEONATO
# ==========================================================================

EDICAO = 8
TEMPORADA = 3

# A ordem daqui e a ordem do menu na hora de perguntar.
# nome     -> vai no fim do titulo do video
# playlist -> nome EXATO da playlist no canal (None = video nao entra em playlist)
# rodadas  -> o que o script aceita como resposta; "quartas", "semi" e "final"
#             viram "Quartas de Final", "Semifinal" e "Final" no titulo
COMPETICOES = {
    "serieA": {
        "nome": "Brasileirão - Série A",
        "playlist": f"Brasileirão - Série A | {TEMPORADA}ª Temporada | {EDICAO}ª Edição",
        "rodadas": [str(n) for n in range(1, 10)] + ["final"],
        "descricao": PASTA_PROJETO / "descricao_serieA.txt",
        "miniatura": PASTA_PROJETO / "capa_serieA.jpg",
    },
    "serieB": {
        "nome": "Brasileirão - Série B",
        "playlist": f"Brasileirão - Série B | {TEMPORADA}ª Temporada | {EDICAO}ª Edição",
        "rodadas": [str(n) for n in range(1, 8)] + ["final"],
        "descricao": PASTA_PROJETO / "descricao_serieB.txt",
        "miniatura": PASTA_PROJETO / "capa_serieB.jpg",
    },
    "copa": {
        "nome": "Copa do Brasil",
        "playlist": f"Copa do Brasil | {TEMPORADA}ª Temporada | {EDICAO}ª Edição",
        "rodadas": [str(n) for n in range(1, 5)] + ["quartas", "semi", "final"],
        "descricao": PASTA_PROJETO / "descricao_copa.txt",
        "miniatura": PASTA_PROJETO / "capa_copa.jpg",
    },
    "supercopa": {
        "nome": "Supercopa",
        "playlist": None,          # a Supercopa nao tem playlist
        "rodadas": ["final"],
        "descricao": PASTA_PROJETO / "descricao_supercopa.txt",
        "miniatura": PASTA_PROJETO / "capa_supercopa.jpg",
    },
}


def nome_playlist(competicao: str) -> str | None:
    return COMPETICOES[competicao]["playlist"]


# ==========================================================================
# ESTREIA
# ==========================================================================

MINUTOS_ENTRE_JOGOS = 20

# O YouTube recusa estreia no passado. Se, na hora de programar um video, a
# estreia dele estiver a menos disto do relogio, o script PARA.
MINUTOS_MARGEM_MINIMA = 10

# Textos exatamente como aparecem no YouTube Studio (em portugues).
CONTAGEM_REGRESSIVA = "1 minuto"
TEMA_ESTREIA = "Esportes"

# ==========================================================================
# NAVEGADOR
# ==========================================================================

# Em branco no caminhos.ini = procura nos lugares de instalacao padrao.
CHROME = _caminho("chrome") or _achar_chrome()

# Perfil separado do seu Chrome normal. O login do YouTube fica salvo aqui
# (rode login.py uma vez).
PERFIL_CHROME = PASTA_PROJETO / "perfil_chrome"
PORTA_DEPURACAO = 9333

# Paciencia maxima para o upload de UM video terminar (arquivos de 2-3 GB).
MINUTOS_LIMITE_UPLOAD = 120

PASTA_DIAGNOSTICO = PASTA_PROJETO / "diagnostico"
