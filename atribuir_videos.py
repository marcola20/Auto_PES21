"""
atribuir_videos.py  --  Auto_PES21

Grava no site da liga o link do video de cada jogo no YouTube, para o telao
da partida passar a estreia. E o botao "Atribuir" da aba YouTube do painel.

De onde vem cada coisa:
  - youtube/historico.csv: o que ja subiu, com o titulo e o link que o
    upar_videos.py le da janela de upload. Video que subiu antes disso (ou
    cuja janela nao mostrou o link) fica sem: cole o link no painel.
  - O site acha a partida como no enviar_resultados.py: mandante x visitante
    pelo nome do arquivo, e o titulo do video diz a competicao e a rodada.
    Se o resultado desse video ja foi enviado (mesmo gravado_em), vai junto
    o id da partida que recebeu o resultado.

O que ja foi atribuido fica em ARQUIVO_CONTROLE. Sem argumentos, so vao os
videos com link novo; um link diferente do anterior substitui o do site.

Uso:
  python atribuir_videos.py                   -> atribui os que tem link e ainda nao foram
  python atribuir_videos.py --simular         -> so mostra o que faria (nao acessa a rede)
  python atribuir_videos.py --listar          -> os videos do historico em JSON (painel)
  python atribuir_videos.py CHAVE [--link L]  -> so esse video, mesmo se ja foi;
                                                 --link grava o link no historico antes
  CHAVE = "arquivo|tamanho", como o painel manda.
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

ARQUIVO_CONTROLE = "videos_atribuidos.json"
CAMINHO_API = "/api/admin/liga/video-pes"

# As mesmas colunas do youtube/upar_videos.py (as duas ultimas chegaram
# depois: linhas antigas nao tem).
COLUNAS_HISTORICO = ["enviado_em", "arquivo", "tamanho", "titulo", "estreia", "gravado_em", "link"]

# ==========================================================================

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
HISTORICO = PASTA_PROJETO / "youtube" / "historico.csv"

# IDs de video do YouTube tem 11 caracteres: letras, numeros, '-' e '_'.
RE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
RE_ID_NO_LINK = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|live/|shorts/|embed/)|studio\.youtube\.com/video/)"
    r"([A-Za-z0-9_-]{11})")


def normalizar_link(texto: str | None) -> str | None:
    """https://youtu.be/<id> a partir de qualquer link do video (inclusive o
    do Studio) ou do id puro; None se nao reconhecer."""
    texto = (texto or "").strip()
    if not texto:
        return None
    if RE_ID.match(texto):
        return f"https://youtu.be/{texto}"
    m = RE_ID_NO_LINK.search(texto)
    return f"https://youtu.be/{m.group(1)}" if m else None


def chave(linha: dict) -> str:
    return f"{linha['arquivo']}|{linha['tamanho']}"


def ler_historico() -> list:
    if not HISTORICO.is_file():
        return []
    with HISTORICO.open(encoding="utf-8", newline="") as f:
        return [{c: (linha.get(c) or "").strip() for c in COLUNAS_HISTORICO}
                for linha in csv.DictReader(f, delimiter=";")]


def gravar_historico(linhas: list) -> None:
    # Temporario e troca, como o controle: o historico impede subir duas vezes.
    temporario = HISTORICO.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLUNAS_HISTORICO)
        w.writerows([linha[c] for c in COLUNAS_HISTORICO] for linha in linhas)
    os.replace(temporario, HISTORICO)


def carregar_controle() -> dict:
    caminho = PASTA_PROJETO / ARQUIVO_CONTROLE
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def salvar_controle(controle: dict) -> None:
    caminho = PASTA_PROJETO / ARQUIVO_CONTROLE
    temporario = caminho.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(controle, f, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def times_do_arquivo(arquivo: str):
    """("Vasco", "Corinthians") de "Vasco vs Corinthians.mp4"; None se o
    video nao e um jogo ("Mosaico - Grupo C")."""
    nome = Path(arquivo).stem
    nome = re.sub(r" \(\d+\)$", "", nome)          # "(2)" do mover_para_enviados
    nome = re.split(r"\s*[|｜]\s*", nome)[0]       # nomes antigos: "A vs B ｜ Supercopa"
    partes = nome.split(" vs ")
    if len(partes) != 2 or not all(p.strip() for p in partes):
        return None
    return partes[0].strip(), partes[1].strip()


def rodada_e_serie(titulo: str) -> tuple:
    """Do titulo "A vs B | 4ª Rodada | Brasileirão - Série A": (4, "A")."""
    rodada = re.search(r"\|\s*(\d+)\s*[ªaº]?\s*Rodada", titulo, re.I)
    serie = re.search(r"S[ée]rie\s+([AB])\b", titulo)
    return (int(rodada.group(1)) if rodada else None), (serie.group(1) if serie else None)


def partida_do_resultado(gravado_em: str):
    """Id da partida que recebeu o resultado deste video, se ja foi enviado."""
    if not gravado_em:
        return None
    import enviar_resultados
    for anotado in enviar_resultados.carregar_controle().values():
        if anotado.get("gravado_em") == gravado_em and anotado.get("partida"):
            return anotado["partida"]
    return None


def montar_pedido(linha: dict) -> dict:
    casa, fora = times_do_arquivo(linha["arquivo"])
    rodada, serie = rodada_e_serie(linha["titulo"])
    return {
        "video": linha["titulo"] or linha["arquivo"],
        "serie": serie,
        "rodada": rodada,
        "casa": {"time": casa},
        "fora": {"time": fora},
        "link": linha["link"],
        "gravado_em": linha["gravado_em"] or None,
    }


def listar_em_json() -> int:
    """--listar: o historico, do mais novo para o mais velho, com a situacao no site."""
    controle = carregar_controle()
    videos = []
    for linha in reversed(ler_historico()):
        times = times_do_arquivo(linha["arquivo"])
        anotado = controle.get(chave(linha)) or {}
        no_site = bool(linha["link"]) and anotado.get("link") == linha["link"]
        videos.append({
            "chave": chave(linha),
            "arquivo": linha["arquivo"],
            "titulo": linha["titulo"],
            "enviado_em": linha["enviado_em"],
            "estreia": linha["estreia"],
            "link": linha["link"],
            "jogo": f"{times[0]} x {times[1]}" if times else None,
            "no_site": no_site,
            "onde": anotado.get("onde") if no_site else None,
        })
    print(json.dumps(videos, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Grava no site o link do video de cada jogo.")
    parser.add_argument("chave", nargs="?", help='"arquivo|tamanho": so esse video, mesmo se ja foi')
    parser.add_argument("--link", help="link do video (grava no historico antes de atribuir)")
    parser.add_argument("--simular", action="store_true", help="mostra o que faria, sem enviar")
    parser.add_argument("--listar", action="store_true", help="o historico em JSON (para o painel)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")
    if args.listar:
        return listar_em_json()

    linhas = ler_historico()
    if args.chave:
        escolhidas = [l for l in linhas if chave(l) == args.chave]
        if not escolhidas:
            print(f"ERRO: {args.chave} nao esta no historico.csv")
            return 1
        if args.link is not None:
            link = normalizar_link(args.link)
            if not link:
                print(f"ERRO: nao reconheci esse link do YouTube: {args.link}")
                return 1
            if escolhidas[0]["link"] != link:
                escolhidas[0]["link"] = link
                if not args.simular:
                    gravar_historico(linhas)
                    print(f"Link gravado no historico: {link}\n")
    else:
        escolhidas = linhas

    import caminhos
    from enviar_resultados import VAR_TOKEN, VAR_URL, enviar
    url = os.environ.get(VAR_URL) or caminhos.SITE_URL
    token = os.environ.get(VAR_TOKEN) or caminhos.SITE_TOKEN
    if not args.simular and (not url or not token):
        print(f"ERRO: preencha 'url' e 'token' na secao [site] de:\n  {caminhos.ARQUIVO}")
        return 1
    if args.simular:
        print("MODO SIMULACAO: nada sera enviado.\n")

    controle = carregar_controle()
    feitos, sem_link, erros = 0, [], []
    for linha in escolhidas:
        if not times_do_arquivo(linha["arquivo"]):
            if args.chave:
                print(f"ERRO: {linha['arquivo']} nao e um jogo (o nome nao e \"Casa vs Fora\").")
                return 1
            continue
        if not linha["link"]:
            sem_link.append(linha["arquivo"])
            continue
        if not args.chave and (controle.get(chave(linha)) or {}).get("link") == linha["link"]:
            continue

        pedido = montar_pedido(linha)
        partida = partida_do_resultado(linha["gravado_em"])
        print(f"- {linha['titulo']}\n    {linha['link']}")
        if args.simular:
            print("    atribuiria" + (" (na partida do resultado ja enviado)" if partida else "") + "\n")
            feitos += 1
            continue

        corpo = json.dumps(pedido, ensure_ascii=False).encode("utf-8")
        try:
            ok, resposta = enviar(url, token, corpo, partida, caminho_api=CAMINHO_API)
        except Exception as erro:
            erros.append((linha["arquivo"], f"{type(erro).__name__}: {erro}"))
            print(f"    ERRO: {type(erro).__name__}: {erro}\n")
            continue
        if not ok:
            mensagem = resposta.get("message") or ""
            if mensagem.startswith("HTTP 404"):
                mensagem = ("o site ainda nao tem a rota de video "
                            "(falta publicar a versao nova do Fc25_Draft)")
            erros.append((linha["arquivo"], mensagem))
            print(f"    ERRO: {mensagem}")
            for candidato in resposta.get("candidatos") or []:
                print(f"      candidato: {candidato}")
            print()
            continue

        onde = f"{resposta['competicao']}, {resposta['onde']}"
        print(f"    OK: {onde}: {resposta['casa']} x {resposta['fora']}")
        if resposta.get("videoAnterior"):
            print(f"    (substituiu o video que estava la: https://youtu.be/{resposta['videoAnterior']})")
        print()
        feitos += 1
        controle[chave(linha)] = {
            "link": linha["link"],
            "partida": resposta.get("partidaId"),
            "onde": onde,
            "atribuido_em": datetime.now().isoformat(timespec="seconds"),
        }
        salvar_controle(controle)

    print("=" * 66)
    verbo = "Atribuiria" if args.simular else "Atribuidos"
    print(f"  {verbo}: {feitos}   Sem link: {len(sem_link)}   Erros: {len(erros)}")
    if sem_link and args.chave is None and len(sem_link) <= 10:
        print("\n  Sem link (cole no painel, na aba YouTube):")
        for arquivo in sem_link:
            print(f"    {arquivo}")
    if erros:
        print("\n  Com erro:")
        for arquivo, mensagem in erros:
            print(f"    {arquivo}: {mensagem}")
    print("=" * 66)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
