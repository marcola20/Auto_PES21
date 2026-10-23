"""
upar_videos.py  --  Auto_PES21 / youtube

Sobe os jogos gravados pelo Auto_PES21 para o YouTube, cada um programado como
ESTREIA (ou como PRIVADO, sem data). Voce escolhe a ordem dos jogos e de
quantos em quantos minutos eles estreiam.

PREPARO (uma vez):
  1. python login.py   -> entra na conta do canal no Chrome do robo.
  2. Escreva as descricoes em descricao_liga.txt e descricao_copa.txt.
  3. Confira se as playlists da edicao ja existem no canal
     (ex.: "Brasileirão CBFV | 8ª Edição").

USO:
  python upar_videos.py              -> pergunta tudo e sobe
  python upar_videos.py --simular    -> so mostra o plano, nao abre o navegador
  python upar_videos.py --pausar     -> para antes de cada "Programar" para voce conferir
  python upar_videos.py --limite 1   -> sobe so os N primeiros (bom para teste)

  O painel (python painel.py, na pasta de cima) usa, sem perguntas:
  python upar_videos.py --listar               -> competicoes e videos em JSON
  python upar_videos.py --plano plano.json     -> respostas num .json

O QUE ELE FAZ:
  - Lista os videos soltos em config.PASTA_VIDEOS, em ordem de gravacao, e
    deixa voce reordenar, tirar algum da lista ou juntar jogos no mesmo
    horario com + (ex.: 1+2,3 -> 1 e 2 estreiam juntos, 3 no horario seguinte).
  - Titulo: "<nome do arquivo> | 3ª Rodada | Brasileirão CBFV"
            (Semi -> "Semifinal", Final -> "Final").
  - Descricao do .txt, playlist da edicao, "nao e para criancas", estreia com
    contagem de 1 minuto e tema Esportes.
  - Cada video programado vai para a subpasta Enviados e para historico.csv.

REGRA DE OURO: na duvida, PARAR. Se qualquer passo nao conferir, o script
salva print + HTML em diagnostico/ e para tudo. O video que falhou pode ter
ficado como RASCUNHO no Studio - apague la antes de rodar de novo.
"""

import argparse
import csv
import json
import re
import struct
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import config
import importar_rpa

# ==========================================================================
# PERGUNTAS
# ==========================================================================


def perguntar_competicao() -> str:
    chaves = list(config.COMPETICOES)
    menu = "   ".join(f"{i} - {config.COMPETICOES[c]['nome']}" for i, c in enumerate(chaves, 1))
    while True:
        print(menu)
        r = input(f"Qual competicao? [1-{len(chaves)}]: ").strip()
        if r.isdigit() and 1 <= int(r) <= len(chaves):
            return chaves[int(r) - 1]
        print(f"  Responda um numero de 1 a {len(chaves)}.\n")


def perguntar_rodada(competicao: str) -> str:
    validas = config.COMPETICOES[competicao]["rodadas"]
    exibicao = ", ".join(rotulo_rodada(v) for v in validas)
    while True:
        r = normalizar_rodada(input(f"Qual rodada? ({exibicao}): "))
        if r in validas:
            return r
        print(f"  Rodada invalida para {config.COMPETICOES[competicao]['nome']}. Opcoes: {exibicao}")


def normalizar_rodada(r: str) -> str:
    """'3ª', ' 03 ', 'Semifinal' -> '3', '3', 'semi': o formato de config.COMPETICOES."""
    r = str(r).strip().lower().rstrip("ªaº°").strip()
    if r in ("semifinal", "semi-final"):
        r = "semi"
    if r in ("quartas de final", "quartas-de-final", "quarta"):
        r = "quartas"
    if r.isdigit():
        r = str(int(r))
    return r


def rotulo_rodada(rodada: str) -> str:
    especiais = {"quartas": "Quartas de Final", "semi": "Semifinal", "final": "Final"}
    return especiais.get(rodada, f"{rodada}ª Rodada")


def perguntar_data() -> datetime:
    hoje = datetime.now().date()
    while True:
        r = input(f"Data da estreia? (dd, dd/mm ou dd/mm/aaaa, Enter = hoje {hoje:%d/%m}): ").strip()
        if not r:
            return datetime.combine(hoje, datetime.min.time())
        partes = r.replace("-", "/").replace(".", "/").split("/")
        try:
            if len(partes) == 1:
                d = datetime(hoje.year, hoje.month, int(partes[0]))
            elif len(partes) == 2:
                d = datetime(hoje.year, int(partes[1]), int(partes[0]))
            elif len(partes) == 3:
                ano = int(partes[2])
                d = datetime(ano + 2000 if ano < 100 else ano, int(partes[1]), int(partes[0]))
            else:
                raise ValueError
        except ValueError:
            print("  Data invalida. Exemplo: 20/09 ou 20/09/2026")
            continue
        if d.date() < hoje:
            print("  Essa data ja passou.")
            continue
        return d


def perguntar_hora() -> tuple[int, int]:
    while True:
        r = input("Horario do primeiro jogo? (ex.: 18:00): ").strip().lower().replace("h", ":")
        partes = [x for x in r.split(":") if x != ""]
        try:
            hora = int(partes[0])
            minuto = int(partes[1]) if len(partes) > 1 else 0
            if len(partes) > 2 or not (0 <= hora < 24 and 0 <= minuto < 60):
                raise ValueError
            return hora, minuto
        except (ValueError, IndexError):
            print("  Horario invalido. Exemplo: 18:00")


def perguntar_ordem(videos: list[Path]) -> list[list[Path]]:
    """Mostra os videos na ordem de gravacao e deixa voce reordenar, tirar algum
    ou juntar jogos no mesmo horario com + (ex.: 1+2,3 -> 1 e 2 juntos, depois 3).

    Devolve os horarios em ordem; cada horario e a lista de jogos que estreiam nele.
    """
    print("\nVideos na pasta, em ordem de gravacao:")
    for i, v in enumerate(videos, 1):
        print(f"  {i:>2}. {formatar_duracao(duracao_segundos(v)):>7}  {v.stem}"
              f"   ({v.stat().st_size / 1024**3:.1f} GB, "
              f"gravado {datetime.fromtimestamp(v.stat().st_mtime):%d/%m %H:%M})")
    while True:
        r = input("Ordem dos jogos? (ex.: 3,1,2 - use + para o mesmo horario, ex.: 1+2,3 "
                  "- Enter mantem a ordem acima): ").strip()
        if not r:
            return [[v] for v in videos]
        r = re.sub(r"\s*\+\s*", "+", r)
        grupos = [[x for x in g.split("+") if x] for g in re.split(r"[\s,;]+", r) if g.strip("+")]
        numeros = [x for g in grupos for x in g]
        if not all(x.isdigit() for x in numeros):
            print("  Use so numeros separados por virgula (e + para juntar). Exemplo: 1+2,3")
            continue
        escolhidos = [int(x) for x in numeros]
        if any(not 1 <= n <= len(videos) for n in escolhidos):
            print(f"  Use numeros de 1 a {len(videos)}.")
            continue
        if len(set(escolhidos)) != len(escolhidos):
            print("  Voce repetiu algum numero.")
            continue
        fora = [v.stem for i, v in enumerate(videos, 1) if i not in escolhidos]
        if fora:
            print(f"  Fica(m) de fora: {', '.join(fora)}")
            if not confirmar("  Tudo bem"):
                continue
        return [[videos[int(n) - 1] for n in g] for g in grupos]


def perguntar_intervalo() -> int:
    padrao = config.MINUTOS_ENTRE_JOGOS
    while True:
        r = input(f"Intervalo entre as estreias, em minutos? (Enter = {padrao}): ").strip()
        if not r:
            return padrao
        if r.isdigit() and 1 <= int(r) <= 24 * 60:
            return int(r)
        print("  Responda um numero de minutos. Exemplo: 30")


def perguntar_modo() -> str:
    """estreia = programado com contagem regressiva; privado = so sobe, sem data."""
    while True:
        r = input("Subir como Estreia ou Privado? [E/P]: ").strip().lower()
        if r in ("e", "estreia"):
            return "estreia"
        if r in ("p", "privado"):
            return "privado"
        print("  Responda E (Estreia) ou P (Privado).")


def perguntar_inicio() -> datetime:
    """Data + horario da primeira estreia. Se ja passou, pergunta os dois de novo."""
    while True:
        data = perguntar_data()
        hora, minuto = perguntar_hora()
        inicio = data.replace(hour=hora, minute=minuto)
        minimo = datetime.now() + timedelta(minutes=config.MINUTOS_MARGEM_MINIMA)
        if inicio >= minimo:
            return inicio
        agora = datetime.now()
        if inicio <= agora:
            print(f"  {inicio:%d/%m %H:%M} ja passou (agora sao {agora:%d/%m %H:%M}).")
        else:
            print(f"  {inicio:%d/%m %H:%M} esta perto demais: a primeira estreia precisa ser "
                  f"a partir de {minimo:%d/%m %H:%M}.")
        print("  Informe a data e o horario de novo.\n")


def confirmar(pergunta: str) -> bool:
    return input(f"{pergunta} [s/N]: ").strip().lower() in ("s", "sim")


# ==========================================================================
# VIDEOS E PLANO
# ==========================================================================


def duracao_segundos(arquivo: Path) -> float | None:
    """Duracao lida no cabecalho do .mp4/.mov (o mesmo dado de Propriedades > Detalhes).

    Nao usa ffmpeg (nao esta instalado) nem abre o Windows para cada arquivo:
    le so os primeiros bytes de cada caixa do arquivo ate achar o 'mvhd'.
    """
    try:
        with arquivo.open("rb") as f:
            return _procurar_mvhd(f, 0, arquivo.stat().st_size)
    except (OSError, struct.error, IndexError):
        return None


def _procurar_mvhd(f, inicio: int, fim: int) -> float | None:
    pos = inicio
    while pos < fim - 8:
        f.seek(pos)
        cabecalho = f.read(8)
        if len(cabecalho) < 8:
            return None
        tamanho, tipo = struct.unpack(">I4s", cabecalho)
        corpo = pos + 8
        if tamanho == 1:                      # caixa grande: o tamanho vem em 8 bytes
            tamanho = struct.unpack(">Q", f.read(8))[0]
            corpo += 8
        elif tamanho == 0:                    # vai ate o fim do arquivo
            tamanho = fim - pos
        if tamanho < 8:
            return None
        if tipo == b"moov":
            return _procurar_mvhd(f, corpo, pos + tamanho)
        if tipo == b"mvhd":
            versao = f.read(1)[0]
            f.read(3)                         # flags
            if versao == 1:
                f.read(16)                    # datas de criacao e modificacao
                escala, duracao = struct.unpack(">IQ", f.read(12))
            else:
                f.read(8)
                escala, duracao = struct.unpack(">II", f.read(8))
            return duracao / escala if escala else None
        pos += tamanho
    return None


def formatar_duracao(segundos: float | None) -> str:
    if not segundos:
        return "  --  "
    total = int(segundos)
    if total >= 3600:
        return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"
    return f"{total // 60}:{total % 60:02d}"


def ja_enviados() -> set[tuple[str, int]]:
    if not config.HISTORICO.is_file():
        return set()
    with config.HISTORICO.open(encoding="utf-8", newline="") as f:
        return {(linha["arquivo"], int(linha["tamanho"])) for linha in csv.DictReader(f, delimiter=";")}


def listar_videos(falar: bool = True) -> list[Path]:
    enviados = ja_enviados()
    videos = []
    for arq in config.PASTA_VIDEOS.iterdir():
        if not arq.is_file() or arq.suffix.lower() not in config.EXTENSOES_VIDEO:
            continue
        if (arq.name, arq.stat().st_size) in enviados:
            if falar:
                print(f"  (pulando {arq.name}: ja consta no historico.csv)")
            continue
        videos.append(arq)
    return sorted(videos, key=lambda v: v.stat().st_mtime)


def ler_descricao(competicao: str) -> str:
    arq = config.COMPETICOES[competicao]["descricao"]
    if not arq.is_file():
        sys.exit(f"ERRO: nao achei {arq}")
    texto = arq.read_text(encoding="utf-8-sig").strip()
    if not texto or "APAGUE ESTE TEXTO" in texto:
        sys.exit(f"ERRO: escreva a descricao em {arq.name} antes de rodar.")
    if "<" in texto or ">" in texto:
        sys.exit(f"ERRO: o YouTube nao aceita < ou > na descricao ({arq.name}).")
    if len(texto) > 5000:
        sys.exit(f"ERRO: {arq.name} passa de 5000 caracteres ({len(texto)}).")
    return texto


def achar_miniatura(competicao: str) -> Path:
    arq = config.COMPETICOES[competicao]["miniatura"]
    if not arq.is_file():
        sys.exit(f"ERRO: nao achei a capa {arq.name} em {arq.parent}.\n"
                 f"       Coloque o arquivo la ou mude o caminho em config.py.")
    return arq


def montar_plano(horarios, competicao, rodada, inicio, intervalo=None):
    """horarios: lista de grupos de videos; os do mesmo grupo estreiam juntos.
    inicio=None (modo privado): os videos sobem sem horario."""
    nome = config.COMPETICOES[competicao]["nome"]
    intervalo = intervalo or config.MINUTOS_ENTRE_JOGOS
    plano = []
    for i, grupo in enumerate(horarios):
        estreia = None if inicio is None else inicio + timedelta(minutes=i * intervalo)
        for video in grupo:
            titulo = f"{video.stem} | {rotulo_rodada(rodada)} | {nome}"
            plano.append({"video": video, "titulo": titulo, "estreia": estreia})
    return plano


def validar_plano(plano) -> list[str]:
    problemas = []
    for item in plano:
        t = item["titulo"]
        if len(t) > 100:
            problemas.append(f"titulo com {len(t)} caracteres (maximo 100): {t}")
        if "<" in t or ">" in t:
            problemas.append(f"titulo com < ou >: {t}")
    margem = datetime.now() + timedelta(minutes=config.MINUTOS_MARGEM_MINIMA)
    if plano and plano[0]["estreia"] is not None and plano[0]["estreia"] < margem:
        problemas.append(f"a primeira estreia ({plano[0]['estreia']:%d/%m %H:%M}) "
                         f"precisa ser pelo menos {config.MINUTOS_MARGEM_MINIMA} min no futuro")
    return problemas


def avisos_de_duracao(plano) -> list[str]:
    """Avisa se um jogo ainda estiver rolando quando o proximo horario estrear.
    Jogos no mesmo horario (juntados com +) nao contam como sobreposicao."""
    avisos = []
    horarios = sorted({item["estreia"] for item in plano if item["estreia"] is not None})
    for atual in plano:
        seguinte = next((h for h in horarios if atual["estreia"] is not None and h > atual["estreia"]), None)
        if seguinte is None:
            continue
        duracao = duracao_segundos(atual["video"])
        if duracao is None:
            continue
        sobra = (seguinte - atual["estreia"]).total_seconds() - duracao
        if sobra < 0:
            avisos.append(f"{atual['video'].stem} ({formatar_duracao(duracao)}) ainda estara no ar "
                          f"quando o proximo estrear as {seguinte:%H:%M}")
    return avisos


def mostrar_plano(plano, playlist, miniatura: Path) -> None:
    print()
    print(f"Playlist: {playlist if playlist else '(nenhuma - competicao sem playlist)'}")
    falta = "" if miniatura.is_file() else "   <-- ESTE ARQUIVO NAO EXISTE"
    print(f"Miniatura: {miniatura.name}{falta}")
    if plano and plano[0]["estreia"] is None:
        print("Videos PRIVADOS (sem data), nao e conteudo para criancas.")
    else:
        print(f"Estreia com contagem de {config.CONTAGEM_REGRESSIVA}, tema {config.TEMA_ESTREIA}, "
              f"nao e conteudo para criancas.")
    print()
    for i, item in enumerate(plano, 1):
        tamanho_gb = item["video"].stat().st_size / 1024**3
        quando = f"{item['estreia']:%d/%m %H:%M}" if item["estreia"] else "privado     "
        duracao = formatar_duracao(duracao_segundos(item["video"]))
        print(f"  {i:>2}. {quando}  {item['titulo']}   ({duracao}, {tamanho_gb:.1f} GB)")
    avisos = avisos_de_duracao(plano)
    if avisos:
        for aviso in avisos:
            print(f"  AVISO: {aviso}")
        print()


# ==========================================================================
# DEPOIS DO ENVIO
# ==========================================================================


def registrar(item) -> None:
    novo = not config.HISTORICO.is_file()
    with config.HISTORICO.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if novo:
            w.writerow(["enviado_em", "arquivo", "tamanho", "titulo", "estreia"])
        estreia = f"{item['estreia']:%Y-%m-%d %H:%M}" if item["estreia"] else "privado"
        w.writerow([f"{datetime.now():%Y-%m-%d %H:%M}", item["video"].name,
                    item["video"].stat().st_size, item["titulo"], estreia])


def mover_para_enviados(video: Path) -> None:
    destino_pasta = config.PASTA_VIDEOS / config.SUBPASTA_ENVIADOS
    destino_pasta.mkdir(exist_ok=True)
    destino = destino_pasta / video.name
    n = 2
    while destino.exists():
        destino = destino_pasta / f"{video.stem} ({n}){video.suffix}"
        n += 1
    # O Chrome pode demorar um pouco para soltar o arquivo depois do upload.
    for _ in range(6):
        try:
            shutil.move(str(video), str(destino))
            return
        except PermissionError:
            time.sleep(10)
    print(f"      AVISO: nao consegui mover {video.name} para {config.SUBPASTA_ENVIADOS}. "
          f"Ele ja esta no historico.csv, entao nao sobe de novo.")


# ==========================================================================
# SEM PERGUNTAS (o painel do Auto_PES21)
# ==========================================================================
# O painel nao tem como responder input(): ele pede a lista com --listar,
# monta a tela e devolve as respostas num .json com --plano.


def situacao_do_login() -> str:
    """'logado', 'sem_login' ou 'desconhecido', sem abrir o Chrome.

    Olha se o perfil do robo tem os cookies de sessao do YouTube (LOGIN_INFO,
    __Secure-3PSID) ainda validos. So os NOMES e a validade: o valor e
    criptografado e nem e lido. Nao garante que o canal e o certo nem que o
    Google nao derrubou a sessao, mas separa o perfil novo, nunca logado, do
    que ja entrou - que e o que o painel precisa para nao pedir login a toa.
    """
    cookies = config.PERFIL_CHROME / "Default" / "Network" / "Cookies"
    if not cookies.is_file():
        return "sem_login"
    consulta = ("select expires_utc, has_expires from cookies "
                "where host_key like '%youtube.com' and name in ('LOGIN_INFO', '__Secure-3PSID')")
    # Le uma copia: com o Chrome do robo aberto, o arquivo pode estar travado.
    copia = Path(tempfile.gettempdir()) / "auto_pes21_cookies.db"
    try:
        shutil.copyfile(cookies, copia)
        with closing(sqlite3.connect(f"file:{copia.as_posix()}?mode=ro", uri=True)) as banco:
            linhas = banco.execute(consulta).fetchall()
    except (OSError, sqlite3.Error):
        return "desconhecido"
    finally:
        copia.unlink(missing_ok=True)
    # expires_utc conta microssegundos desde 1601 (o relogio do Windows).
    agora = (time.time() + 11_644_473_600) * 1_000_000
    validos = [1 for expira, tem_validade in linhas if not tem_validade or expira > agora]
    return "logado" if validos else "sem_login"


def listar_em_json() -> int:
    """--listar: competicoes e videos que podem subir, em JSON no stdout."""
    competicoes = [{
        "chave": chave,
        "nome": c["nome"],
        "playlist": c["playlist"],
        "rodadas": [{"valor": r, "rotulo": rotulo_rodada(r)} for r in c["rodadas"]],
    } for chave, c in config.COMPETICOES.items()]
    videos = []
    if config.PASTA_VIDEOS.is_dir():
        for v in listar_videos(falar=False):
            videos.append({
                "arquivo": v.name,
                "nome": v.stem,
                "duracao": formatar_duracao(duracao_segundos(v)).strip(),
                "tamanho_gb": round(v.stat().st_size / 1024**3, 1),
                "gravado_em": f"{datetime.fromtimestamp(v.stat().st_mtime):%d/%m %H:%M}",
            })
    print(json.dumps({
        "pasta": str(config.PASTA_VIDEOS),
        "pasta_existe": config.PASTA_VIDEOS.is_dir(),
        "competicoes": competicoes,
        "videos": videos,
        "intervalo_padrao": config.MINUTOS_ENTRE_JOGOS,
        "margem_minutos": config.MINUTOS_MARGEM_MINIMA,
        "edicao": config.EDICAO,
        "temporada": config.TEMPORADA,
        "login": situacao_do_login(),
        "rpa_antigo": importar_rpa.situacao(),
    }, ensure_ascii=False))
    return 0


def ler_plano(caminho: str, videos: list[Path]) -> tuple:
    """--plano: as respostas que o terminal perguntaria, num .json.

    {"competicao": "serieA", "rodada": "5", "modo": "estreia",
     "inicio": "2026-10-23 18:00", "intervalo": 20,
     "horarios": [["A vs B.mp4", "C vs D.mp4"], ["E vs F.mp4"]]}

    Os videos vao pelo NOME, e nao pelo numero da lista: entre o painel
    montar a tela e o envio, um video novo na pasta mudaria a numeracao.
    Devolve (competicao, rodada, horarios, inicio, intervalo); ValueError
    com a mensagem para mostrar se algo nao conferir.
    """
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    competicao = dados.get("competicao")
    if competicao not in config.COMPETICOES:
        raise ValueError(f"competicao desconhecida: {competicao}")
    rodada = normalizar_rodada(dados.get("rodada", ""))
    if rodada not in config.COMPETICOES[competicao]["rodadas"]:
        raise ValueError(f"rodada invalida para {config.COMPETICOES[competicao]['nome']}: "
                         f"{dados.get('rodada')}")

    por_nome = {v.name: v for v in videos}
    horarios, vistos = [], set()
    for grupo in dados.get("horarios") or []:
        if not grupo:
            continue
        for nome in grupo:
            if nome not in por_nome:
                raise ValueError(f"o video '{nome}' nao esta mais na pasta (ou ja subiu)")
            if nome in vistos:
                raise ValueError(f"o video '{nome}' aparece duas vezes")
            vistos.add(nome)
        horarios.append([por_nome[n] for n in grupo])
    if not horarios:
        raise ValueError("nenhum video escolhido")

    if dados.get("modo") == "privado":
        return competicao, rodada, horarios, None, None
    if dados.get("modo") != "estreia":
        raise ValueError(f"modo deve ser 'estreia' ou 'privado', veio {dados.get('modo')!r}")
    try:
        inicio = datetime.strptime(str(dados.get("inicio")), "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(f"data/horario invalido: {dados.get('inicio')!r}")
    intervalo = int(dados.get("intervalo") or config.MINUTOS_ENTRE_JOGOS)
    if not 1 <= intervalo <= 24 * 60:
        raise ValueError(f"intervalo invalido: {intervalo} minutos")
    return competicao, rodada, horarios, inicio, intervalo


# ==========================================================================
# PRINCIPAL
# ==========================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="Sobe os jogos do PES como estreia no YouTube.")
    parser.add_argument("--simular", action="store_true", help="so mostra o plano")
    parser.add_argument("--pausar", action="store_true", help="para antes de cada Programar")
    parser.add_argument("--limite", type=int, default=0, help="sobe so os N primeiros videos")
    parser.add_argument("--listar", action="store_true",
                        help="so lista competicoes e videos em JSON (para o painel)")
    parser.add_argument("--plano", metavar="ARQUIVO.json",
                        help="respostas num .json em vez de perguntar (para o painel); "
                             "ja vale como confirmado")
    args = parser.parse_args()

    if args.listar:
        return listar_em_json()

    if not config.PASTA_VIDEOS.is_dir():
        print(f"ERRO: nao achei a pasta {config.PASTA_VIDEOS}")
        return 1
    videos = listar_videos()
    if args.limite > 0:
        videos = videos[:args.limite]
    if not videos:
        print(f"Nenhum video para subir em {config.PASTA_VIDEOS}")
        return 0
    print(f"{len(videos)} video(s) encontrado(s).\n")

    if args.plano:
        try:
            competicao, rodada, horarios, inicio, intervalo = ler_plano(args.plano, videos)
        except (OSError, ValueError) as erro:
            print(f"ERRO no plano: {erro}")
            return 1
    else:
        competicao = perguntar_competicao()
        rodada = perguntar_rodada(competicao)
        horarios = perguntar_ordem(videos)
        # No modo privado nao ha o que agendar, entao nem pergunta data e horario.
        if perguntar_modo() == "estreia":
            inicio = perguntar_inicio()
            # Com um horario so (todos juntos), nao ha intervalo a perguntar.
            intervalo = perguntar_intervalo() if len(horarios) > 1 else None
        else:
            inicio, intervalo = None, None

    playlist = config.nome_playlist(competicao)
    plano = montar_plano(horarios, competicao, rodada, inicio, intervalo)
    mostrar_plano(plano, playlist, config.COMPETICOES[competicao]["miniatura"])

    problemas = validar_plano(plano)
    if problemas:
        print("NAO DA PARA SEGUIR:")
        for prob in problemas:
            print(f"  - {prob}")
        return 1
    if args.simular:
        print("(--simular: nada foi enviado)")
        return 0
    descricao = ler_descricao(competicao)
    miniatura = achar_miniatura(competicao)
    # Pelo painel, a confirmacao ja foi feita na tela (aqui nao ha teclado).
    if not args.plano and not confirmar("Confere? Posso subir"):
        print("Cancelado.")
        return 0

    import studio  # so aqui: --simular nao precisa do Playwright

    feitos = 0
    with studio.Studio() as s:
        item = None
        try:
            s.verificar_login()
            for i, item in enumerate(plano, 1):
                print(f"\n[{i}/{len(plano)}] {item['titulo']}")
                s.enviar(item["video"], item["titulo"], descricao, playlist,
                         item["estreia"], miniatura, pausar=args.pausar)
                registrar(item)
                mover_para_enviados(item["video"])
                feitos += 1
                print("      OK: privado" if item["estreia"] is None
                      else f"      OK: estreia {item['estreia']:%d/%m %H:%M}")
        except (Exception, KeyboardInterrupt) as erro:
            print("\n" + "=" * 70)
            if isinstance(erro, KeyboardInterrupt):
                print("INTERROMPIDO por voce.")
            elif isinstance(erro, studio.ErroStudio):
                print(f"PAREI na etapa: {erro.etapa}")
                if erro.detalhe:
                    print(f"  {erro.detalhe}")
            else:
                print(f"PAREI na etapa: {s.etapa} (erro inesperado)")
                print(f"  {type(erro).__name__}: {str(erro).splitlines()[0] if str(erro) else ''}")
            print_diag = s.salvar_diagnostico()
            if print_diag:
                print(f"  print da tela: {print_diag}")
            if item is not None:
                print(f"  Video que falhou: {item['video'].name}")
                print("  Ele pode ter ficado como RASCUNHO no Studio: apague la antes de rodar de novo.")
            print(f"  Programados antes da parada: {feitos} de {len(plano)}")
            print("=" * 70)
            return 1

    print(f"\nPronto: {feitos} video(s) programado(s) como estreia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
