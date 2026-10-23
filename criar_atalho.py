"""
criar_atalho.py  --  Auto_PES21

Cria na Area de Trabalho o atalho "Auto PES21", que abre o painel com um
clique duplo, sem janela preta de terminal.

Por que um atalho e nao um .exe: o projeto se atualiza com git pull. Um .exe
(PyInstaller) congelaria uma copia do codigo e precisaria ser refeito a cada
atualizacao - e antivirus costuma desconfiar dele. O atalho so aponta para o
pythonw.exe deste PC e para o painel.py desta pasta, entao sempre abre a
versao atual.

Uso (uma vez; ou pelo painel, aba Configuracao):
  python criar_atalho.py

Se o Python for reinstalado em outra pasta, o atalho para de abrir: e so
criar de novo.
"""

import os
import subprocess
import sys
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
NOME_DO_ATALHO = "Auto PES21.lnk"
ICONE = PASTA_PROJETO / "painel" / "icone.ico"

# WScript.Shell e o jeito do proprio Windows de gravar um .lnk. Os valores vao
# por variavel de ambiente para pasta com espaco ou acento nao quebrar o
# comando.
SCRIPT_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$area = [Environment]::GetFolderPath('Desktop')
$caminho = Join-Path $area $env:ATALHO_NOME
$atalho = (New-Object -ComObject WScript.Shell).CreateShortcut($caminho)
$atalho.TargetPath = $env:ATALHO_ALVO
$atalho.Arguments = '"' + $env:ATALHO_SCRIPT + '"'
$atalho.WorkingDirectory = $env:ATALHO_PASTA
$atalho.IconLocation = $env:ATALHO_ICONE
$atalho.Description = 'Painel do Auto PES21'
$atalho.Save()
Write-Output $caminho
"""


def pythonw() -> Path:
    """O pythonw.exe (Python sem janela) ao lado do Python que roda este script."""
    atual = Path(sys.executable)
    candidato = atual.with_name("pythonw.exe")
    return candidato if candidato.is_file() else atual


def criar_atalho() -> Path:
    """Grava (ou regrava) o atalho e devolve onde ele ficou."""
    ambiente = dict(
        os.environ,
        ATALHO_NOME=NOME_DO_ATALHO,
        ATALHO_ALVO=str(pythonw()),
        ATALHO_SCRIPT=str(PASTA_PROJETO / "painel.py"),
        ATALHO_PASTA=str(PASTA_PROJETO),
        ATALHO_ICONE=str(ICONE),
    )
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", SCRIPT_POWERSHELL],
        env=ambiente, capture_output=True, text=True, errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if resultado.returncode != 0:
        raise OSError(f"nao consegui criar o atalho: {resultado.stderr.strip()[:300]}")
    return Path(resultado.stdout.strip().splitlines()[-1])


def main() -> int:
    try:
        caminho = criar_atalho()
    except OSError as erro:
        print(f"ERRO: {erro}")
        return 1
    print(f"Atalho criado: {caminho}")
    print("Clique duas vezes nele para abrir o painel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
