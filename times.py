"""
times.py  --  Auto_PES21

Lista dos times no PES 2021, na ORDEM em que aparecem na tela de selecao. A
ordem importa: e ela que diz quantas vezes apertar "Baixo" para chegar em cada
time.

Todos os times ficam dentro da competicao "Brasileirao Serie A" do PES, para a
navegacao usar uma lista so. Mas a ordem ali NAO e alfabetica: primeiro vem os
10 times da Serie A, depois os 8 da Serie B, e por fim os 2 que so completam a
liga do jogo (o PES exige 20). A serie de cada um vai no nome do video.

Este arquivo e importado pelos outros scripts, entao a lista fica num lugar so.
"""

import unicodedata

SERIE_A = [
    "Botafogo",
    "Coritiba",
    "Cruzeiro",
    "Flamengo",
    "Fluminense",
    "Grêmio",
    "Palmeiras",
    "Santos",
    "São Paulo",
    "Vasco",
]

SERIE_B = [
    "Corinthians",
    "EC Juventude",
    "Figueirense",
    "Inter",
    "Náutico",
    "Paraná",
    "Sport",
    "Vitória",
]

# Nao jogam nenhuma das series, mas estao no fim da lista do PES. Ficam aqui
# para a calibracao fotografar a lista inteira e o reconhecimento nao se
# confundir se o cursor parar num deles.
FORA_DAS_SERIES = [
    "Portuguesa",
    "Ipatinga",
]

TIMES = SERIE_A + SERIE_B + FORA_DAS_SERIES


def indice_do_time(nome: str) -> int:
    """Diz em que posicao da lista o time esta (0 = primeiro).

    Aceita o nome com ou sem acento, maiusculo ou minusculo, para voce nao
    precisar digitar "Grêmio" com acento toda vez.
    """
    alvo = normalizar(nome)
    for i, time in enumerate(TIMES):
        if normalizar(time) == alvo:
            return i
    raise ValueError(
        f"Time '{nome}' nao esta na lista. Os validos sao:\n  "
        + ", ".join(TIMES)
    )


def nome_oficial(nome: str) -> str:
    """O nome como esta na lista, com acento: 'gremio' -> 'Grêmio'.

    Serve para o nome do video sair bonito mesmo que em JOGOS o time tenha
    sido digitado sem acento.
    """
    return TIMES[indice_do_time(nome)]


def serie_do_time(nome: str):
    """'A', 'B', ou None para os times que so completam a liga do PES."""
    time = nome_oficial(nome)
    if time in SERIE_A:
        return "A"
    if time in SERIE_B:
        return "B"
    return None


def time_do_site(nome: str):
    """O time da lista que o site chama de `nome`, ou None se nao achar.

    O site nem sempre usa o nome do PES: "Internacional" e "Inter",
    "Juventude" e "EC Juventude". Vale o nome igual; senao, um que comeca o
    outro ("inter" / "internacional") ou e a ultima palavra dele ("juventude" /
    "ec juventude") - desde que so UM time da lista sirva, para nao chutar.
    """
    alvo = normalizar(nome)
    for time in TIMES:
        if normalizar(time) == alvo:
            return time
    parecidos = [time for time in TIMES
                 if _um_contem_o_outro(normalizar(time), alvo)]
    return parecidos[0] if len(parecidos) == 1 else None


def _um_contem_o_outro(a: str, b: str) -> bool:
    curto, longo = sorted((a, b), key=len)
    return longo.startswith(curto) or longo.endswith(" " + curto)


def normalizar(texto: str) -> str:
    """Tira acentos e deixa minusculo: 'São Paulo' -> 'sao paulo'."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.strip().lower()


def apelido(nome: str) -> str:
    """Nome seguro para usar em nome de arquivo: 'São Paulo' -> 'sao_paulo'."""
    return normalizar(nome).replace(" ", "_")


if __name__ == "__main__":
    print(f"{len(TIMES)} times cadastrados:\n")
    for i, time in enumerate(TIMES):
        serie = serie_do_time(time) or "-"
        print(f"  [{i:2d}]  {time:14s}  serie {serie}  ->  arquivo: {apelido(time)}.png")
