"""
empacotar.py  --  Auto_PES21

Monta o pacote para quem nao programa: uma pasta com o codigo E um Python
proprio (com Pillow, pydirectinput, playwright e ffmpeg ja instalados). Quem
baixa so descompacta e da dois cliques em "Abrir painel.bat".

Gera, em dist/:
  Auto_PES21-v<versao>.zip  -> o pacote completo (primeiro download)
  codigo.zip                -> so o codigo; e o que o painel baixa para
                               atualizar (atualizar.py)

Normalmente quem roda e o GitHub (.github/workflows/release.yml), quando voce
publica uma tag:  git tag v1.2.0  e  git push origin v1.2.0

Para testar aqui:
  python empacotar.py 1.0.0

Entram so os arquivos que estao no git (git ls-files): os dados deste PC
(caminhos.ini, fila, historico, login do Chrome) ficam de fora sozinhos.
"""

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_BUILD = PASTA_PROJETO / "build"
PASTA_DIST = PASTA_PROJETO / "dist"
NOME = "Auto_PES21"

# Do git, mas nao servem para quem so usa.
FORA_DO_PACOTE = (".github/", ".gitignore", "youtube/.gitignore")

URL_PYTHON = "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip"

LEIA_ME = """\
AUTO PES21  -  versao {versao}

1. Descompacte esta pasta onde quiser (ex.: Documentos). Evite
   "Arquivos de Programas": o robo grava a fila e o historico aqui dentro.
2. Dois cliques em "Abrir painel.bat". O painel abre no navegador.
3. Aba Configuracao: confira as pastas do PES, do sider e dos videos, e
   cole o endereco e o token do site. Ali tambem tem o botao
   "Criar atalho na Area de Trabalho".
4. YouTube: na aba YouTube, "Entrar na conta do canal" (uma vez).

Atualizacao: quando sair versao nova, o painel mostra uma faixa verde no
topo. Um clique e pronto - seus dados continuam como estao.

Se o Windows disser "O Windows protegeu o computador": "Mais informacoes"
e "Executar assim mesmo". O programa nao tem assinatura digital (paga).
"""


def limpar(pasta: Path) -> None:
    """Apaga a saida da rodada anterior; para com mensagem clara se nao der
    (pasta aberta no Explorer ou num terminal)."""
    if pasta.exists():
        try:
            shutil.rmtree(pasta)
        except OSError as erro:
            sys.exit(f"ERRO: nao consegui apagar {pasta} (aberta em outro programa?): {erro}")


def arquivos_do_git() -> list[str]:
    saida = subprocess.run(["git", "ls-files", "-z"], cwd=PASTA_PROJETO, check=True,
                           capture_output=True).stdout.decode("utf-8")
    nomes = [n for n in saida.split("\0") if n]
    return sorted(n for n in nomes
                  if not any(n == f or n.startswith(f) for f in FORA_DO_PACOTE)
                  and (PASTA_PROJETO / n).is_file())


def baixar(url: str, destino: Path) -> Path:
    if destino.is_file():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {url}")
    temporario = destino.with_suffix(".part")
    pedido = urllib.request.Request(url, headers={"User-Agent": "Auto_PES21-empacotar"})
    with urllib.request.urlopen(pedido, timeout=120) as r, open(temporario, "wb") as f:
        shutil.copyfileobj(r, f)
    temporario.replace(destino)
    return destino


def montar_python(pasta: Path, versao_python: str) -> None:
    """Python 'embeddable' oficial + as bibliotecas do requirements.txt."""
    zip_python = baixar(URL_PYTHON.format(v=versao_python),
                        PASTA_BUILD / "cache" / f"python-{versao_python}-embed-amd64.zip")
    with zipfile.ZipFile(zip_python) as z:
        z.extractall(pasta)
    # O ._pth deixa o Python "isolado": ele nao poe a pasta do script no
    # sys.path, e os scripts de youtube/ importam os vizinhos (config,
    # studio). Sem o ._pth ele acha a biblioteca padrao pelo pythonXY.zip ao
    # lado do .exe e o site-packages em Lib/, como um Python normal.
    for pth in pasta.glob("python*._pth"):
        pth.unlink()
    site_packages = pasta / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    print("Instalando as bibliotecas no Python do pacote...")
    # O pip vai junto: a atualizacao instala biblioteca nova se o
    # requirements.txt mudar.
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-warn-script-location", "--target", str(site_packages),
                    "-r", str(PASTA_PROJETO / "requirements.txt"), "pip"], check=True)
    for lixo in site_packages.rglob("__pycache__"):
        shutil.rmtree(lixo, ignore_errors=True)
    # Se o PC tiver outro Python 3.x igual, as bibliotecas "do usuario" dele
    # (AppData\Roaming\Python) entrariam no caminho e poderiam ganhar das do
    # pacote. O Python roda o sitecustomize sozinho ao abrir.
    (site_packages / "sitecustomize.py").write_text(
        "# Gerado pelo empacotar.py: o Python do pacote usa so as bibliotecas dele.\n"
        "import site, sys\n"
        "if site.USER_SITE in sys.path:\n"
        "    sys.path.remove(site.USER_SITE)\n", encoding="utf-8")


def conferir_python(pasta: Path) -> None:
    """Roda o Python do pacote importando tudo que os scripts usam."""
    teste = ("import sys, site, ctypes, sqlite3, PIL.Image, pydirectinput, playwright.sync_api, imageio_ffmpeg; "
             "import winrt.windows.media.ocr, winrt.windows.globalization, winrt.windows.graphics.imaging, "
             "winrt.windows.storage.streams; "
             "assert site.USER_SITE not in sys.path, 'site do usuario no caminho'; "
             "assert PIL.__file__.startswith(sys.prefix), 'Pillow de fora do pacote'; "
             "print(sys.version.split()[0], imageio_ffmpeg.get_ffmpeg_exe())")
    resultado = subprocess.run([str(pasta / "python.exe"), "-c", teste],
                               capture_output=True, text=True, cwd=pasta.parent)
    if resultado.returncode != 0:
        sys.exit(f"ERRO: o Python do pacote nao importou as bibliotecas:\n{resultado.stderr}")
    print(f"Python do pacote ok: {resultado.stdout.strip()}")


def zipar(pasta: Path, destino: Path, raiz: str = "") -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, str(Path(raiz) / arquivo.relative_to(pasta)))
    print(f"  {destino.relative_to(PASTA_PROJETO)}  ({destino.stat().st_size / 1024**2:.1f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monta o pacote do Auto_PES21.")
    parser.add_argument("versao", help="ex.: 1.2.0 (o v da tag pode vir junto)")
    parser.add_argument("--python", default=sys.version.split()[0],
                        help="versao do Python embutido (padrao: a deste Python)")
    parser.add_argument("--sem-python", action="store_true", help="so o codigo.zip (rapido)")
    args = parser.parse_args()
    versao = args.versao.lstrip("vV")
    if not versao[:1].isdigit():
        sys.exit(f"versao invalida: {args.versao}")

    arquivos = arquivos_do_git()
    if "painel.py" not in arquivos or "requirements.txt" not in arquivos:
        sys.exit("ERRO: painel.py e requirements.txt precisam estar no git")

    codigo = PASTA_BUILD / "codigo"
    limpar(codigo)
    for nome in arquivos:
        destino = codigo / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PASTA_PROJETO / nome, destino)
    (codigo / "VERSAO").write_text(versao + "\n", encoding="utf-8")
    (codigo / "MANIFESTO.txt").write_text("\n".join(arquivos) + "\n", encoding="utf-8")

    limpar(PASTA_DIST)
    print(f"Versao {versao}: {len(arquivos)} arquivos de codigo")
    zipar(codigo, PASTA_DIST / "codigo.zip")
    if args.sem_python:
        return 0

    completo = PASTA_BUILD / NOME
    limpar(completo)
    shutil.copytree(codigo, completo)
    (completo / "LEIA-ME.txt").write_text(LEIA_ME.format(versao=versao), encoding="utf-8")
    montar_python(completo / "python", args.python)
    conferir_python(completo / "python")
    zipar(completo, PASTA_DIST / f"{NOME}-v{versao}.zip", raiz=NOME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
