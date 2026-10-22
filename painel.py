"""
painel.py  --  Auto_PES21

O painel no navegador, para usar o projeto sem abrir codigo: monta a fila de
jogos pelas rodadas do site, ajusta o caminhos.ini e roda os tres passos
(rodar_jogos, extrair_eventos, enviar_resultados) mostrando a saida na tela.

NAO substitui os scripts: so chama eles, do mesmo jeito que o terminal. Tudo
continua funcionando sem o painel.

So a biblioteca padrao do Python, para nao precisar instalar nada a mais. A
pagina (HTML, CSS e JS) fica na pasta painel/.

Uso:
  python painel.py                  -> abre http://127.0.0.1:8021 no navegador
  python painel.py --sem-navegador  -> so sobe o servidor
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

PORTA = 8021              # se estiver ocupada, tenta as proximas
PORTAS_A_TENTAR = 10

# O site fica numa hospedagem gratuita que dorme: a primeira chamada pode
# levar quase um minuto para acordar o servidor.
SEGUNDOS_TIMEOUT_SITE = 90

ARQUIVO_FILA = "fila_jogos.json"            # a fila montada no painel
ARQUIVO_CONTROLE = "resultados_enviados.json"   # do enviar_resultados.py
EXTENSOES_VIDEO = (".mp4", ".mkv", ".mov", ".avi")

# ==========================================================================

import codecs
import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import times

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_PAGINA = PASTA_PROJETO / "painel"
ARQUIVO_INI = PASTA_PROJETO / "caminhos.ini"
EXEMPLO_INI = PASTA_PROJETO / "caminhos.exemplo.ini"

# Os campos do caminhos.ini que a pagina mostra, na ordem da tela.
CAMPOS_INI = [
    ("caminhos", "pasta_pes"),
    ("caminhos", "pasta_sider"),
    ("caminhos", "pasta_videos"),
    ("site", "url"),
    ("site", "token"),
    ("site", "base_jogadores"),
]

TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".png": "image/png",
         ".svg": "image/svg+xml"}


# --------------------------------------------------------------------------
# caminhos.ini
# --------------------------------------------------------------------------
# Leio o .ini aqui mesmo em vez de importar caminhos.py: aquele modulo para o
# programa (sys.exit) se uma pasta estiver vazia - justo o que o painel
# precisa deixar voce consertar.

def ler_ini() -> configparser.ConfigParser:
    if not ARQUIVO_INI.exists():
        shutil.copyfile(EXEMPLO_INI, ARQUIVO_INI)
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ARQUIVO_INI, encoding="utf-8")
    return ini


def valor_ini(ini, secao: str, chave: str) -> str:
    return ini.get(secao, chave, fallback="").strip().strip('"')


def expandir(caminho: str) -> Path:
    return Path(caminho).expanduser()


def gravar_ini(novos: dict) -> None:
    """Troca so os valores, linha a linha, e mantem os comentarios do arquivo.

    novos: {(secao, chave): valor}. Chave que nao existe entra no fim da
    secao dela; secao que nao existe entra no fim do arquivo.
    """
    with open(ARQUIVO_INI, encoding="utf-8", newline="") as f:
        texto = f.read()
    quebra = "\r\n" if "\r\n" in texto else "\n"     # o Bloco de Notas grava \r\n
    linhas = texto.splitlines()
    secao = None
    ultima_da_secao = {}          # secao -> indice da ultima linha com conteudo
    feitos = set()
    for i, linha in enumerate(linhas):
        m = re.match(r"\s*\[(.+?)\]\s*$", linha)
        if m:
            secao = m.group(1).strip()
            ultima_da_secao[secao] = i
            continue
        if secao and linha.strip():
            ultima_da_secao[secao] = i
        m = re.match(r"\s*([A-Za-z_]+)\s*[=:]", linha)
        if m and not linha.lstrip().startswith(("#", ";")):
            chave = (secao, m.group(1).lower())
            if chave in novos:
                linhas[i] = f"{chave[1]} = {novos[chave]}"
                feitos.add(chave)

    # De baixo para cima, para os indices de cima continuarem valendo.
    faltam = [c for c in novos if c not in feitos]
    for secao in sorted({s for s, _ in faltam if s in ultima_da_secao},
                        key=lambda s: -ultima_da_secao[s]):
        posicao = ultima_da_secao[secao] + 1
        for s, chave in faltam:
            if s == secao:
                linhas.insert(posicao, f"{chave} = {novos[(s, chave)]}")
                posicao += 1
    for secao in dict.fromkeys(s for s, _ in faltam if s not in ultima_da_secao):
        linhas += ["", f"[{secao}]"]
        linhas += [f"{chave} = {novos[(s, chave)]}" for s, chave in faltam if s == secao]

    temporario = ARQUIVO_INI.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8", newline="") as f:
        f.write(quebra.join(linhas) + quebra)
    os.replace(temporario, ARQUIVO_INI)


def conferir_config(ini) -> dict:
    """O que da para conferir sem rodar nada: os arquivos estao onde deviam?"""
    pes = valor_ini(ini, "caminhos", "pasta_pes")
    sider = valor_ini(ini, "caminhos", "pasta_sider")
    videos = valor_ini(ini, "caminhos", "pasta_videos")
    base = valor_ini(ini, "site", "base_jogadores")

    def arquivo(pasta, nome):
        if not pasta:
            return {"ok": False, "texto": "vazio"}
        achou = (expandir(pasta) / nome).is_file()
        return {"ok": achou, "texto": f"achei o {nome}" if achou else f"nao achei o {nome} nesta pasta"}

    def pasta_existe(pasta):
        if not pasta:
            return {"ok": False, "texto": "vazio"}
        achou = expandir(pasta).is_dir()
        return {"ok": achou, "texto": "pasta encontrada" if achou else "essa pasta nao existe"}

    if not base:
        conf_base = {"ok": None, "texto": "vazio: os nomes ficam como o OCR leu"}
    else:
        achou = expandir(base).is_file()
        conf_base = {"ok": achou, "texto": "arquivo encontrado" if achou else "arquivo nao encontrado"}

    return {
        "pasta_pes": arquivo(pes, "PES2021.exe"),
        "pasta_sider": arquivo(sider, "sider.exe"),
        "pasta_videos": pasta_existe(videos),
        "url": {"ok": bool(valor_ini(ini, "site", "url")) or None,
                "texto": "preenchido" if valor_ini(ini, "site", "url") else "vazio: sem rodadas do site e sem envio"},
        "token": {"ok": bool(valor_ini(ini, "site", "token")) or None,
                  "texto": "guardado" if valor_ini(ini, "site", "token") else "vazio: so da para simular o envio"},
        "base_jogadores": conf_base,
    }


def config_para_pagina() -> dict:
    ini = ler_ini()
    valores = {chave: valor_ini(ini, secao, chave) for secao, chave in CAMPOS_INI}
    # O token nunca volta para a pagina: ela so fica sabendo se ele existe.
    valores["token"] = ""
    return {"valores": valores, "conferencia": conferir_config(ini),
            "arquivo": str(ARQUIVO_INI)}


# --------------------------------------------------------------------------
# Site da liga
# --------------------------------------------------------------------------

class ErroDoSite(Exception):
    pass


def pedir_ao_site(caminho: str):
    url = valor_ini(ler_ini(), "site", "url")
    if not url:
        raise ErroDoSite("A url do site esta vazia. Preencha na aba Configuracao.")
    try:
        with urllib.request.urlopen(url.rstrip("/") + caminho,
                                    timeout=SEGUNDOS_TIMEOUT_SITE) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise ErroDoSite(f"O site respondeu com erro {erro.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        motivo = getattr(erro, "reason", erro)
        raise ErroDoSite(f"Nao consegui falar com o site ({motivo}).")


def nomes_na_pasta_de_videos() -> set:
    """Nomes (sem extensao) de video e .json na pasta de videos, sem as subpastas.

    So a raiz: Enviados/ guarda jogos antigos, e o mesmo confronto pode ter
    se repetido em outra competicao.
    """
    pasta = expandir(valor_ini(ler_ini(), "caminhos", "pasta_videos"))
    if not pasta.is_dir():
        return set()
    return {p.stem for p in pasta.iterdir()
            if p.is_file() and p.suffix.lower() in EXTENSOES_VIDEO + (".json",)}


def nome_do_video(casa: str, fora: str) -> str:
    """O nome que o rodar_jogos.renomear_video() da ao video, sem extensao."""
    return f"{casa} vs {fora}"


def rodadas_da_liga(liga_id: str) -> list:
    rodadas = pedir_ao_site(f"/api/liga/{urllib.parse.quote(liga_id)}/rodadas")
    na_pasta = nomes_na_pasta_de_videos()
    resultado = []
    for rodada in rodadas:
        partidas = []
        for p in rodada.get("partidas") or []:
            casa = times.time_do_site(p["timeCasaNome"])
            fora = times.time_do_site(p["timeForaNome"])
            jogada = p.get("status") == 2 or p.get("isWO")
            if not casa or not fora:
                situacao = "sem_time"
            elif jogada:
                situacao = "jogado"
            elif nome_do_video(casa, fora) in na_pasta:
                situacao = "gravado"
            else:
                situacao = "pendente"
            partidas.append({
                "casa_site": p["timeCasaNome"], "fora_site": p["timeForaNome"],
                "casa": casa, "fora": fora, "situacao": situacao,
                "placar": f"{p.get('golsCasa')} x {p.get('golsFora')}" if jogada else None,
                "wo": bool(p.get("isWO")),
            })
        resultado.append({
            "numero": rodada.get("numero"), "titulo": rodada.get("titulo"),
            "data": rodada.get("dataHora"), "partidas": partidas,
        })
    return resultado


# --------------------------------------------------------------------------
# Fila e pasta de videos
# --------------------------------------------------------------------------

def ler_fila() -> list:
    caminho = PASTA_PROJETO / ARQUIVO_FILA
    if not caminho.exists():
        return []
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except ValueError:
        return []


def gravar_fila(fila: list) -> list:
    limpa = []
    for jogo in fila:
        casa, fora = times.nome_oficial(jogo["casa"]), times.nome_oficial(jogo["fora"])
        limpa.append({"casa": casa, "fora": fora,
                      "competicao": (jogo.get("competicao") or None),
                      "rodada": jogo.get("rodada")})
    caminho = PASTA_PROJETO / ARQUIVO_FILA
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(limpa, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporario, caminho)
    return limpa


def fila_para_pagina() -> list:
    na_pasta = nomes_na_pasta_de_videos()
    return [dict(j, gravado=nome_do_video(j["casa"], j["fora"]) in na_pasta)
            for j in ler_fila()]


def situacao_dos_videos() -> dict:
    """Cada jogo da raiz da pasta de videos e em que passo ele esta."""
    pasta = expandir(valor_ini(ler_ini(), "caminhos", "pasta_videos"))
    if not pasta.is_dir():
        return {"pasta": str(pasta), "existe": False, "jogos": []}

    controle_arq = PASTA_PROJETO / ARQUIVO_CONTROLE
    try:
        controle = json.loads(controle_arq.read_text(encoding="utf-8")) if controle_arq.exists() else {}
    except ValueError:
        controle = {}

    jogos = {}
    for p in sorted(pasta.iterdir(), key=lambda p: p.stat().st_mtime):
        if not p.is_file():
            continue
        sufixo = p.suffix.lower()
        if sufixo not in EXTENSOES_VIDEO and sufixo != ".json":
            continue
        jogo = jogos.setdefault(p.stem, {"nome": p.stem, "video": None, "json": None})
        if sufixo in EXTENSOES_VIDEO:
            jogo["video"] = p.name
            continue
        info = {"arquivo": p.name, "status": None, "placar": None, "avisos": [], "envio": None}
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
            c, f = dados.get("casa") or {}, dados.get("fora") or {}
            info["status"] = dados.get("status")
            info["placar"] = f"{c.get('time')} {c.get('gols')} x {f.get('gols')} {f.get('time')}"
            info["avisos"] = dados.get("avisos") or []
        except (OSError, ValueError) as erro:
            info["status"] = "ilegivel"
            info["avisos"] = [f"nao consegui ler o .json: {erro}"]
        anotado = controle.get(p.name)
        if anotado:
            mesmo = anotado.get("hash") == hashlib.sha256(p.read_bytes()).hexdigest()
            info["envio"] = "enviado" if mesmo else "mudou"
            info["enviado_em"] = anotado.get("enviado_em")
        jogo["json"] = info

    return {"pasta": str(pasta), "existe": True, "jogos": list(jogos.values())}


# --------------------------------------------------------------------------
# Tarefa em andamento (um script por vez)
# --------------------------------------------------------------------------

TAREFAS = {
    "rodar":   {"titulo": "Rodar jogos", "script": "rodar_jogos.py"},
    "extrair": {"titulo": "Extrair eventos", "script": "extrair_eventos.py"},
    "enviar":  {"titulo": "Enviar resultados", "script": "enviar_resultados.py"},
}


class Tarefa:
    """O script que esta rodando e o que ele ja escreveu.

    A saida e guardada em linhas, imitando o terminal: uma linha que termina
    em "\\r" (o "esperando... 12s" do rodar_jogos) e reescrita pela seguinte,
    em vez de virar uma cascata de linhas.
    """

    def __init__(self):
        self.trava = threading.Lock()
        self.numero = 0
        self.nome = None
        self.titulo = None
        self.processo = None
        self.linhas = []
        self.provisoria = False
        self.resto = ""
        self.codigo = None
        self.parada = False
        self.inicio = None
        self.fim = None

    def rodando(self) -> bool:
        return self.processo is not None and self.processo.poll() is None

    def iniciar(self, nome: str, argumentos: list) -> None:
        with self.trava:
            if self.rodando():
                raise RuntimeError(f"Ja tem uma tarefa rodando: {self.titulo}.")
            self.numero += 1
            self.nome, self.titulo = nome, TAREFAS[nome]["titulo"]
            self.linhas, self.provisoria, self.resto = [], False, ""
            self.codigo, self.parada = None, False
            self.inicio, self.fim = time.time(), None
            comando = [sys.executable, "-u", TAREFAS[nome]["script"], *argumentos]
            self._anotar(f"[painel] {' '.join(comando[2:])}\n")
            ambiente = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            self.processo = subprocess.Popen(
                comando, cwd=PASTA_PROJETO, env=ambiente,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._ler, args=(self.processo,), daemon=True).start()

    def _ler(self, processo) -> None:
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            pedaco = processo.stdout.read1(4096)
            if not pedaco:
                break
            with self.trava:
                self._anotar(decodificador.decode(pedaco))
        codigo = processo.wait()
        with self.trava:
            self._anotar(decodificador.decode(b"", final=True))
            if self.resto:
                self._anotar("\n")
            self.codigo = codigo
            self.fim = time.time()
            if self.parada:
                self._anotar("[painel] Parado por voce.\n")
                if self.nome == "rodar":
                    self._anotar("[painel] ATENCAO: a gravacao pode ter ficado ligada. Confira na NVIDIA.\n")

    def _anotar(self, texto: str) -> None:
        self.resto += texto
        while True:
            m = re.search(r"\r\n|\n|\r", self.resto)
            if not m:
                return
            # Um "\r" no fim pode ser a metade de um "\r\n" que ainda vai chegar.
            if m.group() == "\r" and m.end() == len(self.resto):
                return
            linha = self.resto[:m.start()].rstrip()
            self.resto = self.resto[m.end():]
            if self.provisoria:
                self.linhas[-1] = linha
            else:
                self.linhas.append(linha)
            self.provisoria = m.group() == "\r"

    def parar(self) -> None:
        with self.trava:
            if not self.rodando():
                return
            self.parada = True
            pid = self.processo.pid
        # /T leva junto o que o script abriu (o ffmpeg do extrair_eventos).
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def estado(self, desde: int) -> dict:
        with self.trava:
            # A ultima linha que o cliente ja tem pode ter sido reescrita
            # ("\r"): mando de novo a partir dela.
            inicio = max(0, min(desde - 1, len(self.linhas)))
            return {
                "numero": self.numero, "nome": self.nome, "titulo": self.titulo,
                "rodando": self.rodando(), "codigo": self.codigo, "parada": self.parada,
                "inicio": self.inicio, "fim": self.fim,
                "desde": inicio, "linhas": self.linhas[inicio:],
            }


tarefa = Tarefa()


def iniciar_tarefa(pedido: dict) -> None:
    nome = pedido.get("tarefa")
    if nome not in TAREFAS:
        raise ValueError("Tarefa desconhecida.")
    argumentos = []
    if nome == "rodar":
        fila = ler_fila()
        if not fila:
            raise ValueError("A fila de jogos esta vazia.")
        argumentos = ["--auto", "--fila", ARQUIVO_FILA]
    elif nome == "enviar" and pedido.get("simular"):
        argumentos = ["--simular"]
    tarefa.iniciar(nome, argumentos)


def caminho_da_foto(pedido: str):
    """So deixa abrir os .png das pastas de diagnostico do projeto."""
    caminho = (PASTA_PROJETO / pedido).resolve()
    try:
        relativo = caminho.relative_to(PASTA_PROJETO)
    except ValueError:
        return None
    if caminho.suffix.lower() != ".png" or not relativo.parts[0].startswith("diagnostico"):
        return None
    return caminho if caminho.is_file() else None


# --------------------------------------------------------------------------
# Servidor
# --------------------------------------------------------------------------

class Pedido(BaseHTTPRequestHandler):
    server_version = "AutoPES21"

    def log_message(self, formato, *args):
        pass   # o terminal fica limpo; o que importa aparece na pagina

    # So responde a quem abriu pelo proprio PC. O painel roda scripts que
    # apertam teclas: uma pagina qualquer da internet nao pode chamar isso.
    def _origem_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados, codigo: int = 200) -> None:
        self._responder(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    def _erro(self, mensagem: str, codigo: int = 400) -> None:
        self._json({"erro": mensagem}, codigo)

    def _corpo(self):
        tamanho = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(tamanho).decode("utf-8") or "{}")

    def do_GET(self):
        if not self._origem_ok():
            return self._erro("Acesso so pelo proprio PC.", 403)
        url = urllib.parse.urlparse(self.path)
        consulta = urllib.parse.parse_qs(url.query)
        rota = url.path

        try:
            if rota == "/api/config":
                return self._json(config_para_pagina())
            if rota == "/api/times":
                return self._json(times.TIMES)
            if rota == "/api/competicoes":
                ligas = pedir_ao_site("/api/liga/ativas")
                return self._json([{"id": l["ligaId"], "nome": l["nome"]} for l in ligas])
            if rota == "/api/rodadas":
                return self._json(rodadas_da_liga(consulta.get("liga", [""])[0]))
            if rota == "/api/fila":
                return self._json(fila_para_pagina())
            if rota == "/api/videos":
                return self._json(situacao_dos_videos())
            if rota == "/api/tarefa":
                return self._json(tarefa.estado(int(consulta.get("desde", ["0"])[0])))
            if rota == "/foto":
                caminho = caminho_da_foto(consulta.get("p", [""])[0])
                if not caminho:
                    return self._erro("Foto nao encontrada.", 404)
                return self._responder(200, caminho.read_bytes(), "image/png")
        except ErroDoSite as erro:
            return self._erro(str(erro), 502)

        # Arquivos da pagina.
        nome = "index.html" if rota == "/" else rota.lstrip("/")
        arquivo = (PASTA_PAGINA / nome).resolve()
        if arquivo.parent != PASTA_PAGINA or not arquivo.is_file():
            return self._erro("Nao encontrado.", 404)
        self._responder(200, arquivo.read_bytes(),
                        TIPOS.get(arquivo.suffix, "application/octet-stream"))

    def do_POST(self):
        # Exigir JSON tambem barra formularios de outros sites: o navegador
        # nao manda Content-Type application/json entre sites sem perguntar.
        if not self._origem_ok() or \
                not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._erro("Acesso so pelo proprio PC.", 403)
        rota = urllib.parse.urlparse(self.path).path
        try:
            pedido = self._corpo()
            if rota == "/api/config":
                novos = {}
                for secao, chave in CAMPOS_INI:
                    if chave not in pedido:
                        continue
                    valor = str(pedido[chave]).strip()
                    if "\n" in valor or "\r" in valor:
                        return self._erro(f"'{chave}' nao pode ter quebra de linha.")
                    # Token vazio = manter o que ja esta guardado.
                    if chave == "token" and not valor and not pedido.get("apagar_token"):
                        continue
                    novos[(secao, chave)] = valor
                gravar_ini(novos)
                return self._json(config_para_pagina())
            if rota == "/api/fila":
                gravar_fila(pedido.get("fila") or [])
                return self._json(fila_para_pagina())
            if rota == "/api/tarefa":
                iniciar_tarefa(pedido)
                return self._json(tarefa.estado(0))
            if rota == "/api/tarefa/parar":
                tarefa.parar()
                return self._json({"ok": True})
        except (ValueError, KeyError, RuntimeError) as erro:
            return self._erro(str(erro))
        return self._erro("Nao encontrado.", 404)


def subir_servidor() -> ThreadingHTTPServer:
    for porta in range(PORTA, PORTA + PORTAS_A_TENTAR):
        try:
            return ThreadingHTTPServer(("127.0.0.1", porta), Pedido)
        except OSError:
            continue
    print(f"ERRO: nenhuma porta livre entre {PORTA} e {PORTA + PORTAS_A_TENTAR - 1}.")
    sys.exit(1)


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    os.chdir(PASTA_PROJETO)      # os scripts procuram templates/ a partir daqui
    servidor = subir_servidor()
    endereco = f"http://127.0.0.1:{servidor.server_address[1]}"
    print("=" * 66)
    print("  AUTO_PES21  --  painel")
    print("=" * 66)
    print(f"\n  Aberto em {endereco}")
    print("  Deixe esta janela aberta enquanto usa o painel (Ctrl+C fecha).\n")
    if "--sem-navegador" not in sys.argv:
        webbrowser.open(endereco)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("Fechando o painel.")
        if tarefa.rodando():
            print("ATENCAO: a tarefa que estava rodando foi interrompida junto.")
            tarefa.parar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
