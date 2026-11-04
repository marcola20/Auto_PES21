"""
atualizar.py  --  Auto_PES21

Atualiza a copia instalada (o zip baixado das releases do GitHub) para a
ultima versao publicada. O painel usa: mostra a faixa "Versao nova" e chama
aplicar() quando voce clica.

So mexe nos arquivos de CODIGO: os que estao no MANIFESTO.txt da versao
nova (a lista que o empacotar.py grava, igual aos arquivos do git). Os dados
deste PC (caminhos.ini, fila, gravacoes, historico.csv, login do Chrome...)
nunca estao nessa lista, entao nunca sao tocados.

Na pasta de desenvolvimento (um checkout do git, com .git) nao faz nada: ali
quem atualiza e o git pull, e quem publica versao nova e voce.

Uso pelo terminal:
  python atualizar.py            -> diz se tem versao nova
  python atualizar.py --aplicar  -> baixa e aplica
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPOSITORIO = "marcola20/Auto_PES21"
URL_ULTIMA = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
NOME_PACOTE_CODIGO = "codigo.zip"     # asset da release so com o codigo

PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO_VERSAO = PASTA_PROJETO / "VERSAO"
ARQUIVO_MANIFESTO = PASTA_PROJETO / "MANIFESTO.txt"
REQUISITOS = "requirements.txt"

SEGUNDOS_TIMEOUT = 30

# Segunda trava, alem do manifesto: mesmo que um dia algum destes entre por
# engano no pacote, a atualizacao nao grava por cima.
NUNCA_SOBRESCREVER = {
    "caminhos.ini", "fila_jogos.json", "gravacoes.json", "resultados_enviados.json",
    "elencos_site.json", "videos_atribuidos.json", "plano_youtube.json",
    "youtube/historico.csv",
}
PASTAS_NUNCA = ("youtube/perfil_chrome", "diagnostico", "telas", "python/", ".git/")


class ErroAtualizacao(Exception):
    pass


def versao_local() -> str:
    """'dev' na pasta de desenvolvimento (sem VERSAO, que so o pacote tem)."""
    try:
        return ARQUIVO_VERSAO.read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


def e_desenvolvimento() -> bool:
    return (PASTA_PROJETO / ".git").exists() or versao_local() == "dev"


def _numeros(versao: str) -> tuple:
    """'v1.10.2' -> (1, 10, 2). Compara numero a numero: 1.10 e maior que 1.9."""
    partes = []
    for parte in versao.strip().lstrip("vV").split("."):
        digitos = "".join(c for c in parte if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def _pedir(url: str, aceitar: str = "application/vnd.github+json"):
    pedido = urllib.request.Request(url, headers={"User-Agent": "Auto_PES21", "Accept": aceitar})
    return urllib.request.urlopen(pedido, timeout=SEGUNDOS_TIMEOUT)


def procurar() -> dict:
    """O que a pagina precisa saber sobre atualizacao.

    {"local", "nova" (ou None), "notas", "pode_aplicar", "motivo"}. Nunca
    levanta erro: sem internet ou sem release, so nao ha versao nova."""
    local = versao_local()
    resposta = {"local": local, "nova": None, "notas": "", "pode_aplicar": False, "motivo": ""}
    if e_desenvolvimento():
        resposta["motivo"] = "pasta de desenvolvimento (atualize com git pull)"
        return resposta
    try:
        with _pedir(URL_ULTIMA) as r:
            release = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        resposta["motivo"] = "nenhuma versao publicada ainda" if erro.code == 404 else f"GitHub respondeu {erro.code}"
        return resposta
    except (OSError, ValueError) as erro:
        resposta["motivo"] = f"sem contato com o GitHub ({erro})"
        return resposta

    nova = str(release.get("tag_name") or "").lstrip("vV")
    if not nova or _numeros(nova) <= _numeros(local):
        return resposta
    asset = next((a for a in release.get("assets") or [] if a.get("name") == NOME_PACOTE_CODIGO), None)
    resposta.update(nova=nova, notas=str(release.get("body") or "").strip()[:4000])
    if asset is None:
        resposta["motivo"] = f"a versao {nova} nao tem o {NOME_PACOTE_CODIGO}"
        return resposta
    resposta.update(pode_aplicar=True, url=asset["browser_download_url"])
    return resposta


def _seguro(relativo: str) -> bool:
    """Caminho do zip que pode ser gravado na pasta do projeto."""
    if not relativo or relativo.startswith(("/", "\\")) or ":" in relativo:
        return False
    partes = Path(relativo).parts
    if ".." in partes:
        return False
    rel = "/".join(partes)
    if rel in NUNCA_SOBRESCREVER:
        return False
    return not any(rel == p.rstrip("/") or rel.startswith(p.rstrip("/") + "/") for p in PASTAS_NUNCA)


def _ler_manifesto(caminho: Path) -> list[str]:
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError:
        return []
    return [linha.strip() for linha in texto.splitlines() if linha.strip()]


def _md5(caminho: Path) -> str | None:
    try:
        return hashlib.md5(caminho.read_bytes()).hexdigest()
    except OSError:
        return None


def python_do_pacote() -> str:
    """python.exe (com terminal) ao lado de quem esta rodando, para o pip."""
    atual = Path(sys.executable)
    if atual.name.lower() == "pythonw.exe" and atual.with_name("python.exe").is_file():
        return str(atual.with_name("python.exe"))
    return str(atual)


def aplicar_zip(zip_codigo: Path, falar=print) -> str:
    """Aplica um codigo.zip ja baixado. Devolve a versao instalada.

    Ordem pensada para nunca deixar meia versao: confere o zip inteiro,
    instala as bibliotecas novas (se mudaram) e so entao troca os arquivos."""
    with tempfile.TemporaryDirectory(prefix="autopes21_") as temp:
        temp = Path(temp)
        try:
            with zipfile.ZipFile(zip_codigo) as z:
                z.extractall(temp)
        except zipfile.BadZipFile:
            raise ErroAtualizacao("o arquivo baixado nao e um zip valido")

        manifesto = _ler_manifesto(temp / "MANIFESTO.txt")
        versao = (temp / "VERSAO").read_text(encoding="utf-8").strip() if (temp / "VERSAO").is_file() else ""
        if not manifesto or not versao or "painel.py" not in manifesto:
            raise ErroAtualizacao("o pacote veio incompleto (sem MANIFESTO, VERSAO ou painel.py)")
        faltando = [n for n in manifesto if not (temp / n).is_file()]
        if faltando:
            raise ErroAtualizacao(f"o pacote veio sem {len(faltando)} arquivo(s), ex.: {faltando[0]}")

        if _md5(temp / REQUISITOS) != _md5(PASTA_PROJETO / REQUISITOS):
            falar("Instalando as bibliotecas da versao nova...")
            resultado = subprocess.run(
                [python_do_pacote(), "-m", "pip", "install", "--disable-pip-version-check",
                 "--no-warn-script-location", "-r", str(temp / REQUISITOS)],
                capture_output=True, text=True, errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if resultado.returncode != 0:
                ultimas = (resultado.stderr or resultado.stdout).strip().splitlines()[-3:]
                raise ErroAtualizacao("o pip falhou; nada foi trocado. " + " | ".join(ultimas))

        antigos = set(_ler_manifesto(ARQUIVO_MANIFESTO))
        trocados = 0
        for nome in manifesto + ["MANIFESTO.txt", "VERSAO"]:
            if not _seguro(nome):
                falar(f"  (pulei {nome}: nao e arquivo de codigo)")
                continue
            destino = PASTA_PROJETO / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            novo = destino.with_name(destino.name + ".novo")
            shutil.copyfile(temp / nome, novo)
            novo.replace(destino)
            trocados += 1

        # Arquivo de codigo que saiu da versao nova: apaga. So os que estavam
        # no manifesto antigo - nada que o usuario criou.
        for nome in sorted(antigos - set(manifesto)):
            caminho = PASTA_PROJETO / nome
            if _seguro(nome) and caminho.is_file():
                caminho.unlink()
                falar(f"  removido: {nome}")

    falar(f"Versao {versao} instalada ({trocados} arquivo(s)).")
    return versao


def aplicar(info: dict | None = None, falar=print) -> str:
    """Baixa o codigo.zip da ultima release e aplica. Devolve a versao."""
    if e_desenvolvimento():
        raise ErroAtualizacao("esta e a pasta de desenvolvimento: atualize com git pull")
    info = info or procurar()
    if not info.get("pode_aplicar"):
        raise ErroAtualizacao(info.get("motivo") or "nao ha versao nova")
    falar(f"Baixando a versao {info['nova']}...")
    with tempfile.TemporaryDirectory(prefix="autopes21_") as temp:
        destino = Path(temp) / NOME_PACOTE_CODIGO
        try:
            with _pedir(info["url"], aceitar="application/octet-stream") as r, open(destino, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as erro:
            raise ErroAtualizacao(f"nao consegui baixar a versao nova: {erro}")
        return aplicar_zip(destino, falar)


def main() -> int:
    if sys.stdout is not None:
        sys.stdout.reconfigure(errors="replace")
    info = procurar()
    print(f"Versao instalada: {info['local']}")
    if not info["nova"]:
        motivo = f" ({info['motivo']})" if info["motivo"] else ""
        print(f"Nada para atualizar{motivo}.")
        return 0
    print(f"Versao nova: {info['nova']}")
    if info["notas"]:
        print(info["notas"])
    if "--aplicar" not in sys.argv:
        print("\nPara instalar: python atualizar.py --aplicar (ou pelo painel)")
        return 0
    try:
        aplicar(info)
    except ErroAtualizacao as erro:
        print(f"ERRO: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
