"""
enviar_resultados.py  --  Auto_PES21

Envia para o site da liga (Fc25_Draft) os .json que o extrair_eventos.py
gerou ao lado de cada video. O site acha a partida pelo mandante x visitante,
grava placar, gols, assistencias, cartoes e substituicoes e recalcula a
classificacao.

E o ultimo passo, separado do loop de gravacao: voce roda quando quiser,
depois do extrair_eventos.py. Nao mexe nos videos nem nos .json - so le.

Como decide o que enviar:
  - .json com "status": "revisar" e PULADO (com aviso): o OCR ficou em
    duvida em algo, e resultado errado no site e pior que resultado nenhum.
    Corrija o .json na mao (e mude o status para "ok") e rode de novo.
  - O que ja foi enviado fica anotado em ARQUIVO_CONTROLE, junto com um
    hash do conteudo. Se o .json mudar (reextraido ou corrigido), ele e
    enviado de novo - o site ATUALIZA a partida, nao duplica.
  - Um jogo com erro (partida nao achada, rede fora...) nao para os outros
    e nao e anotado, entao e tentado de novo na proxima vez.

Precisa de duas variaveis de ambiente (nada de token dentro do codigo):
  CBFV_API_URL    endereco do site, ex.: https://cbfv.exemplo.com
  CBFV_API_TOKEN  seu token de admin do site

Uso:
  python enviar_resultados.py                -> envia os novos/alterados
  python enviar_resultados.py --simular      -> so mostra o que enviaria
                                                (nao acessa a rede)
  python enviar_resultados.py "arquivo.json" -> envia esse, mesmo se ja foi
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

# Mesma pasta do extrair_eventos.py: os .json ficam ao lado dos videos.
PASTA_VIDEOS = r"C:\Users\Marcola\Videos\NVIDIA\eFootball PES 2021"

# Onde fica anotado o que ja foi enviado. Fica no projeto, e nao na pasta
# de videos, para essa pasta continuar tendo so o que a gravacao produz.
ARQUIVO_CONTROLE = "resultados_enviados.json"

VAR_URL = "CBFV_API_URL"
VAR_TOKEN = "CBFV_API_TOKEN"
CAMINHO_API = "/api/admin/liga/resultados-pes"

# O site recalcula a classificacao a cada jogo; 60s sobra. Se o servidor
# estiver dormindo (hospedagem gratuita), a primeira chamada demora mais.
SEGUNDOS_TIMEOUT = 60

# ==========================================================================

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent


def carregar_controle() -> dict:
    caminho = PASTA_PROJETO / ARQUIVO_CONTROLE
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def salvar_controle(controle: dict) -> None:
    # Grava num temporario e troca: se o script cair no meio da escrita, o
    # controle antigo continua inteiro (senao tudo seria reenviado).
    caminho = PASTA_PROJETO / ARQUIVO_CONTROLE
    temporario = caminho.with_suffix(".tmp")
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(controle, f, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


def hash_do_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def listar_jsons(pasta: Path) -> list:
    return sorted(pasta.glob("*.json"), key=lambda p: p.stat().st_mtime)


def descrever(dados: dict) -> str:
    c, f = dados.get("casa") or {}, dados.get("fora") or {}
    return f"{c.get('time')} {c.get('gols')} x {f.get('gols')} {f.get('time')}"


def enviar(url: str, token: str, corpo: bytes) -> tuple:
    """Devolve (ok, resposta_em_dict). Erro HTTP nao e excecao: o site manda
    a mensagem em {"message": ...} e ela e o que interessa mostrar."""
    pedido = urllib.request.Request(
        url.rstrip("/") + CAMINHO_API,
        data=corpo,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=SEGUNDOS_TIMEOUT) as resposta:
            return True, json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        texto = erro.read().decode("utf-8", errors="replace")
        try:
            detalhe = json.loads(texto)
        except ValueError:
            detalhe = {}
        if erro.code == 401:
            detalhe["message"] = f"token recusado (confira {VAR_TOKEN})"
        elif erro.code == 403:
            detalhe["message"] = "o token nao e de admin"
        detalhe.setdefault("message", f"HTTP {erro.code}: {texto[:200]}")
        return False, detalhe


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia os resultados extraidos para o site da liga.")
    parser.add_argument("arquivo", nargs="?", help="um .json so (envia mesmo se ja foi)")
    parser.add_argument("--simular", action="store_true", help="mostra o que enviaria, sem enviar")
    args = parser.parse_args()

    # O terminal do Windows as vezes nao e UTF-8 (mesmo motivo do extrair_eventos.py).
    sys.stdout.reconfigure(errors="replace")

    pasta = Path(PASTA_VIDEOS)
    if args.arquivo:
        caminho = Path(args.arquivo)
        if not caminho.is_absolute():
            caminho = pasta / caminho
        if not caminho.is_file():
            print(f"ERRO: nao achei o arquivo:\n  {caminho}")
            return 1
        arquivos = [caminho]
    else:
        arquivos = listar_jsons(pasta)

    url, token = os.environ.get(VAR_URL), os.environ.get(VAR_TOKEN)
    if not args.simular and (not url or not token):
        print(f"ERRO: defina as variaveis de ambiente {VAR_URL} e {VAR_TOKEN}.")
        print("  (ou rode com --simular para so ver o que seria enviado)")
        return 1

    controle = carregar_controle()
    enviados, sem_mudanca, pulados, erros = [], 0, [], []
    nao_identificados = []   # (jogo, lado/time, papel, nome, motivo)

    if args.simular:
        print("MODO SIMULACAO: nada sera enviado.\n")

    for caminho in arquivos:
        nome = caminho.name
        hash_atual = hash_do_arquivo(caminho)
        anotado = controle.get(nome)
        if not args.arquivo and anotado and anotado.get("hash") == hash_atual:
            sem_mudanca += 1
            continue

        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError) as erro:
            erros.append((nome, f"nao consegui ler o .json: {erro}"))
            print(f"- {nome}\n    ERRO: nao consegui ler o .json: {erro}\n")
            continue

        jogo = descrever(dados)
        if dados.get("status") != "ok":
            pulados.append(nome)
            print(f"- {nome}\n    PULADO: status \"{dados.get('status')}\" - confira o video e corrija o .json.")
            for aviso in dados.get("avisos") or []:
                print(f"      aviso: {aviso}")
            print()
            continue

        motivo = "reenviar (arquivo mudou)" if anotado else "novo"
        if args.simular:
            enviados.append(nome)
            print(f"- {nome}\n    enviaria ({motivo}): {jogo}\n")
            continue

        print(f"- {nome}")
        try:
            ok, resposta = enviar(url, token, caminho.read_bytes())
        except Exception as erro:
            # Rede fora, DNS, timeout...: segue para os outros jogos.
            erros.append((nome, f"{type(erro).__name__}: {erro}"))
            print(f"    ERRO: {type(erro).__name__}: {erro}\n")
            continue

        if not ok:
            mensagem = resposta.get("message")
            erros.append((nome, mensagem))
            print(f"    ERRO: {mensagem}")
            for candidato in resposta.get("candidatos") or []:
                print(f"      candidato: {candidato}")
            print()
            continue

        enviados.append(nome)
        print(f"    {resposta['competicao']}, rodada {resposta['rodada']}: "
              f"{resposta['casa']} {resposta['golsCasa']} x {resposta['golsFora']} {resposta['fora']}  |  "
              f"{resposta['situacao']}  |  {resposta['eventosGravados']} evento(s)")
        for n in resposta.get("naoIdentificados") or []:
            nome_pes = n["nome"] or "(nome ilegivel)"
            nao_identificados.append((jogo, n["time"], n["papel"], nome_pes, n["motivo"]))
            print(f"      nao identificado ({n['time']}, {n['papel']}): {nome_pes} - {n['motivo']}")
        for aviso in resposta.get("avisos") or []:
            print(f"      aviso: {aviso}")
        print()

        controle[nome] = {
            "hash": hash_atual,
            "enviado_em": datetime.now().isoformat(timespec="seconds"),
            "partida": resposta.get("partidaId"),
            "jogo": jogo,
        }
        # Anota a cada jogo: se cair no meio, os ja enviados nao vao de novo.
        salvar_controle(controle)

    print("=" * 66)
    verbo = "Enviaria" if args.simular else "Enviados"
    print(f"  {verbo}: {len(enviados)}   Ja enviados sem mudanca: {sem_mudanca}   "
          f"Pulados (revisar): {len(pulados)}   Erros: {len(erros)}")
    if nao_identificados:
        print(f"\n  Jogadores nao identificados ({len(nao_identificados)}) - lance na mao pela tela da liga:")
        for jogo, time, papel, nome, motivo in nao_identificados:
            print(f"    {jogo}  |  {time}, {papel}: {nome}  ({motivo})")
    if erros:
        print("\n  Com erro (serao tentados de novo na proxima vez):")
        for nome, mensagem in erros:
            print(f"    {nome}: {mensagem}")
    print("=" * 66)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
