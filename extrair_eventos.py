"""
extrair_eventos.py  --  Auto_PES21

Le o FINAL de cada video de partida (a tela "Fim de jogo") e salva, ao lado
do video, um .json com placar, eventos, notas dos jogadores e estatisticas.

E uma automacao separada do loop de gravacao (rodar_jogos.py): roda depois,
sobre os videos ja gravados, e nao mexe no jogo. Roda 100% local, sem API:
a leitura e feita pelo OCR que ja vem no Windows.

Como funciona:
  1. O ffmpeg decodifica so os ultimos segundos do video.
  2. So ficam os quadros com a barra de botoes do "Fim de jogo" (Destaques /
     Registro individual / Jogar novamente...) e que estao PARADOS (o meio
     das transicoes de aba e da rolagem sai borrado). Quadros iguais seguidos
     formam uma "tela".
  3. Cada tela e lida pelo OCR varias vezes (imagem original e binarizada,
     em escalas diferentes) e em varios quadros. O resultado final de cada
     campo e a VOTACAO dessas leituras: um erro isolado do OCR perde.
  4. Numeros curtos (placar, estatisticas, notas, minutos) o OCR do Windows
     nao le sozinhos, entao cada um e recortado e colado numa "linha falsa"
     entre pedacos de texto que ele le bem (ver ler_pecas).
  5. Os icones da linha do tempo sao reconhecidos pela COR (bola branca,
     triangulo azul/verde/vermelho, cartao).
  6. Monta os eventos (pareia substituicoes, liga assistencia ao gol),
     normaliza os times com times.py, troca cada nome de jogador pelo do
     elenco do time na base do PES do site (o OCR erra letra que nao existe
     em portugues: "Č", "ć", "ń") e confere: gols nos eventos TEM que
     bater com o placar. Se algo nao bate ou ficou ilegivel, o .json sai com
     "status": "revisar" e o motivo em "avisos". Nada e inventado: campo
     ilegivel ou empatado na votacao vira null.

Precisa do OCR do Windows com o idioma Portugues (vem no Windows 10/11 em
portugues) e destes pacotes (pequenos, so a "ponte" Python -> Windows):
  pip install winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections

Uso:
  python extrair_eventos.py                 -> todo video que ainda nao tem .json
  python extrair_eventos.py "arquivo.mp4"   -> so esse (sobrescreve)
  python extrair_eventos.py --forcar        -> refaz todos
  python extrair_eventos.py "arquivo.mp4" --salvar-quadros
                                            -> tambem grava as telas usadas em
                                               diagnostico_eventos/
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

from caminhos import PASTA_VIDEOS, BASE_JOGADORES   # definidas em caminhos.ini
EXTENSOES_VIDEO = (".mp4", ".mkv", ".mov", ".avi")

# Correcao dos nomes pelo elenco (base_jogadores no caminhos.ini). O OCR em
# portugues nao conhece letras como "Č" e "ć" e troca por outra ("Petr Čech"
# saia "Petrbech", "Vidić" saia "Vidié"). O nome lido vira o do elenco do
# time mais parecido com ele. Medido nos 5 primeiros jogos: nome errado
# fica a 0.88-0.93 do certo, e o 2o mais parecido no maximo a 0.46.
SEMELHANCA_MINIMA_NOME = 0.75
FOLGA_MINIMA_NOME = 0.15      # do mais parecido para o 2o: senao, na duvida, nao troca
# Time do times.py com outro nome na base, quando o "comeca igual" de
# elenco_do_time nao resolve sozinho ("Sport" tambem casa com Sporting CP...).
NOME_NA_BASE = {"Sport": "Sport Recife"}

# Quanto do final do video olhar. No video de referencia a tela "Fim de jogo"
# com os botoes ocupa so os ultimos ~15s (antes disso vem o replay dos
# melhores momentos e uma tela verde de estatisticas). 90s da folga para o
# loop demorar mais em alguma aba; o custo e so decodificar mais video.
SEGUNDOS_DO_FINAL = 90

# Quadros por segundo tirados desse trecho. A aba "Pontuacao dos jogadores"
# fica na tela so ~1s; com 4 por segundo ela sempre cai em varios quadros.
QUADROS_POR_SEGUNDO = 4

# Barra de botoes do "Fim de jogo", em fracao da tela (vale em 720p e 1080p).
# Os botoes sao cinza-claro; no replay e no campo essa faixa e grama/placa.
# Medido no video de referencia: 83% de pixels claros com o painel, no
# maximo 14% sem ele. 50% separa com folga.
REGIAO_BARRA = (0.06, 0.77, 0.94, 0.85)   # (esq, topo, dir, baixo)
LIMIAR_CLARO = 190                        # 0-255: o que conta como "claro"
FRACAO_MINIMA_BARRA = 0.50

# Painel central (placar + aba atual), em fracao da tela. O recorte e sempre
# redimensionado para PAINEL_BASE, o tamanho dele em 720p, e todas as
# coordenadas de LAYOUT abaixo sao nesse tamanho.
REGIAO_PAINEL = (0.20, 0.02, 0.80, 0.745)
PAINEL_BASE = (768, 522)

# Quando dois quadros seguidos sao "iguais". O painel e semitransparente e o
# estadio atras continua se mexendo, entao nunca da diferenca zero. Medido:
# tela parada muda ~0.1% dos pixels; troca de aba ou rolagem, 4% a 37%.
LIMIAR_PIXEL_MUDOU = 40      # diferenca de cinza para um pixel "mudar"
FRACAO_QUADRO_MUDOU = 0.01

# Quantos quadros de cada tela parada entram na votacao. Mais que isso so
# gasta tempo: sao quadros quase identicos.
QUADROS_POR_TELA = 3

# ---- OCR ----
IDIOMA_OCR = "pt-BR"

# Binarizacao: o texto do painel e branco; o fundo e azul-escuro com o
# estadio aparecendo atras. Fica so o que e claro E sem cor (branco/cinza),
# o que apaga as placas coloridas do estadio que confundiam o OCR
# ("Ronaldo" saia "aldo", "10" saia "0").
LIMIAR_TEXTO = 150           # canal mais escuro do pixel acima disto
SATURACAO_TEXTO = 60         # e diferenca entre canais abaixo disto

# Passadas de OCR na tela inteira: (binarizar?, escala). Cada uma erra em
# lugares diferentes (a original acerta acento maiusculo, "Éric"; a
# binarizada acerta o que o fundo atrapalha) e a votacao junta o melhor.
PASSADAS_LINHAS = [(False, 2), (True, 2), (True, 3)]

# Alturas (px) em que cada numero curto e colado na linha falsa. Medido: o
# OCR do Windows acerta em algumas alturas e nao le nada em outras, mas
# quase nunca le errado; varias alturas + votacao cobrem isso.
ALTURAS_PECA = (48, 64, 80)

# ---- LAYOUT (coordenadas em PAINEL_BASE, medidas no video de referencia) ----
CENTRO_X = 384                            # linha do tempo e centro do painel
CAIXA_TITULO_FIM = (300, 28, 470, 62)     # texto "Fim de jogo" (separador)
CAIXA_PLACAR_CASA = (225, 70, 325, 135)
CAIXA_PLACAR_FORA = (445, 70, 545, 135)
FAIXA_Y_NOMES_TIMES = (135, 160)          # nomes dos times sob os escudos
FAIXA_Y_TITULO_ABA = (175, 205)           # "Eventos da partida" etc.

# Aba de estatisticas: valores ao lado de cada rotulo (rotulo no centro).
X_VALOR_CASA = (60, 225)
X_VALOR_FORA = (545, 715)
# Mancha de texto menor que isto (px) nos valores e sujeira do estadio, nao
# algarismo (ver sem_pontos_soltos).
MANCHA_MINIMA_ESTATISTICA = 8

# Aba de notas: colunas de cada lado (numero, inicio do nome, nota, estrela).
NOTAS_X_NUMERO = {"casa": (26, 66), "fora": (408, 450)}
NOTAS_X_INICIO_NOME = {"casa": (25, 100), "fora": (410, 475)}
NOTAS_X_NOTA = {"casa": (282, 334), "fora": (664, 716)}
NOTAS_X_ESTRELA = {"casa": (334, 362), "fora": (708, 740)}
# Quem entrou no fim fica com "-" no lugar da nota. O OCR nao le o traco, mas
# ele e baixo: recortado justo da 6 px de altura, um algarismo da 17.
ALTURA_MAXIMA_TRACO = 9

# Aba de eventos: area visivel da lista (abaixo do titulo da aba) e onde fica
# o icone de cada lado, em relacao a CENTRO_X.
EVENTOS_Y_VISIVEL = (212, 516)
ICONE_DX = {"casa": (-82, -56), "fora": (54, 82)}
# O nome do evento encosta no icone: a casa termina em x ~283-298 e a fora
# comeca em ~467-482 (5 jogos medidos). Texto cuja borda do lado do icone
# fica mais longe do centro que isto e letreiro do estadio atras do painel
# ("BRASILEIRAO" lido como "eirao" em x 524-539, Coritiba x Flamengo) ou o
# pedaco de fora de um nome partido pelo OCR ("Juan Roman" | "Riquelme").
NOME_DX_MAX = 115
# Recorte do minuto dentro da bolha, relativo ao centro dela. O anel fica a
# +-20 px do centro e "90+4'" ocupa -15..+15; o recorte antigo (+-13) comia o
# "9", que virava "7" ("70+4"), e "45+3" nem era lido. Na vertical o texto
# vai de -2.5 a +5.5 do centro achado; o anel nao entra nesta faixa.
MINUTO_DX = (-17, 18)
MINUTO_DY = (-4, 7)
DISTANCIA_MAX_BOLHA = 45      # texto mais longe que isto de uma bolha: orfao
# Um evento de verdade e lido muitas vezes (varios quadros, varias passadas
# do OCR, varias telas): no video da Supercopa, 20 a 80 leituras cada. Um
# quadro pego no meio da rolagem gera leituras soltas em posicao torta
# ("santos" aos 21', um segundo "Hulk"). Menos leituras que isto = ruido.
LEITURAS_MINIMAS_EVENTO = 3

# Cores dos icones (medidas no video de referencia, RGB):
#   entrou = verde (0,130,60)   saiu = vermelho (200,40,40)
#   assistencia = azul (0,90,180)   gol = bola branca
#   melhor em campo = estrela ciano (0,130,150): g ~ b, diferente do azul
PIXELS_MINIMOS_ICONE = 12
# A estrela e um disco cheio de ~18x18 px: ~200 pixels ciano em 5 videos. A
# placa azul da Unimed atras da linha (Felipe, Inter x Sport) dava 14 e
# virava um segundo melhor em campo.
PIXELS_MINIMOS_ESTRELA = 80

PASTA_DIAGNOSTICO = "diagnostico_eventos"

# ==========================================================================

import argparse
import asyncio
import gzip
import json
import unicodedata
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageOps

import times


# --------------------------------------------------------------------------
# Video -> telas paradas do "Fim de jogo"
# --------------------------------------------------------------------------

def info_video(caminho: Path):
    """(largura, altura, duracao em segundos), lidos do cabecalho pelo ffmpeg."""
    saida = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(caminho)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stderr
    dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", saida)
    res = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", saida)
    if not dur or not res:
        raise RuntimeError("ffmpeg nao conseguiu ler o video")
    h, m, s = dur.groups()
    return int(res.group(1)), int(res.group(2)), int(h) * 3600 + int(m) * 60 + float(s)


def quadros_do_final(caminho: Path):
    """Gera (segundo_no_video, Image RGB) dos ultimos SEGUNDOS_DO_FINAL.

    Os quadros vem por um pipe em formato cru, em vez de PNGs numa pasta
    temporaria: sao centenas de quadros e so uns poucos interessam.
    """
    largura, altura, duracao = info_video(caminho)
    inicio = max(0.0, duracao - SEGUNDOS_DO_FINAL)
    comando = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error",
        "-ss", f"{inicio:.2f}", "-i", str(caminho),
        "-vf", f"fps={QUADROS_POR_SEGUNDO}",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    tamanho = largura * altura * 3
    proc = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        n = 0
        while True:
            dados = proc.stdout.read(tamanho)
            if len(dados) < tamanho:
                break
            yield inicio + n / QUADROS_POR_SEGUNDO, Image.frombytes("RGB", (largura, altura), dados)
            n += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def recortar_fracao(img: Image.Image, regiao) -> Image.Image:
    w, h = img.size
    e, t, d, b = regiao
    return img.crop((int(w * e), int(h * t), int(w * d), int(h * b)))


def tem_painel_fim_de_jogo(img: Image.Image) -> bool:
    # Reduz antes de contar: a decisao e grosseira e isso roda em centenas
    # de quadros.
    faixa = recortar_fracao(img, REGIAO_BARRA).convert("L").resize((220, 16))
    claros = sum(faixa.histogram()[LIMIAR_CLARO + 1:])
    return claros / (faixa.width * faixa.height) >= FRACAO_MINIMA_BARRA


def miniatura(painel: Image.Image) -> Image.Image:
    return painel.convert("L").resize((192, 128))


def mudou(a: Image.Image, b: Image.Image) -> bool:
    dif = ImageChops.difference(a, b)
    mudados = sum(dif.histogram()[LIMIAR_PIXEL_MUDOU + 1:])
    return mudados / (dif.width * dif.height) >= FRACAO_QUADRO_MUDOU


@dataclass
class Tela:
    """Uma tela parada: varios quadros quase identicos, em ordem no video."""
    quadros: list = field(default_factory=list)     # (segundo, painel)
    aba: str = None                                 # estatisticas/pontuacao/eventos
    linhas: list = field(default_factory=list)      # [ [Linha...] por quadro ]


def selecionar_telas(caminho: Path) -> list:
    """Agrupa os quadros parados do "Fim de jogo" em telas.

    Um quadro so e aceito se for igual ao anterior (tela assentada): isso
    descarta o meio das transicoes de aba e da rolagem. Quadros aceitos
    iguais ao primeiro da tela atual entram nela; senao abrem tela nova.
    """
    telas = []
    anterior = None
    for segundo, img in quadros_do_final(caminho):
        if not tem_painel_fim_de_jogo(img):
            anterior = None
            continue
        painel = recortar_fracao(img, REGIAO_PAINEL)
        if painel.size != PAINEL_BASE:
            painel = painel.resize(PAINEL_BASE, Image.LANCZOS)
        mini = miniatura(painel)
        parado = anterior is not None and not mudou(mini, anterior)
        anterior = mini
        if not parado:
            continue
        if telas and not mudou(mini, telas[-1].mini):
            telas[-1].quadros.append((segundo, painel))
        else:
            tela = Tela(quadros=[(segundo, painel)])
            tela.mini = mini
            telas.append(tela)

    for tela in telas:
        q = tela.quadros
        if len(q) > QUADROS_POR_TELA:
            passo = (len(q) - 1) / (QUADROS_POR_TELA - 1)
            tela.quadros = [q[round(i * passo)] for i in range(QUADROS_POR_TELA)]
    return telas


# --------------------------------------------------------------------------
# OCR do Windows
# --------------------------------------------------------------------------

@dataclass
class Caixa:
    texto: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2

    @property
    def cy(self):
        return (self.y0 + self.y1) / 2


@dataclass
class Linha(Caixa):
    palavras: list = field(default_factory=list)
    binaria: bool = False      # lida na imagem binarizada (posicao confiavel)


def binarizar(img: Image.Image) -> Image.Image:
    """Texto branco do painel -> preto sobre branco, o resto some."""
    r, g, b = img.convert("RGB").split()
    menor = ImageChops.darker(ImageChops.darker(r, g), b)
    maior = ImageChops.lighter(ImageChops.lighter(r, g), b)
    claro = menor.point(lambda v: 255 if v > LIMIAR_TEXTO else 0)
    sem_cor = ImageChops.subtract(maior, menor).point(lambda v: 255 if v < SATURACAO_TEXTO else 0)
    return ImageOps.invert(ImageChops.multiply(claro, sem_cor))


class OCR:
    def __init__(self):
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.storage.streams import DataWriter
        except ImportError:
            raise RuntimeError("faltam os pacotes do OCR do Windows (ver o topo deste arquivo)")
        self._bitmap = SoftwareBitmap
        self._rgba8 = BitmapPixelFormat.RGBA8
        self._writer = DataWriter
        self.motor = OcrEngine.try_create_from_language(Language(IDIOMA_OCR))
        if self.motor is None:
            raise RuntimeError(f"o OCR do Windows nao tem o idioma {IDIOMA_OCR} instalado")
        self.loop = asyncio.new_event_loop()

    async def _aguardar(self, operacao):
        return await operacao

    def ler(self, img: Image.Image, escala: float = 1.0) -> list:
        """Linhas de texto, com coordenadas divididas por `escala` (isto e,
        de volta ao tamanho de antes de ampliar)."""
        rgba = img.convert("RGBA")
        w = self._writer()
        w.write_bytes(rgba.tobytes())
        bmp = self._bitmap.create_copy_from_buffer(
            w.detach_buffer(), self._rgba8, rgba.width, rgba.height)
        resultado = self.loop.run_until_complete(self._aguardar(self.motor.recognize_async(bmp)))
        linhas = []
        for ln in resultado.lines:
            palavras = [Caixa(p.text,
                              p.bounding_rect.x / escala, p.bounding_rect.y / escala,
                              (p.bounding_rect.x + p.bounding_rect.width) / escala,
                              (p.bounding_rect.y + p.bounding_rect.height) / escala)
                        for p in ln.words]
            if not palavras:
                continue
            linhas.append(Linha(ln.text,
                                min(p.x0 for p in palavras), min(p.y0 for p in palavras),
                                max(p.x1 for p in palavras), max(p.y1 for p in palavras),
                                palavras))
        return linhas


def ampliar(img: Image.Image, escala: float) -> Image.Image:
    return img.resize((round(img.width * escala), round(img.height * escala)), Image.LANCZOS)


def ler_linhas(ocr: OCR, painel: Image.Image) -> list:
    """Todas as passadas de OCR do painel inteiro, juntas numa lista."""
    linhas = []
    for binario, escala in PASSADAS_LINHAS:
        img = ampliar(painel, escala)
        if binario:
            img = binarizar(img)
        for ln in ocr.ler(img, escala):
            ln.binaria = binario
            linhas.append(ln)
    return linhas


def justo(img: Image.Image, margem: int = 2):
    """Recorte so em volta do texto (branco) da imagem; None se nao ha texto."""
    caixa = ImageOps.invert(binarizar(img)).getbbox()
    if caixa is None:
        return None
    x0, y0, x1, y1 = caixa
    return img.crop((max(0, x0 - margem), max(0, y0 - margem),
                     min(img.width, x1 + margem), min(img.height, y1 + margem)))


def sem_pontos_soltos(img: Image.Image, minimo: int) -> Image.Image:
    """Apaga manchas de texto menores que `minimo` pixels (8-vizinhanca).

    Uma placa clara do estadio atras do painel deixa pontinhos brancos que a
    binarizacao nao tira. Grudado no "8" de "81 (68)", um ponto de 5 px fez
    o OCR perder o "(68)" em todas as leituras. Algarismo, "(" e "%" tem 12+
    px; o ponto decimal da nota tem 3 - por isso isto NAO serve para notas.
    """
    img = img.copy()
    bw = binarizar(img).load()
    px = img.load()
    w, h = img.size
    vistos = set()
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
                        if 0 <= na < w and 0 <= nb < h and (na, nb) not in vistos \
                                and bw[na, nb] == 0:
                            vistos.add((na, nb))
                            pilha.append((na, nb))
            if len(mancha) < minimo:
                for p in mancha:
                    px[p] = (0, 0, 0)
    return img


def ler_pecas(ocr: OCR, pecas: list, separador: Image.Image) -> list:
    """Le recortes pequenos (numeros curtos) e devolve, para cada um, a lista
    de textos lidos (um por altura em que deu para ler).

    O OCR do Windows nao le um "0" ou "83'" sozinho numa imagem: ele precisa
    de uma linha de texto. Entao cada recorte e colado numa grade, cada um
    entre copias do texto "Fim de jogo" do proprio painel, que ele le sempre.
    Cada palavra lida e atribuida ao recorte cuja posicao na grade a contem.
    """
    lidos = [[] for _ in pecas]
    # Cada recorte e cortado justo em volta do texto: o recorte bruto e bem
    # maior que o numero, e colado assim o numero saia minusculo perto do
    # separador, com buracos enormes em volta - e o OCR nao lia.
    justas = [(i, justo(p)) for i, p in enumerate(pecas)]
    justas = [(i, p) for i, p in justas if p is not None]
    sep_justo = justo(separador)
    if not justas or sep_justo is None:
        return lidos
    por_linha = 4
    for altura in ALTURAS_PECA:
        # O separador tem letra com perna ("j", "g"); numero nao. O numero vai
        # na altura da maiuscula do separador, alinhado pelo topo.
        altura_num = round(altura * 0.72)

        def no_tamanho(img, h):
            return img.resize((max(1, round(img.width * h / img.height)), h), Image.LANCZOS)
        sep = no_tamanho(sep_justo, altura)
        espaco = altura // 2
        fileiras = [justas[i:i + por_linha] for i in range(0, len(justas), por_linha)]
        largura = max(sep.width + sum(no_tamanho(p, altura_num).width + sep.width + 2 * espaco
                                      for _, p in f) for f in fileiras) + 2 * espaco
        grade = Image.new("RGB", (largura, len(fileiras) * altura * 2 + altura), (0, 0, 0))
        caixas = []
        for n, fileira in enumerate(fileiras):
            y = altura // 2 + n * altura * 2
            x = espaco
            grade.paste(sep, (x, y))
            x += sep.width + espaco
            for i, p in fileira:
                p = no_tamanho(p, altura_num)
                grade.paste(p, (x, y))
                caixas.append((i, x - espaco / 2, y, x + p.width + espaco / 2, y + altura))
                x += p.width + espaco
                grade.paste(sep, (x, y))
                x += sep.width + espaco
        textos = [[] for _ in pecas]
        for linha in ocr.ler(binarizar(grade)):
            for pal in linha.palavras:
                for i, x0, y0, x1, y1 in caixas:
                    if x0 <= pal.cx <= x1 and y0 <= pal.cy <= y1:
                        textos[i].append(pal)
                        break
        for i, pals in enumerate(textos):
            if pals:
                lidos[i].append(" ".join(p.texto for p in sorted(pals, key=lambda p: p.x0)))
    return lidos


# --------------------------------------------------------------------------
# Votacao e interpretacao dos textos lidos
# --------------------------------------------------------------------------

class Avisos:
    """Lista de avisos + se algum deles exige revisao manual."""

    def __init__(self):
        self.lista = []
        self.revisar = False

    def add(self, texto: str, revisar: bool = True):
        if texto not in self.lista:
            self.lista.append(texto)
        self.revisar = self.revisar or revisar


def votar(valores):
    """(vencedor, problema). Sem leitura ou empate -> (None, motivo): nesse
    caso o campo fica null, em vez de escolher um no chute."""
    valores = [v for v in valores if v is not None]
    if not valores:
        return None, "ilegivel"
    ranking = Counter(valores).most_common(2)
    if len(ranking) > 1 and ranking[0][1] == ranking[1][1]:
        return None, f"leitura em duvida ({ranking[0][0]} ou {ranking[1][0]})"
    return ranking[0][0], None


# Letras que o OCR costuma trocar por digitos, so dentro de campos numericos.
TROCAS_DIGITO = str.maketrans({"o": "0", "O": "0", "Q": "0", "D": "0", "l": "1", "I": "1",
                               "i": "1", "|": "1", "!": "1", "S": "5", "s": "5", "B": "8",
                               "Z": "2", "z": "2", "[": "(", "{": "(", "]": ")", "}": ")"})


def ler_inteiro(texto):
    t = texto.translate(TROCAS_DIGITO).replace(" ", "")
    return int(t) if re.fullmatch(r"\d{1,3}", t) else None


def ler_posse(texto):
    t = texto.translate(TROCAS_DIGITO).replace(" ", "")
    m = re.fullmatch(r"(\d{1,3})%?", t)
    return int(m.group(1)) if m and int(m.group(1)) <= 100 else None


def ler_par(texto):
    """'101 (91)' -> (101, 91). O segundo nunca e maior que o primeiro
    (chutes a gol <= chutes etc.), o que tambem desfaz o erro comum de ler o
    "(" como "1": '94 180)' -> (94, 80)."""
    t = texto.translate(TROCAS_DIGITO)
    m = re.fullmatch(r"\s*(\d{1,3})\s*\(\s*(\d{1,3})\s*\)?\s*", t)
    if m and int(m.group(2)) <= int(m.group(1)):
        return int(m.group(1)), int(m.group(2))
    m = re.fullmatch(r"\s*(\d{1,3})\s+1(\d{1,3})\s*\)\s*", t)
    if m and int(m.group(2)) <= int(m.group(1)):
        return int(m.group(1)), int(m.group(2))
    return None


def ler_nota(texto):
    t = texto.translate(TROCAS_DIGITO).replace(" ", "").replace(",", ".")
    m = re.fullmatch(r"(\d{1,2})\.(\d)", t)
    return float(t) if m and float(t) <= 10 else None


def ler_minuto(texto):
    """"83'" -> "83"; "90+2'" -> "90+2"."""
    t = texto.translate(TROCAS_DIGITO).replace(" ", "").rstrip("'`´’")
    return t if re.fullmatch(r"\d{1,3}(\+\d{1,2})?", t) else None


# Palavras minusculas que sao parte de nome, nao pedaco de palavra quebrada.
PARTICULAS = {"de", "da", "do", "dos", "das", "e", "van", "von", "der", "den", "di",
              "del", "la", "le", "dal", "ter", "ten", "bin", "al", "y"}


def limpar_nome(texto):
    """Tira lixo das pontas (o icone da bola as vezes vira "@") e cola pedacos
    que o OCR separou: "Ar jen Robben" -> "Arjen Robben". Um pedaco comecando
    com minuscula (que nao seja "de", "van"...) e continuacao da palavra
    anterior: nome de jogador comeca com maiuscula."""
    palavras = re.findall(r"[^\s]+", texto)
    limpas = []
    for p in palavras:
        p = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ.]+$", "", p)
        if not p or p.isdigit():
            continue
        if limpas and p[0].islower() and p.lower() not in PARTICULAS:
            limpas[-1] += p
        else:
            limpas.append(p)
    return " ".join(limpas) or None


def chave_nome(nome):
    return times.normalizar(nome).replace(" ", "")


# Letras finas que o OCR confunde entre si em nome (chave ja minuscula).
TROCAS_LETRA = str.maketrans({"j": "i", "l": "i", "1": "i", "0": "o"})


def votar_nome(candidatos):
    """Vota pela grafia sem acento/espaco; dentro da vencedora, a grafia mais
    lida, e no empate a com mais acentos (o OCR perde acento, nao inventa)."""
    nomes = [n for n in (limpar_nome(c) for c in candidatos if c) if n]
    if not nomes:
        return None, "ilegivel"
    chave, problema = votar([chave_nome(n) for n in nomes])
    if chave is None:
        return None, problema
    grafias = Counter(n for n in nomes if chave_nome(n) == chave)
    melhor = max(grafias, key=lambda n: (grafias[n], sum(not c.isascii() for c in n)))
    return melhor, None


# --------------------------------------------------------------------------
# Leitura de cada parte da tela
# --------------------------------------------------------------------------

def normalizado(texto):
    return times.normalizar(texto).replace(" ", "")


def aba_da_tela(linhas) -> str:
    for ln in linhas:
        if FAIXA_Y_TITULO_ABA[0] <= ln.cy <= FAIXA_Y_TITULO_ABA[1]:
            t = normalizado(ln.texto)
            if "pontua" in t:
                return "pontuacao"
            if "estat" in t:
                return "estatisticas"
            if "evento" in t:
                return "eventos"
    return None


def ler_cabecalho(ocr, telas, avisos: Avisos):
    """Times e placar: aparecem em todas as telas, entao votam todas."""
    nomes = {"casa": [], "fora": []}
    placar = {"casa": [], "fora": []}
    for tela in telas:
        for (_, painel), linhas in zip(tela.quadros, tela.linhas):
            for ln in linhas:
                if FAIXA_Y_NOMES_TIMES[0] <= ln.cy <= FAIXA_Y_NOMES_TIMES[1]:
                    nomes["casa" if ln.cx < CENTRO_X else "fora"].append(ln.texto)
            lidos = ler_pecas(ocr, [painel.crop(CAIXA_PLACAR_CASA), painel.crop(CAIXA_PLACAR_FORA)],
                              painel.crop(CAIXA_TITULO_FIM))
            placar["casa"] += [ler_inteiro(t) for t in lidos[0]]
            placar["fora"] += [ler_inteiro(t) for t in lidos[1]]

    resultado = {}
    for lado in ("casa", "fora"):
        nome, problema = votar([n.strip() for n in nomes[lado]])
        if problema:
            avisos.add(f"nome do time da {lado}: {problema}")
        gols, problema = votar(placar[lado])
        if problema:
            avisos.add(f"placar da {lado}: {problema}")
        resultado[lado] = (nome, gols)
    return resultado


ROTULOS_ESTATISTICAS = [
    ("posse", "posse"), ("chutes", "chutes"), ("faltas", "faltas"),
    ("escanteio", "escanteios"), ("cobranc", "cobrancas_de_falta"), ("passes", "passes"),
    ("cruzamento", "cruzamentos"), ("interc", "interceptacoes"),
    ("desarme", "desarmes"), ("defesa", "defesas"),
]
# Linhas da tabela com dois numeros "N (M)": o segundo vai para outro campo.
PARES_ESTATISTICAS = {"chutes": "chutes_a_gol", "faltas": "impedimentos",
                      "passes": "passes_certos"}
CAMPOS_ESTATISTICAS = ["posse", "chutes", "chutes_a_gol", "faltas", "impedimentos",
                       "escanteios", "cobrancas_de_falta", "passes", "passes_certos",
                       "cruzamentos", "interceptacoes", "desarmes", "defesas"]


def metades_do_par(peca: Image.Image):
    """'0 (0)' -> recortes '0' e '(0)', cortando no maior vao entre colunas
    com texto (o espaco antes do parentese). O OCR do Windows descarta o
    "0 (0)" inteiro mesmo na grade, mas le as duas metades."""
    img = justo(peca)
    if img is None:
        return None
    bw = binarizar(img).load()
    com_texto = [any(bw[x, y] == 0 for y in range(img.height)) for x in range(img.width)]
    vaos, inicio = [], None
    for x, tem in enumerate(com_texto):
        if not tem and inicio is None:
            inicio = x
        elif tem and inicio is not None:
            vaos.append((x - inicio, inicio, x))
            inicio = None
    vaos = [v for v in vaos if v[1] > 0]       # margem da esquerda nao e vao
    if not vaos:
        return None
    _, x0, x1 = max(vaos)
    return img.crop((0, 0, x0, img.height)), img.crop((x1, 0, img.width, img.height))


def ler_estatisticas(ocr, telas, avisos: Avisos):
    votos = {(c, l): [] for c in CAMPOS_ESTATISTICAS for l in ("casa", "fora")}
    for tela in telas:
        for (_, painel), linhas in zip(tela.quadros, tela.linhas):
            # Acha a altura de cada rotulo (coluna do meio) pelo texto.
            alturas = defaultdict(list)
            for ln in linhas:
                if abs(ln.cx - CENTRO_X) > 120 or ln.cy < FAIXA_Y_TITULO_ABA[1]:
                    continue
                t = normalizado(ln.texto)
                for prefixo, campo in ROTULOS_ESTATISTICAS:
                    if t.startswith(prefixo):
                        alturas[campo].append(ln.cy)
            campos = list(alturas)
            ys = [statistics.median(alturas[c]) for c in campos]
            pecas = []
            for y in ys:
                for x0, x1 in (X_VALOR_CASA, X_VALOR_FORA):
                    pecas.append(sem_pontos_soltos(
                        painel.crop((x0, round(y - 12), x1, round(y + 12))), MANCHA_MINIMA_ESTATISTICA))
            separador = painel.crop(CAIXA_TITULO_FIM)
            lidos = ler_pecas(ocr, pecas, separador)
            for i, campo in enumerate(campos):
                for j, lado in enumerate(("casa", "fora")):
                    textos = lidos[2 * i + j]
                    if campo in PARES_ESTATISTICAS and not any(ler_par(t) for t in textos):
                        metades = metades_do_par(pecas[2 * i + j])
                        if metades:
                            esq, dir_ = ler_pecas(ocr, list(metades), separador)
                            textos = [f"{a} {b}" for a, b in zip(esq, dir_)]
                    for texto in textos:
                        if campo in PARES_ESTATISTICAS:
                            par = ler_par(texto)
                            if par:
                                votos[(campo, lado)].append(par[0])
                                votos[(PARES_ESTATISTICAS[campo], lado)].append(par[1])
                        elif campo == "posse":
                            votos[(campo, lado)].append(ler_posse(texto))
                        else:
                            votos[(campo, lado)].append(ler_inteiro(texto))

    est = {}
    for campo in CAMPOS_ESTATISTICAS:
        est[campo] = {}
        problemas = {}
        for lado in ("casa", "fora"):
            est[campo][lado], problemas[lado] = votar(votos[(campo, lado)])
        # Posse soma sempre 100%: um lado ilegivel sai do outro, sem chute.
        if campo == "posse":
            for lado, outro in (("casa", "fora"), ("fora", "casa")):
                if est[campo][lado] is None and est[campo][outro] is not None:
                    est[campo][lado] = 100 - est[campo][outro]
                    problemas[lado] = None
        for lado, problema in problemas.items():
            if problema:
                avisos.add(f"estatistica {campo} ({lado}): {problema}")
    return est


def contar_pixels(painel, caixa, teste):
    regiao = painel.crop(tuple(round(v) for v in caixa)).convert("RGB")
    px = regiao.load()
    return [(x, y) for y in range(regiao.height) for x in range(regiao.width) if teste(*px[x, y])]


def eh_ciano(r, g, b):
    return g >= 100 and b >= 100 and abs(g - b) <= 50 and r <= 80


def agrupar(valores, tolerancia):
    """Agrupa numeros proximos: [100, 103, 150] -> [[100, 103], [150]]."""
    grupos = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return grupos


def ler_notas(ocr, telas, avisos: Avisos):
    """Uma lista por lado. A mesma linha em quadros da mesma tela esta na
    mesma altura, entao junta os votos por altura; entre telas (se a lista
    rolou), junta pelo nome."""
    jogadores = {"casa": {}, "fora": {}}      # chave do nome -> votos
    for tela in telas:
        for lado in ("casa", "fora"):
            x_ini = NOTAS_X_INICIO_NOME[lado]
            candidatas = [ln for linhas in tela.linhas for ln in linhas
                          if x_ini[0] <= ln.x0 <= x_ini[1] and ln.cy > FAIXA_Y_TITULO_ABA[1]]
            for grupo in agrupar([ln.cy for ln in candidatas], 8):
                y = statistics.median(grupo)
                nomes = [ln.texto for ln in candidatas if abs(ln.cy - y) <= 8]
                numeros, notas, estrelas, tracos = [], [], 0, 0
                for _, painel in tela.quadros:
                    xn, xo, xe = NOTAS_X_NUMERO[lado], NOTAS_X_NOTA[lado], NOTAS_X_ESTRELA[lado]
                    recorte_nota = painel.crop((xo[0], round(y - 12), xo[1], round(y + 12)))
                    lidos = ler_pecas(ocr, [painel.crop((xn[0], round(y - 12), xn[1], round(y + 12))),
                                            recorte_nota],
                                      painel.crop(CAIXA_TITULO_FIM))
                    numeros += [ler_inteiro(t) for t in lidos[0]]
                    notas += [ler_nota(t) for t in lidos[1]]
                    nota_justa = justo(recorte_nota)
                    tracos += nota_justa is not None and nota_justa.height <= ALTURA_MAXIMA_TRACO
                    ciano = contar_pixels(painel, (xe[0], y - 10, xe[1], y + 10), eh_ciano)
                    estrelas += len(ciano) >= PIXELS_MINIMOS_ESTRELA
                nome, _ = votar_nome(nomes)
                if nome is None:
                    # Nome curto sozinho ("Pepe") o OCR do painel inteiro nao
                    # le; colado entre os "Fim de jogo" da grade, le.
                    x0, x1 = NOTAS_X_NUMERO[lado][1], NOTAS_X_NOTA[lado][0]
                    for _, painel in tela.quadros:
                        nomes += ler_pecas(ocr, [painel.crop((x0, round(y - 12), x1, round(y + 12)))],
                                           painel.crop(CAIXA_TITULO_FIM))[0]
                    nome, _ = votar_nome(nomes)
                chave = chave_nome(nome) if nome else f"?{tela.quadros[0][0]}:{y:.0f}"
                j = jogadores[lado].setdefault(chave, {"nomes": [], "numeros": [], "notas": [],
                                                       "estrela": 0, "tracos": 0, "quadros": 0})
                j["nomes"] += nomes
                j["numeros"] += numeros
                j["notas"] += notas
                j["estrela"] += estrelas
                j["tracos"] += tracos
                j["quadros"] += len(tela.quadros)

    # Linha cujo nome empatou numa tela ("Elano ou Etano", "Pepe" curto) vira
    # um jogador "?" a parte, e o mesmo jogador saia duas vezes. A camisa nao
    # se repete no time: "?" com o numero de um jogador com nome e ele.
    for lado in ("casa", "fora"):
        por_numero = {}
        for chave, j in jogadores[lado].items():
            numero, _ = votar(j["numeros"])
            if not chave.startswith("?") and numero is not None:
                por_numero.setdefault(numero, chave)
        for chave in [c for c in jogadores[lado] if c.startswith("?")]:
            numero, _ = votar(jogadores[lado][chave]["numeros"])
            if numero in por_numero:
                sem_nome = jogadores[lado].pop(chave)
                dono = jogadores[lado][por_numero[numero]]
                for campo in ("nomes", "numeros", "notas", "estrela", "tracos", "quadros"):
                    dono[campo] += sem_nome[campo]

    notas = {"casa": [], "fora": []}
    for lado in ("casa", "fora"):
        for j in jogadores[lado].values():
            nome, p_nome = votar_nome(j["nomes"])
            numero, p_num = votar(j["numeros"])
            nota, p_nota = votar(j["notas"])
            if nota is None and j["tracos"] * 2 > j["quadros"]:
                p_nota = None     # "-": entrou no fim, o jogo nao deu nota
            for campo, problema in (("nome", p_nome), ("numero", p_num), ("nota", p_nota)):
                if problema:
                    avisos.add(f"notas ({lado}), jogador {nome or '?'}: {campo} {problema}")
            notas[lado].append({"numero": numero, "jogador": nome, "nota": nota,
                                "melhor_em_campo": j["estrela"] * 2 > j["quadros"]})
    return notas


# ---- Eventos ----

def eh_verde(r, g, b):
    return g >= 100 and g - r >= 60 and g - b >= 25


def eh_vermelho(r, g, b):
    return r >= 150 and r - g >= 80 and r - b >= 80


def eh_azul(r, g, b):
    return b >= 140 and b - g >= 40 and b - r >= 100


def eh_amarelo(r, g, b):
    return r >= 180 and g >= 150 and b <= 100


def eh_branco(r, g, b):
    return min(r, g, b) >= 180 and max(r, g, b) - min(r, g, b) <= 40


def classificar_icone(painel, lado, y):
    dx0, dx1 = ICONE_DX[lado]
    caixa = (CENTRO_X + dx0, y - 9, CENTRO_X + dx1, y + 9)
    contagem = {nome: contar_pixels(painel, caixa, teste) for nome, teste in (
        ("entrou", eh_verde), ("vermelho", eh_vermelho), ("assistencia", eh_azul),
        ("cartao_amarelo", eh_amarelo), ("gol", eh_branco))}
    nome, pontos = max(contagem.items(), key=lambda kv: len(kv[1]))
    if len(pontos) < PIXELS_MINIMOS_ICONE:
        # Nada desenhado ao lado do texto: nao e evento (e.g. letreiro do
        # estadio aparecendo atras do painel). Algo desenhado mas de cor
        # desconhecida: icone novo (gol contra? outro cartao?).
        marcado = contar_pixels(painel, caixa, lambda r, g, b:
                                max(r, g, b) >= 120 and max(r, g, b) - min(r, g, b) >= 60)
        return "desconhecido" if len(marcado) >= PIXELS_MINIMOS_ICONE else None
    if nome == "vermelho":
        # Triangulo ocupa ~metade do retangulo em volta dele; cartao, quase todo.
        xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
        area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
        return "cartao_vermelho" if len(pontos) / area > 0.75 else "saiu"
    return nome


def altura_do_icone(painel, lado, cy):
    """Centro (y) do icone ao lado de uma linha cuja altura veio torta, ou
    None se nao ha icone perto. Busca so +-12 px: o icone da linha vizinha
    (24 px abaixo ou acima, na mesma bolha) nao entra."""
    dx0, dx1 = ICONE_DX[lado]
    topo = round(cy) - 12
    caixa = (CENTRO_X + dx0, topo, CENTRO_X + dx1, round(cy) + 12)
    pontos = max((contar_pixels(painel, caixa, teste) for teste in
                  (eh_verde, eh_vermelho, eh_azul, eh_amarelo, eh_branco)), key=len)
    if len(pontos) < PIXELS_MINIMOS_ICONE:
        return None
    return topo + statistics.median(y for _, y in pontos)


def achar_bolhas(painel):
    """Centros (y) das bolhas de minuto na linha do tempo.

    A bolha e um anel branco de ~44 px no centro. O teste: anel dos dois
    lados na altura do centro, e faixa branca larga ~20 px acima e abaixo
    (topo e base do anel). A linha vertical entre bolhas tem so 4 px de
    largura, e "Intervalo"/"Inicio" nao tem topo e base, entao nao passam.
    """
    bw = binarizar(painel).load()

    def preto(x, y):
        return bw[x, y] == 0

    def lados(y):
        return (any(preto(x, y) for x in range(CENTRO_X - 23, CENTRO_X - 16))
                and any(preto(x, y) for x in range(CENTRO_X + 16, CENTRO_X + 23)))

    def faixa_larga(y):
        return sum(preto(x, y) for x in range(CENTRO_X - 10, CENTRO_X + 10)) >= 14

    ys = []
    for y in range(EVENTOS_Y_VISIVEL[0] + 22, EVENTOS_Y_VISIVEL[1] - 22):
        if lados(y) and any(faixa_larga(y - d) for d in range(17, 23)) \
                and any(faixa_larga(y + d) for d in range(17, 23)):
            ys.append(y)
    return [statistics.median(g) for g in agrupar(ys, 3)]


MARCADORES = ("inicio", "intervalo", "fimdepartida")


def ordem_do_minuto(minuto):
    """'89' -> (89, 0); '90+2' -> (90, 2); ilegivel vai para o fim."""
    if minuto is None:
        return (999, 0)
    base, _, extra = minuto.partition("+")
    return (int(base), int(extra or 0))


def repeticoes_acima(bolhas, marcadores):
    """Para cada bolha (y, minuto), a posicao dela entre as bolhas do MESMO
    minuto - (periodo, n) - ou None se esta tela nao deixa saber.

    Pode haver duas bolhas 70' do mesmo lado (gol e, noutro lance, troca).
    Como os minutos so crescem, bolhas iguais ficam juntas: basta contar as
    iguais logo acima na tela. A conta so vale se a tela mostra onde a
    sequencia comeca - uma bolha de outro minuto, ou um marcador ("Inicio",
    "Intervalo"), acima dela. Se a sequencia encosta no topo da tela, pode
    haver mais iguais escondidas acima; outra tela, mais rolada, mostra.

    Marcador entre duas bolhas iguais tambem separa as sequencias: a troca
    feita no intervalo sai como 45', igual ao gol dos 45' do 1o tempo, com
    "Intervalo" entre as duas. Contadas juntas, a troca era a 2a bolha 45'
    numa tela e a 1a noutra (onde o gol ja tinha rolado para fora), e saia
    duplicada (Botafogo x Flamengo). Por isso o periodo: 1 = sequencia que
    comeca no "Intervalo", 0 = qualquer outra.

    marcadores: [(y, texto normalizado)].
    """
    def marcador_entre(cima, baixo):
        entre = [(y, nome) for y, nome in marcadores if cima < y < baixo]
        return max(entre)[1] if entre else None    # o mais perto da bolha de baixo

    resultado = []
    for i, (y, minuto) in enumerate(bolhas):
        if minuto is None:
            resultado.append(None)
            continue
        j = i - 1
        while (j >= 0 and bolhas[j][1] == minuto
               and marcador_entre(bolhas[j][0], bolhas[j + 1][0]) is None):
            j -= 1
        topo = bolhas[j + 1][0]
        limite = bolhas[j][0] if j >= 0 else float("-inf")
        marcador = marcador_entre(limite, topo)
        if marcador is None and not (j >= 0 and bolhas[j][1] is not None):
            resultado.append(None)
            continue
        resultado.append((1 if marcador == "intervalo" else 0, i - j - 1))
    return resultado


def ler_eventos(ocr, telas, avisos: Avisos):
    """Itens da linha do tempo, em ordem: (minuto, lado, icone, jogador).

    A lista rola entre telas, e o mesmo evento aparece em varias delas. Cada
    evento e identificado pelo que ele E, nao por onde esta na tela:
        (minuto da bolha, qual bolha desse minuto, lado,
         posicao da linha em relacao a bolha)
    Ex.: "Diego Ribas" e a 1a linha a esquerda da (1a) bolha 76'. Em qualquer
    tela em que ele apareca, a chave e a mesma, e as leituras dele votam
    juntas. Sem o "qual bolha", duas bolhas 70' do mesmo lado se fundiam e um
    dos eventos sumia (ver repeticoes_acima).

    Antes a juncao era geometrica: medir quanto a lista rolou entre uma tela
    e outra. Nao funciona - as bolhas sao iguais e igualmente espacadas, entao
    a coluna central se repete, e rolar 1 ou 2 eventos parecia a mesma coisa.
    Resultado: eventos de telas diferentes caiam na bolha errada, duplicados.
    """
    y_min, y_max = EVENTOS_Y_VISIVEL
    observacoes = defaultdict(list)    # (minuto, n, lado, dy) -> [(nome, icone)]
    sem_minuto = set()                 # nomes vistos ao lado de bolha ilegivel
    sem_ordem = defaultdict(set)       # nome visto so em bolha de ordem incerta -> {(minuto, lado)}
    bolhas_vistas = set()              # (minuto, (periodo, qual bolha desse minuto))

    for tela in telas:
        # Dentro de UMA tela a posicao e confiavel (a tela esta parada):
        # junta as bolhas dos quadros dela e vota o minuto de cada uma.
        lidas = []                     # (y, minuto)
        ys_por_quadro = []
        for _, painel in tela.quadros:
            ys = achar_bolhas(painel)
            ys_por_quadro.append(ys)
            textos = ler_pecas(ocr, [painel.crop((CENTRO_X + MINUTO_DX[0], round(y + MINUTO_DY[0]),
                                                  CENTRO_X + MINUTO_DX[1], round(y + MINUTO_DY[1])))
                                     for y in ys], painel.crop(CAIXA_TITULO_FIM))
            lidas += [(y, ler_minuto(t)) for y, ts in zip(ys, textos) for t in ts]
        bolhas = []                    # (y, minuto)
        for grupo in agrupar([y for y, _ in lidas], 8):
            y = statistics.median(grupo)
            minuto, _ = votar([m for yy, m in lidas if abs(yy - y) <= 8])
            bolhas.append((y, minuto))
        marcadores = [(ln.cy, normalizado(ln.texto)) for linhas in tela.linhas for ln in linhas
                      if normalizado(ln.texto) in MARCADORES]
        repeticoes = repeticoes_acima(bolhas, marcadores)
        bolhas_vistas |= {(m, n) for (_, m), n in zip(bolhas, repeticoes) if m and n is not None}

        for (_, painel), linhas, ys in zip(tela.quadros, tela.linhas, ys_por_quadro):
            def lado_da(ln):
                if CENTRO_X - NOME_DX_MAX <= ln.x1 < CENTRO_X - 30:
                    return "casa"
                if CENTRO_X + 30 < ln.x0 <= CENTRO_X + NOME_DX_MAX:
                    return "fora"
                return None
            confiaveis = [ln for ln in linhas if ln.binaria and lado_da(ln)]
            for ln in linhas:
                lado = lado_da(ln)
                if lado is None or normalizado(ln.texto) in MARCADORES:
                    continue
                cy = ln.cy
                if not ln.binaria:
                    # A passada na imagem original acerta acentos, mas a
                    # ALTURA que ela da para a linha sai torta (ate ~13 px, o
                    # estadio atras confunde o OCR). Isso partia um evento
                    # em dois (David Villa aos 62' saia duplicado). Usa a
                    # altura da mesma linha lida numa passada binarizada.
                    mesma = [c for c in confiaveis if lado_da(c) == lado and abs(c.cy - cy) <= 20]
                    mesma = max(mesma, default=None, key=lambda c: SequenceMatcher(
                        None, normalizado(c.texto), normalizado(ln.texto)).ratio())
                    if mesma is not None and SequenceMatcher(
                            None, normalizado(mesma.texto), normalizado(ln.texto)).ratio() >= 0.5:
                        cy = mesma.cy
                    else:
                        # Nome curto em cima do estadio movimentado ("Felipe"
                        # e o cartao aos 90+2', Inter x Sport): a passada
                        # binarizada nao le nada, e o evento sumia calado.
                        # A altura do icone ao lado tambem e confiavel. Mas
                        # so vale icone sem dono: letreiro do estadio lido
                        # perto de um evento ("Unimed", "Banrisul") acharia o
                        # icone DESSE evento e votaria no nome dele.
                        cy = altura_do_icone(painel, lado, cy)
                        if cy is None or any(lado_da(c) == lado and abs(c.cy - cy) <= 12
                                             for c in confiaveis):
                            continue
                # Texto cortado na borda da area visivel nao conta: ele
                # aparece inteiro em outra tela.
                if not (y_min + 8 <= cy <= y_max - 8):
                    continue
                icone = classificar_icone(painel, lado, cy)
                if icone is None:
                    continue
                if not ys or not bolhas:
                    continue
                # Distancia texto -> bolha medida no mesmo quadro.
                y_bolha = min(ys, key=lambda y: abs(y - cy))
                # Bolha longe: a dele esta fora da tela (cortada na borda).
                # Nesta tela nao da para saber o minuto; outra tela mostra.
                if abs(y_bolha - cy) > DISTANCIA_MAX_BOLHA:
                    continue
                i = min(range(len(bolhas)), key=lambda k: abs(bolhas[k][0] - y_bolha))
                minuto = bolhas[i][1]
                chave = chave_nome(limpar_nome(ln.texto) or ln.texto)
                if minuto is None:
                    sem_minuto.add(chave)
                    continue
                if repeticoes[i] is None:
                    sem_ordem[chave].add((minuto, lado))
                    continue
                observacoes[(minuto, repeticoes[i], lado, cy - y_bolha)].append((ln.texto, icone))

    # A posicao em relacao a bolha varia 1-2 px entre telas (rolagem para no
    # meio de pixel): agrupa por bolha+lado e junta as posicoes proximas.
    itens = []
    por_bolha = defaultdict(list)
    for (minuto, n, lado, dy), obs in observacoes.items():
        por_bolha[(minuto, n, lado)].append((dy, obs))
    for (minuto, n, lado), linhas in por_bolha.items():
        for grupo in agrupar([dy for dy, _ in linhas], 6):
            dy = statistics.median(grupo)
            obs = [o for d, os_ in linhas if abs(d - dy) <= 6 for o in os_]
            if len(obs) < LEITURAS_MINIMAS_EVENTO:
                continue
            nome, p_nome = votar_nome([n for n, _ in obs])
            icone, p_icone = votar([i for _, i in obs])
            if p_nome:
                avisos.add(f"nome do evento aos {minuto}' ({lado}): {p_nome}")
            if p_icone:
                avisos.add(f"icone do evento de {nome} aos {minuto}' ({lado}): {p_icone}")
                icone = "desconhecido"
            itens.append(((ordem_do_minuto(minuto), n, lado != "casa", dy),
                          {"minuto": minuto, "lado": lado, "icone": icone, "jogador": nome}))

    # Nome visto so onde nao deu para situar pode ser um evento perdido. Mas
    # quase sempre e leitura torta de quem foi lido certo noutra tela
    # ("nilmarv" = Nilmar) ou lixo curto ("a"): esses nao viram aviso.
    # Tambem pedaco de nome lido: o OCR as vezes parte a linha, e "Sergio
    # Ramos" vira "Sergi" + "Ramos" - por isso compara tambem com cada
    # palavra dos nomes lidos.
    # Antes de comparar, junta as letras que o OCR troca: "danjlp" (Danilo,
    # Santos x Fluminense) nao chegava a 0.7 de "danilo" e virava revisar.
    def sem_trocas(chave):
        return chave.translate(TROCAS_LETRA)

    lidos = [sem_trocas(chave_nome(i["jogador"])) for _, i in itens if i["jogador"]]
    lidos += [sem_trocas(chave_nome(p)) for _, i in itens if i["jogador"]
              for p in i["jogador"].split() if p.lower() not in PARTICULAS]

    def perdido(chave):
        return len(chave) >= 4 and not get_close_matches(sem_trocas(chave), lidos, n=1, cutoff=0.7)

    for chave in filter(perdido, sem_minuto):
        avisos.add(f"evento com minuto ilegivel em todas as telas (jogador ~{chave})")
    # Na bolha de ordem incerta o minuto e o lado sao conhecidos. Se ali ja
    # tem evento lido com nome parecido (um contido no outro, ou >= 0.6), e
    # ele: "klep9r" = Kleber aos 80' (Sport x Vasco), e "jesusnavasbanrisul..."
    # = Jesus Navas com o letreiro do estadio grudado (Inter x Vitoria). So
    # no mesmo minuto e lado da para afrouxar assim sem esconder evento.
    def lido_ali(chave, minuto, lado):
        chave = sem_trocas(chave)
        for _, i in itens:
            if i["minuto"] != minuto or i["lado"] != lado or not i["jogador"]:
                continue
            nome = sem_trocas(chave_nome(i["jogador"]))
            contido = (len(nome) >= 4 and nome in chave) or (len(chave) >= 4 and chave in nome)
            if contido or SequenceMatcher(None, chave, nome).ratio() >= 0.6:
                return True
        return False

    for chave in filter(perdido, set(sem_ordem) - sem_minuto):
        if all(lido_ali(chave, minuto, lado) for minuto, lado in sem_ordem[chave]):
            continue
        avisos.add(f"evento sempre no topo da lista, sem saber qual bolha (jogador ~{chave})")

    # Toda bolha tem ao menos um evento. Bolha sem nenhum = evento que nao
    # foi lido em lugar nenhum; sem esta conta ele sumia sem aviso.
    com_evento = {(i["minuto"], ordem[1]) for ordem, i in itens}
    for minuto, (periodo, n) in sorted(bolhas_vistas - com_evento,
                                       key=lambda b: (ordem_do_minuto(b[0]), b[1])):
        qual = f" ({n + 1}a bolha desse minuto)" if n else ""
        qual += " (depois do intervalo)" if periodo else ""
        avisos.add(f"bolha {minuto}'{qual} sem nenhum evento lido: evento perdido")

    # Ordem: minuto, bolha, depois lado, depois de cima para baixo. Por lado porque a
    # assistencia pertence ao gol logo acima DO MESMO LADO.
    itens.sort(key=lambda t: t[0])
    return [i for _, i in itens]


# --------------------------------------------------------------------------
# Leitura -> JSON final
# --------------------------------------------------------------------------

def minuto_int(texto, avisos: Avisos):
    """'41' -> 41; '90+2' -> 90 (o acrescimo vira aviso); ilegivel -> None."""
    if texto is None:
        return None
    base, _, extra = texto.partition("+")
    if extra:
        # O formato de saida so tem minuto inteiro. Guardamos o minuto base
        # e registramos o acrescimo, sem marcar para revisao.
        avisos.add(f"minuto {texto} com acrescimo gravado como {base}", revisar=False)
    return int(base)


def montar_eventos(itens, avisos: Avisos):
    """Transforma os icones da linha do tempo nos eventos do JSON.

    - "assistencia" logo depois de um gol do mesmo minuto e lado e a
      assistencia desse gol (e assim que o PES desenha: triangulo azul
      embaixo da bola).
    - Substituicao = par entrou/saiu do mesmo minuto e lado. Com mais de uma
      troca no mesmo minuto, pareamos na ordem: 1o entrou com 1o saiu.
    """
    eventos = []
    trocas = {}     # (minuto, lado) -> evento de substituicao ainda incompleto
    ultimo_gol = None

    for item in itens:
        minuto = minuto_int(item["minuto"], avisos)
        lado, icone, jogador = item["lado"], item["icone"], item["jogador"]

        if icone in ("gol", "gol_contra"):
            ultimo_gol = {"minuto": minuto, "lado": lado, "tipo": icone,
                          "jogador": jogador, "assistencia": None}
            eventos.append(ultimo_gol)
            continue

        if icone == "assistencia":
            if (ultimo_gol is not None and ultimo_gol["minuto"] == minuto
                    and ultimo_gol["lado"] == lado and ultimo_gol["assistencia"] is None):
                ultimo_gol["assistencia"] = jogador
            else:
                avisos.add(f"assistencia de {jogador} aos {minuto}' ({lado}) "
                           "sem gol correspondente")
            ultimo_gol = None
            continue
        ultimo_gol = None

        if icone in ("entrou", "saiu"):
            chave = (minuto, lado)
            pendente = trocas.get(chave)
            if pendente is None or pendente[icone] is not None:
                pendente = {"minuto": minuto, "lado": lado, "tipo": "substituicao",
                            "entrou": None, "saiu": None}
                eventos.append(pendente)
                trocas[chave] = pendente
            pendente[icone] = jogador
            continue

        if icone in ("cartao_amarelo", "cartao_vermelho"):
            eventos.append({"minuto": minuto, "lado": lado, "tipo": icone, "jogador": jogador})
            continue

        avisos.add(f"icone desconhecido aos {minuto}' ({lado}), jogador {jogador} "
                   "- evento nao registrado")

    for ev in eventos:
        if ev["tipo"] == "substituicao" and (ev["entrou"] is None or ev["saiu"] is None):
            avisos.add(f"substituicao incompleta aos {ev['minuto']}' ({ev['lado']}): "
                       f"entrou={ev['entrou']}, saiu={ev['saiu']}")
        if ev["minuto"] is None:
            avisos.add(f"evento sem minuto: {ev}")
    return eventos


def normalizar_time(nome, lado: str, avisos: Avisos):
    """Nome lido -> nome oficial de times.py. Aceita erro pequeno do OCR
    ("Corinthlans") comparando com a lista; o que nao parecer com nenhum time
    fica como foi lido, com aviso."""
    if not nome:
        return None
    try:
        return times.nome_oficial(nome)
    except ValueError:
        pass
    oficiais = {times.normalizar(t): t for t in times.TIMES}
    parecido = get_close_matches(times.normalizar(nome), list(oficiais), n=1, cutoff=0.8)
    if parecido:
        return oficiais[parecido[0]]
    avisos.add(f"time da {lado} '{nome}' nao esta em times.py")
    return nome


# Letras que o NFKD nao separa em base + acento ("ł" nao vira "l" + marca).
LETRAS_SEM_DECOMPOSICAO = str.maketrans({"ł": "l", "ø": "o", "đ": "d", "ß": "ss", "æ": "ae",
                                         "œ": "oe", "ı": "i", "þ": "th"})


def chave_base(texto):
    """'Łukasz Fabiański' -> 'lukaszfabianski': sem acento, espaco e pontuacao."""
    t = unicodedata.normalize("NFKD", texto.lower().translate(LETRAS_SEM_DECOMPOSICAO))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)))


_elencos = None


def elencos():
    """Chave do time -> nomes dos jogadores, da base do PES. None se nao ha
    base configurada ou ela nao abre (ai os nomes ficam como lidos)."""
    global _elencos
    if _elencos is None:
        _elencos = {}
        if BASE_JOGADORES and Path(BASE_JOGADORES).is_file():
            with gzip.open(BASE_JOGADORES, "rt", encoding="utf-8") as f:
                for jogador in json.load(f):
                    for time in jogador["t"]:
                        _elencos.setdefault(chave_base(time), []).append(jogador["n"])
    return _elencos or None


def elenco_do_time(time):
    """Jogadores do time na base. O nome pode ser mais curto no times.py
    ("Vasco" x "Vasco da Gama"): vale o igual, senao o unico que comeca igual."""
    base = elencos()
    if not base or not time:
        return None
    chave = chave_base(NOME_NA_BASE.get(time, time))
    if chave in base:
        return base[chave]
    parecidos = [c for c in base if c.startswith(chave)]
    return base[parecidos[0]] if len(parecidos) == 1 else None


def nome_do_elenco(nome, elenco):
    """O jogador do elenco mais parecido com o nome lido, ou None se nenhum
    parece o bastante ou se dois parecem quase igual (na duvida, nao troca)."""
    chave = chave_base(nome)
    pontos = sorted(((SequenceMatcher(None, chave, chave_base(c)).ratio(), c) for c in elenco),
                    reverse=True)
    if not pontos or pontos[0][0] < SEMELHANCA_MINIMA_NOME:
        return None
    if len(pontos) > 1 and pontos[0][0] - pontos[1][0] < FOLGA_MINIMA_NOME:
        # Dois "Danilo" no mesmo elenco: se a grafia e a mesma, tanto faz.
        return pontos[0][1] if pontos[0][1] == pontos[1][1] else None
    return pontos[0][1]


def corrigir_nomes(casa, fora, eventos, notas, avisos: Avisos):
    """Troca cada nome lido pelo do elenco do time na base do PES."""
    if elencos() is None:
        return
    elenco = {"casa": elenco_do_time(casa), "fora": elenco_do_time(fora)}
    for lado, time in (("casa", casa), ("fora", fora)):
        if elenco[lado] is None:
            avisos.add(f"time {time} nao achado na base de jogadores: nomes da {lado} "
                       "ficaram como o OCR leu", revisar=False)

    def corrigir(nome, lado):
        if not nome or elenco[lado] is None:
            return nome
        certo = nome_do_elenco(nome, elenco[lado])
        if certo is None:
            # Pode ser jogador transferido depois da base, ou leitura ruim.
            # O site ainda tenta casar o nome; so fica o registro.
            avisos.add(f"'{nome}' ({lado}) nao esta no elenco da base", revisar=False)
            return nome
        return certo

    outro = {"casa": "fora", "fora": "casa"}
    for ev in eventos:
        lado = ev["lado"]
        # No gol contra o autor e do time que sofreu o gol.
        autor = outro[lado] if ev["tipo"] == "gol_contra" else lado
        for campo in ("jogador", "assistencia", "entrou", "saiu"):
            if campo in ev:
                ev[campo] = corrigir(ev[campo], autor if campo == "jogador" else lado)
    for lado, lista in notas.items():
        for n in lista:
            n["jogador"] = corrigir(n["jogador"], lado)
    juntar_notas_repetidas(notas, avisos)


def juntar_notas_repetidas(notas: dict, avisos: Avisos):
    """O OCR le o mesmo nome com grafias diferentes em telas diferentes
    ("Samuel Eto'o" / "Samuel Etoo"), entao ler_notas nao junta as duas
    linhas; depois da correcao pelo elenco elas tem o mesmo nome. Junta."""
    for lado, lista in notas.items():
        unicos = {}
        for n in lista:
            chave = chave_nome(n["jogador"]) if n["jogador"] else None
            if chave is None or chave not in unicos:
                unicos[chave if chave else id(n)] = n
                continue
            dono = unicos[chave]
            for campo in ("numero", "nota"):
                if dono[campo] is None:
                    dono[campo] = n[campo]
                elif n[campo] is not None and n[campo] != dono[campo]:
                    avisos.add(f"notas ({lado}), jogador {dono['jogador']} lido duas vezes "
                               f"com {campo} diferente: {dono[campo]} e {n[campo]}")
            dono["melhor_em_campo"] = dono["melhor_em_campo"] or n["melhor_em_campo"]
        notas[lado] = list(unicos.values())


def serie_da_partida(casa, fora):
    """Mesma regra do loop (rodar_jogos.nome_do_video): so ha serie quando os
    dois times sao da mesma. A x B, ou time que so completa a liga -> None."""
    try:
        serie = times.serie_do_time(casa)
        return serie if serie and serie == times.serie_do_time(fora) else None
    except (ValueError, TypeError):
        return None


def rodada_do_nome(nome_arquivo: str):
    m = re.search(r"(\d+)\s*[ªº°]?\s*Rodada", nome_arquivo, re.IGNORECASE)
    return int(m.group(1)) if m else None


def conferir_estatisticas(est: dict, avisos: Avisos):
    p = est["posse"]
    if None not in p.values() and p["casa"] + p["fora"] != 100:
        avisos.add(f"posse nao soma 100%: {p['casa']} + {p['fora']}")


def conferir_notas(notas: dict, eventos: list, avisos: Avisos):
    for lado, lista in notas.items():
        if not lista:
            avisos.add(f"notas da {lado} nao lidas")
    melhores = [n["jogador"] for lista in notas.values() for n in lista if n["melhor_em_campo"]]
    if len(melhores) != 1 and any(notas.values()):
        avisos.add(f"esperava 1 melhor em campo, achei {len(melhores)}: {melhores}")
    # A aba de notas mostra os 11 titulares e o loop nao rola essa lista, entao
    # quem entrou no jogo normalmente fica de fora. E limitacao do video, nao
    # erro de leitura: so informa, sem marcar para revisao.
    com_nota = {chave_nome(n["jogador"]) for lista in notas.values() for n in lista if n["jogador"]}
    sem_nota = [e["entrou"] for e in eventos
                if e["tipo"] == "substituicao" and e["entrou"]
                and chave_nome(e["entrou"]) not in com_nota]
    if sem_nota and any(notas.values()):
        avisos.add("sem nota no video (entraram no jogo): " + ", ".join(sem_nota), revisar=False)


def extrair(video: Path, ocr: OCR, salvar_quadros: bool) -> dict:
    avisos = Avisos()
    resultado = {
        "video": video.name,
        # Data do arquivo (renomear nao muda): o site reconhece o mesmo video
        # num reenvio mesmo que o nome se repita em outro jogo.
        "gravado_em": datetime.fromtimestamp(video.stat().st_mtime).isoformat(timespec="seconds"),
        "extraido_em": datetime.now().isoformat(timespec="seconds"),
        "serie": None,
        "rodada": rodada_do_nome(video.name),
        "casa": {"time": None, "gols": None},
        "fora": {"time": None, "gols": None},
        "eventos": [],
        "notas": {"casa": [], "fora": []},
        "estatisticas": None,
    }

    telas = selecionar_telas(video)
    if salvar_quadros:
        pasta = Path(PASTA_DIAGNOSTICO) / video.stem
        pasta.mkdir(parents=True, exist_ok=True)
        for i, tela in enumerate(telas, 1):
            segundo, painel = tela.quadros[0]
            painel.save(pasta / f"{i:02d}_{segundo:07.1f}s.png")

    for tela in telas:
        tela.linhas = [ler_linhas(ocr, painel) for _, painel in tela.quadros]
        tela.aba = aba_da_tela([ln for linhas in tela.linhas for ln in linhas])
    telas = [t for t in telas if t.aba]

    if not telas:
        # Sem a tela de fim de jogo nao ha o que ler. Salva mesmo assim
        # (status revisar) para o video nao ser reprocessado a toa toda vez.
        avisos.add(f"tela 'Fim de jogo' nao encontrada nos ultimos {SEGUNDOS_DO_FINAL}s")
        return {**resultado, "status": "revisar", "avisos": avisos.lista}

    por_aba = defaultdict(list)
    for tela in telas:
        por_aba[tela.aba].append(tela)
    for aba in ("estatisticas", "pontuacao", "eventos"):
        if not por_aba[aba]:
            avisos.add(f"aba '{aba}' nao apareceu no video")

    cab = ler_cabecalho(ocr, telas, avisos)
    casa = normalizar_time(cab["casa"][0], "casa", avisos)
    fora = normalizar_time(cab["fora"][0], "fora", avisos)
    itens = ler_eventos(ocr, por_aba["eventos"], avisos) if por_aba["eventos"] else []
    eventos = montar_eventos(itens, avisos)
    notas = ler_notas(ocr, por_aba["pontuacao"], avisos)
    corrigir_nomes(casa, fora, eventos, notas, avisos)
    conferir_notas(notas, eventos, avisos)
    est = None
    if por_aba["estatisticas"]:
        est = ler_estatisticas(ocr, por_aba["estatisticas"], avisos)
        conferir_estatisticas(est, avisos)

    # A conferencia principal: gols nos eventos x placar.
    if por_aba["eventos"]:
        for lado, gols in (("casa", cab["casa"][1]), ("fora", cab["fora"][1])):
            nos_eventos = sum(1 for e in eventos
                              if e["tipo"] in ("gol", "gol_contra") and e["lado"] == lado)
            if gols is not None and nos_eventos != gols:
                avisos.add(f"placar da {lado} e {gols}, mas li {nos_eventos} gol(s) nos eventos")

    return {
        **resultado,
        "serie": serie_da_partida(casa, fora),
        "casa": {"time": casa, "gols": cab["casa"][1]},
        "fora": {"time": fora, "gols": cab["fora"][1]},
        "eventos": eventos,
        "notas": notas,
        "estatisticas": est,
        "status": "revisar" if avisos.revisar else "ok",
        "avisos": avisos.lista,
    }


# --------------------------------------------------------------------------
# O loop sobre os videos
# --------------------------------------------------------------------------

def caminho_json(video: Path) -> Path:
    return video.with_suffix(".json")


def listar_videos():
    pasta = Path(PASTA_VIDEOS)
    return sorted(p for p in pasta.rglob("*")
                  if p.is_file() and p.suffix.lower() in EXTENSOES_VIDEO)


def achar_video(arg: str) -> Path:
    """Aceita caminho completo, ou so o nome do arquivo (procura nas subpastas)."""
    p = Path(arg)
    if p.is_file():
        return p
    candidatos = [v for v in listar_videos() if v.name == p.name]
    if not candidatos:
        raise FileNotFoundError(f"nao achei o video '{arg}' em {PASTA_VIDEOS}")
    return candidatos[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrai o resultado do final dos videos.")
    parser.add_argument("arquivo", nargs="?", help="um video so (sobrescreve o .json)")
    parser.add_argument("--forcar", action="store_true", help="refaz todos os videos")
    parser.add_argument("--salvar-quadros", action="store_true",
                        help=f"grava as telas usadas em {PASTA_DIAGNOSTICO}/")
    args = parser.parse_args()

    # O terminal do Windows as vezes nao e UTF-8; sem isto um nome com
    # acento ou a barra U+FF5C derrubaria o print.
    sys.stdout.reconfigure(errors="replace")

    if args.arquivo:
        try:
            videos = [achar_video(args.arquivo)]
        except FileNotFoundError as erro:
            print(f"ERRO: {erro}")
            return 1
    else:
        videos = [v for v in listar_videos() if args.forcar or not caminho_json(v).exists()]
    if not videos:
        print("Nenhum video novo para processar (use --forcar para refazer).")
        return 0

    try:
        ocr = OCR()
    except RuntimeError as erro:
        print(f"ERRO: {erro}")
        return 1

    if elencos() is None:
        motivo = (f"nao achei {BASE_JOGADORES}" if BASE_JOGADORES
                  else "'base_jogadores' vazio no caminhos.ini")
        print(f"AVISO: nomes ficam como o OCR leu ({motivo}).")
    print(f"{len(videos)} video(s) para processar.\n")
    falhas = 0
    for video in videos:
        print(f"- {video.name}")
        try:
            resultado = extrair(video, ocr, args.salvar_quadros)
        except Exception as erro:
            # Erro de ffmpeg/OCR: NAO grava .json, para o video ser tentado
            # de novo na proxima rodada. E segue para os outros.
            falhas += 1
            print(f"    ERRO: {type(erro).__name__}: {erro}\n")
            continue
        with open(caminho_json(video), "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        c, fo = resultado["casa"], resultado["fora"]
        print(f"    {c['time']} {c['gols']} x {fo['gols']} {fo['time']}  |  "
              f"{len(resultado['eventos'])} evento(s)  |  {resultado['status']}")
        for aviso in resultado["avisos"]:
            print(f"      aviso: {aviso}")
        print()

    print(f"Fim: {len(videos) - falhas} ok, {falhas} com erro.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
