"""
times.py  --  Auto_PES21

Lista dos times do Brasileirao Serie A no PES 2021, na ORDEM ALFABETICA em que
aparecem na tela de selecao. A ordem importa: e ela que diz quantas vezes
apertar "Baixo" para chegar em cada time.

Este arquivo e importado pelos outros scripts, entao a lista fica num lugar so.
"""

import unicodedata

TIMES = [
    "Botafogo",
    "Corinthians",
    "Coritiba",
    "Cruzeiro",
    "Flamengo",
    "Fluminense",
    "Grêmio",
    "Inter",
    "Palmeiras",
    "Santos",
    "São Paulo",
    "Vasco",
]


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
        print(f"  [{i:2d}]  {time:14s}  ->  arquivo: {apelido(time)}.png")
