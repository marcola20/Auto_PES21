"""
ler_jogadores.py  --  Auto_PES21

Le as fotos do "Registro individual de jogo" que o rodar_jogos.py tira depois
de cada partida (pasta_videos/Jogadores/<video> <data>/) e devolve as
estatisticas de cada jogador dos dois times.

Quem chama e o extrair_eventos.py, que poe o resultado no .json do video
(campo "jogadores"). Tambem roda sozinho, para conferir uma pasta:
  python ler_jogadores.py "pasta das fotos"

Como le cada foto (1080p, recorte a partir de (105, 47) da tela):
  - A lista da esquerda aparece em TODAS as fotos do time: os nomes, as
    posicoes e as notas sao votados entre elas (13 fotos = 13 leituras).
  - Qual jogador a foto mostra e a linha com o nome em ciano.
  - Os numeros da direita estao sempre na mesma ordem e na mesma altura:
    nao precisa ler os rotulos. Cada numero passa pelo ler_pecas do
    extrair_eventos (colado numa linha falsa, em tres alturas, e votado).
  - O grupo da posicao sai da COR do selo, que o PES usa sempre igual:
    amarelo goleiro, azul defesa, verde meio, vermelho ataque.

Nada e inventado: numero ilegivel ou empatado na votacao vira null, com aviso.
"""

# ==========================================================================
# CONFIGURACOES (coordenadas da TELA 1920x1080, medidas nas fotos reais)
# ==========================================================================

ORIGEM_FOTO = (105, 47)          # visao.REGIAO_PAINEIS_REGISTRO comeca aqui

REGIAO_TITULO = (700, 62, 1290, 122)      # "Registro individual de jogo"
REGIAO_TIME = (128, 62, 460, 122)         # nome do time

# Lista da esquerda: linha k centrada em y = 197 + 42k (igual ao visao.py).
X_SELO = (140, 202)                       # "GO", "ZC", "VOL"...
X_NOME = (215, 545)
X_NOTA = (550, 615)
X_ESTRELA = (612, 645)

# Numeros da direita: linha i centrada em y = 219 + 42i.
Y_PRIMEIRO_VALOR = 219
PASSO_VALOR = 42
X_VALOR_CAMPO = (1000, 1240)
X_VALOR_GOLEIRO = (1600, 1800)
MEIA_ALTURA = 19

# Na ordem da tela. Linha com "N (M)" vira dois campos.
CAMPOS_DE_CAMPO = [
    ("gols", None), ("gols_de_penalti", None), ("gols_de_falta", None),
    ("assistencias", None), ("chutes", "chutes_a_gol"), ("passes", "passes_certos"),
    ("cruzamentos", None), ("faltas", "impedimentos"), ("cobrancas_de_falta", None),
    ("escanteios", None), ("interceptacoes", None), ("minutos", None), ("toques", None),
    ("distancia_de_drible", None), ("velocidade_media", None),
    ("desarmes", "desarmes_certos"), ("afastamentos", None),
]
CAMPOS_DE_GOLEIRO = [("chutes_sofridos", "chutes_sofridos_a_gol"), ("defesas", None)]
CAMPOS_DECIMAIS = {"distancia_de_drible", "velocidade_media"}   # "19.1 m", "13.4 km/h"

# Texto da lista: escuro sobre fundo claro (o selecionado e ciano, tambem
# com pouco vermelho). Fundo da lista medido > 180 no vermelho.
VERMELHO_MAXIMO_TEXTO = 120

# Quem entrou no fim fica com "-" no lugar da nota: recortado justo, o traco
# tem ~4 px de altura e um algarismo ~22 (em 1080p).
ALTURA_MAXIMA_TRACO = 10

# Pontinhos brancos (chuva, reflexo do estadio) grudados nos numeros: o
# "11 (11)" com um ponto antes do "(" o OCR nao lia. Algarismo e parentese
# tem 18+ px de altura em 1080p; mancha mais baixa que isto e sujeira, menos
# o ponto decimal ("19.1 m"), que fica na linha de base dos algarismos.
ALTURA_MINIMA_ALGARISMO = 14
FOLGA_LINHA_DE_BASE = 4

# Estrela do melhor em campo: disco ciano, ~400 pixels em 1080p.
PIXELS_MINIMOS_ESTRELA = 150

# Selo de posicao: letras coloridas sobre fundo ESCURO. Medido (Vasco x
# Santos): 886+ dos 1240 pixels do recorte do selo sao escuros numa linha de
# verdade; a placa clara do estadio logo abaixo da lista (fundo claro, como
# uma linha) tem 0 a 463 e virava 2 jogadores fantasmas sem nome.
FRACAO_MINIMA_ESCURO_SELO = 0.6

# Cor do selo de posicao -> grupo. Medido: goleiro (240,200,0), defesa
# (40,200,240), meio (80,200,40), ataque (240,40,80).
GRUPOS = {"goleiro": (240, 200, 0), "defesa": (40, 200, 240),
          "meio": (80, 200, 40), "ataque": (240, 40, 80)}

MAX_LINHAS = 16

# ==========================================================================

import json
import re
import sys
from pathlib import Path

from PIL import Image

import extrair_eventos as ee
import times


def tela_da_foto(caminho: Path) -> Image.Image:
    """A foto e um recorte; devolve-a na posicao da tela, para as
    coordenadas daqui valerem direto."""
    tela = Image.new("RGB", (1920, 1080))
    tela.paste(Image.open(caminho).convert("RGB"), ORIGEM_FOTO)
    return tela


def y_linha(k: int) -> int:
    return 197 + 42 * k


def faixa(tela, x, y, meia=MEIA_ALTURA):
    return tela.crop((x[0], y - meia, x[1], y + meia))


def escuro_para_branco(img: Image.Image) -> Image.Image:
    """Texto escuro sobre claro -> branco sobre preto, que e o que o
    ler_pecas espera (ele foi feito para o texto branco do fim de jogo)."""
    r = img.convert("RGB").split()[0]
    return r.point(lambda v: 255 if v < VERMELHO_MAXIMO_TEXTO else 0).convert("RGB")


def colorido_para_branco(img: Image.Image) -> Image.Image:
    """Letras coloridas do selo (amarelo, azul, verde, vermelho) sobre o
    fundo escuro -> branco sobre preto."""
    px = [(255, 255, 255) if max(p) > 110 and max(p) - min(p) > 60 else (0, 0, 0)
          for p in img.convert("RGB").get_flattened_data()]
    out = Image.new("RGB", img.size)
    out.putdata(px)
    return out


def linhas_da_lista(tela) -> int:
    """Quantas linhas a lista tem: o fundo claro da lista vai ate o fim dela,
    e toda linha tem o selo da posicao (o estadio abaixo pode ser claro)."""
    n = 0
    for k in range(MAX_LINHAS):
        amostra = tela.crop((450, y_linha(k) - 10, 540, y_linha(k) + 10)).convert("L")
        claros = sum(1 for v in amostra.get_flattened_data() if v > 170)
        if claros < 0.5 * amostra.width * amostra.height or not tem_selo(tela, k):
            break
        n += 1
    return n


def tem_selo(tela, k) -> bool:
    selo = list(faixa(tela, X_SELO, y_linha(k), 10).convert("RGB").get_flattened_data())
    escuros = sum(1 for p in selo if max(p) < 70)
    cores = sum(1 for p in selo if max(p) > 120 and max(p) - min(p) > 60)
    return escuros >= FRACAO_MINIMA_ESCURO_SELO * len(selo) and cores >= 30


def grupo_do_selo(tela, k):
    selo = faixa(tela, X_SELO, y_linha(k), 10).convert("RGB")
    cores = [p for p in selo.get_flattened_data() if max(p) > 120 and max(p) - min(p) > 60]
    if len(cores) < 30:
        return None
    media = tuple(sum(c[i] for c in cores) / len(cores) for i in range(3))
    return min(GRUPOS, key=lambda g: sum((a - b) ** 2 for a, b in zip(GRUPOS[g], media)))


def tem_estrela(tela, k) -> bool:
    regiao = faixa(tela, X_ESTRELA, y_linha(k), 15).convert("RGB")
    return sum(1 for p in regiao.get_flattened_data() if ee.eh_ciano(*p)) >= PIXELS_MINIMOS_ESTRELA


def manchas(img: Image.Image) -> list:
    """Manchas de texto (branco) da imagem: lista de (pixels, caixa)."""
    bw = ee.binarizar(img).load()
    w, h = img.size
    vistos = set()
    saida = []
    for y in range(h):
        for x in range(w):
            if bw[x, y] != 0 or (x, y) in vistos:
                continue
            mancha, pilha = [], [(x, y)]
            vistos.add((x, y))
            while pilha:
                a, b = pilha.pop()
                mancha.append((a, b))
                for na in (a - 1, a, a + 1):
                    for nb in (b - 1, b, b + 1):
                        if 0 <= na < w and 0 <= nb < h and (na, nb) not in vistos                                 and bw[na, nb] == 0:
                            vistos.add((na, nb))
                            pilha.append((na, nb))
            xs = [q[0] for q in mancha]
            ys = [q[1] for q in mancha]
            saida.append((mancha, (min(xs), min(ys), max(xs), max(ys))))
    return saida


def so_algarismos(img: Image.Image) -> Image.Image:
    """Apaga o que nao e algarismo, parentese, unidade ou ponto decimal."""
    todas = manchas(img)
    altas = [c for _, c in todas if c[3] - c[1] + 1 >= ALTURA_MINIMA_ALGARISMO]
    if not altas:
        return img
    base = max(c[3] for c in altas)
    esquerda = min(c[0] for c in altas)
    direita = max(c[2] for c in altas)
    img = img.copy()
    px = img.load()
    for pixels, c in todas:
        alta = c[3] - c[1] + 1 >= ALTURA_MINIMA_ALGARISMO
        # O ponto decimal fica na linha de base E entre os algarismos.
        ponto = (abs(c[3] - base) <= FOLGA_LINHA_DE_BASE
                 and esquerda < c[0] and c[2] < direita)
        if not alta and not ponto:
            for q in pixels:
                px[q] = (0, 0, 0)
    return img


def partes_do_par(peca: Image.Image):
    """'11 (11)' -> recortes '11' e '11' (sem os parenteses).

    O OCR do Windows pula o "0 (0)" inteiro e as vezes ate o "(0)" sozinho,
    mas le um "0" solto. Cortar no maior vao nao serve: nesta fonte o "(" e
    um traco quase reto e, com um pontinho de chuva grudado, vira um "7".
    O que separa bem e a ALTURA: cada parentese e uma mancha ~5 px mais alta
    que os algarismos (24 x 19 em 1080p), e leva junto o que estiver grudado.
    """
    img = ee.justo(peca)
    if img is None:
        return None
    todas = [c for _, c in manchas(img)]
    alturas = sorted(c[3] - c[1] + 1 for c in todas
                     if c[3] - c[1] + 1 >= ALTURA_MINIMA_ALGARISMO)
    if not alturas:
        return None
    algarismo = alturas[len(alturas) // 2] if len(alturas) % 2 else alturas[len(alturas) // 2 - 1]
    parenteses = sorted((c for c in todas if c[3] - c[1] + 1 >= algarismo + 3),
                        key=lambda c: c[0])
    if len(parenteses) < 2:
        return None
    abre, fecha = parenteses[0], parenteses[-1]
    if abre[0] < 3 or fecha[0] - abre[2] < 4:
        return None
    esq = so_algarismos(img.crop((0, 0, abre[0], img.height)))
    dentro = so_algarismos(img.crop((abre[2] + 1, 0, fecha[0], img.height)))
    return esq, dentro


def eh_traco(peca: Image.Image) -> bool:
    j = ee.justo(peca)
    return j is not None and j.height <= ALTURA_MAXIMA_TRACO


def ler_decimal(texto):
    t = texto.translate(ee.TROCAS_DIGITO).replace(",", ".")
    m = re.match(r"\s*(\d{1,3})\s*\.\s*(\d)", t)
    return float(f"{m.group(1)}.{m.group(2)}") if m else None


def votos_de_valor(ocr, peca, separador, eh_par, decimal):
    """Os valores lidos de um numero (cada um ja interpretado)."""
    textos = ee.ler_pecas(ocr, [peca], separador)[0]
    if eh_par:
        valores = [v for v in (ee.ler_par(t) for t in textos) if v]
        partes = partes_do_par(peca)
        if partes:
            esq, dentro = ee.ler_pecas(ocr, list(partes), separador)
            for a, b in zip(esq, dentro):
                a, b = ee.ler_inteiro(a), ee.ler_inteiro(b)
                if a is not None and b is not None and b <= a:
                    valores.append((a, b))
        return valores
    if decimal:
        return [v for v in (ler_decimal(t) for t in textos) if v is not None]
    return [v for v in (ee.ler_inteiro(t) for t in textos) if v is not None]


def ler_numeros(ocr, tela, separador, campos, x, avisos, quem):
    """Os numeros de uma coluna (de campo ou de goleiro) de uma foto."""
    pecas = [so_algarismos(faixa(tela, x, Y_PRIMEIRO_VALOR + PASSO_VALOR * i))
             for i in range(len(campos))]
    # Primeiro tudo junto (rapido); o que nao sair, um a um com as metades.
    lidos = ee.ler_pecas(ocr, pecas, separador)
    saida = {}
    for (campo, segundo), peca, textos in zip(campos, pecas, lidos):
        eh_par = segundo is not None
        decimal = campo in CAMPOS_DECIMAIS
        if eh_par:
            valores = [v for v in (ee.ler_par(t) for t in textos) if v]
        elif decimal:
            valores = [v for v in (ler_decimal(t) for t in textos) if v is not None]
        else:
            valores = [v for v in (ee.ler_inteiro(t) for t in textos) if v is not None]
        if not valores:
            valores = votos_de_valor(ocr, peca, separador, eh_par, decimal)
        valor, problema = ee.votar(valores)
        if problema:
            avisos.add(f"jogadores: {quem}, {campo}: {problema}")
        if eh_par:
            saida[campo], saida[segundo] = valor if valor else (None, None)
        else:
            saida[campo] = valor
    return saida


def ler_lista(ocr, telas, separador, avisos, rotulo):
    """Nome, posicao, grupo, nota e estrela de cada linha, votados entre
    todas as fotos do time."""
    n = max(linhas_da_lista(t) for t in telas)
    nomes = [[] for _ in range(n)]
    selos = [[] for _ in range(n)]
    notas = [[] for _ in range(n)]
    tracos = [0] * n
    grupos = [[] for _ in range(n)]
    estrelas = [0] * n
    for tela in telas:
        recorte = tela.crop((X_NOME[0], y_linha(0) - 21, X_NOME[1], y_linha(n - 1) + 21))
        for escala in (1, 2):
            for ln in ocr.ler(ee.ampliar(recorte, escala), escala):
                k = round((ln.cy + y_linha(0) - 21 - y_linha(0)) / 42)
                if 0 <= k < n:
                    nomes[k].append(ln.texto)
        pecas_nota = [escuro_para_branco(faixa(tela, X_NOTA, y_linha(k))) for k in range(n)]
        pecas_selo = [colorido_para_branco(faixa(tela, X_SELO, y_linha(k), 12)) for k in range(n)]
        # Notas e selos em passadas separadas: juntos na mesma grade, o OCR
        # pulava o "LD" do Rafinha em TODAS as fotos (Flamengo x Corinthians),
        # e sozinho le "LD" sempre.
        lidas_nota = ee.ler_pecas(ocr, pecas_nota, separador)
        lidas_selo = ee.ler_pecas(ocr, pecas_selo, separador)
        for k in range(n):
            if eh_traco(pecas_nota[k]):
                tracos[k] += 1
            notas[k] += [ee.ler_nota(t) for t in lidas_nota[k]]
            selos[k] += [re.sub(r"[^A-Z]", "", t.upper()) or None for t in lidas_selo[k]]
            grupos[k].append(grupo_do_selo(tela, k))
            estrelas[k] += tem_estrela(tela, k)

    # O que a grade nao leu em nenhuma foto: uma peca por vez, em ate 3 fotos.
    for k in range(n):
        for tela in telas[:3]:
            if not any(selos[k]):
                pecas = [colorido_para_branco(faixa(tela, X_SELO, y_linha(k), 12))]
                selos[k] += [re.sub(r"[^A-Z]", "", t.upper()) or None
                             for t in ee.ler_pecas(ocr, pecas, separador)[0]]
            if tracos[k] <= len(telas) / 2 and not any(v is not None for v in notas[k]):
                pecas = [escuro_para_branco(faixa(tela, X_NOTA, y_linha(k)))]
                notas[k] += [ee.ler_nota(t) for t in ee.ler_pecas(ocr, pecas, separador)[0]]

    lista = []
    for k in range(n):
        nome, problema = ee.votar_nome(nomes[k])
        if problema:
            avisos.add(f"jogadores: {rotulo}, nome da linha {k + 1}: {problema}")
        posicao, _ = ee.votar(selos[k])
        grupo, _ = ee.votar(grupos[k])
        if tracos[k] > len(telas) / 2:
            nota = None                      # "-": entrou no fim, sem nota
        else:
            nota, problema = ee.votar(notas[k])
            if problema:
                avisos.add(f"jogadores: {rotulo}, nota de {nome}: {problema}", revisar=False)
        lista.append({"jogador": nome, "posicao": posicao, "grupo": grupo, "nota": nota,
                      "melhor_em_campo": estrelas[k] > len(telas) / 2})
    return lista


def ler_time(ocr, fotos: list, avisos, rotulo):
    """Uma lista de jogadores com as estatisticas, a partir das fotos de um time."""
    telas = [tela_da_foto(f) for f in fotos]
    separador = telas[0].crop(REGIAO_TITULO)

    lidos = []
    for tela in telas:
        recorte = tela.crop(REGIAO_TIME)
        lidos += [ln.texto for esc in (1, 2) for ln in ocr.ler(ee.ampliar(recorte, esc), esc)]
    nome_time, _ = ee.votar([times.normalizar(t) for t in lidos])

    lista = ler_lista(ocr, telas, separador, avisos, rotulo)
    vistos = set()
    for tela, foto in zip(telas, fotos):
        import visao
        k = visao.linha_selecionada_no_registro(tela)
        if k is None or k >= len(lista):
            avisos.add(f"jogadores: {rotulo}, {foto.name}: nao achei o jogador selecionado")
            continue
        if k in vistos:
            continue
        vistos.add(k)
        jogador = lista[k]
        quem = f"{rotulo} {jogador['jogador'] or f'linha {k + 1}'}"
        jogador.update(ler_numeros(ocr, tela, separador, CAMPOS_DE_CAMPO, X_VALOR_CAMPO,
                                   avisos, quem))
        if jogador["grupo"] == "goleiro":
            jogador.update(ler_numeros(ocr, tela, separador, CAMPOS_DE_GOLEIRO,
                                       X_VALOR_GOLEIRO, avisos, quem))
    for k, jogador in enumerate(lista):
        if k not in vistos:
            avisos.add(f"jogadores: {rotulo}, sem foto de {jogador['jogador']}")
    return nome_time, lista


def ler_pasta(pasta: Path, ocr, avisos, casa=None, fora=None) -> dict:
    """{"casa": [...], "fora": [...]} a partir da pasta de fotos de uma partida.

    O time de cada lado sai do nome lido no alto da lista, comparado com casa
    e fora; sem como decidir, o time 1 (o que abre primeiro) e a casa.
    """
    resumo = json.loads((pasta / "jogadores.json").read_text(encoding="utf-8"))
    casa = casa or resumo.get("casa")
    fora = fora or resumo.get("fora")
    resultado = {"casa": [], "fora": []}
    for t in resumo.get("times", []):
        fotos = [pasta / f for f in t["fotos"] if (pasta / f).exists()]
        if not fotos:
            continue
        nome, lista = ler_time(ocr, fotos, avisos, f"time {t['numero']}")
        lado = "casa" if t["numero"] == 1 else "fora"
        for candidato, time in (("casa", casa), ("fora", fora)):
            if time and nome and (times.normalizar(time) in nome
                                  or nome in times.normalizar(time)):
                lado = candidato
        if resultado[lado]:
            avisos.add(f"jogadores: os dois times foram lidos como {lado}")
            lado = "fora" if lado == "casa" else "casa"
        resultado[lado] = lista
    for lado, time in (("casa", casa), ("fora", fora)):
        if not resultado[lado]:
            avisos.add(f"jogadores: sem estatisticas da {lado}")
            continue
        elenco = ee.elenco_do_time(time)
        if elenco:
            for j in resultado[lado]:
                if j["jogador"]:
                    j["jogador"] = ee.nome_do_elenco(j["jogador"], elenco) or j["jogador"]
    return resultado


def pasta_do_video(video: Path, gravado_em: str):
    """A pasta das fotos de um video: Jogadores/<nome do video> <data>.

    O video pode ter sido movido para Enviados/: a pasta Jogadores fica na
    raiz da pasta de videos. A data (do arquivo) e a chave, e nao o nome.
    """
    from datetime import datetime
    data = datetime.fromisoformat(gravado_em).strftime("%Y-%m-%d %H.%M.%S")
    raiz = Path(ee.PASTA_VIDEOS) / "Jogadores"
    if not raiz.is_dir():
        return None
    candidatas = [p for p in raiz.iterdir() if p.is_dir() and p.name.endswith(data)]
    return candidatas[0] if candidatas else None


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    pasta = Path(sys.argv[1])
    avisos = ee.Avisos()
    resultado = ler_pasta(pasta, ee.OCR(), avisos)
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    for a in avisos.lista:
        print("aviso:", a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
