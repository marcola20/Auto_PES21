"""
visao.py  --  Auto_PES21

Tudo que envolve "olhar a tela" mora aqui, para os outros scripts nao repetirem
o mesmo codigo.

Duas tecnicas diferentes, cada uma para um problema:

1) COMPARACAO DIRETA DE PIXELS - usada para a tela de fim de jogo.
   Funciona porque aquele painel e opaco e nao muda de brilho.

2) MASCARA DE TEXTO VERDE - usada para ler o nome do time selecionado.
   O card do time muda de brilho conforme ganha ou perde o foco, entao
   comparar pixel a pixel falharia. Como o nome do item SELECIONADO e sempre
   verde, eu marco so os pixels "verdes" e comparo o formato das letras.
   Assim o brilho do fundo deixa de importar.
"""

import time
from pathlib import Path

from PIL import Image, ImageChops, ImageGrab

# ---------------------------------------------------------------------------
# Regioes da tela, em pixels (x1, y1, x2, y2), medidas em 1920x1080.
# Se voce mudar a resolucao do jogo, todas essas precisam ser remedidas.
# ---------------------------------------------------------------------------
REGIAO_FIM_DE_JOGO = (855, 70, 1065, 115)
REGIAO_NOME_CASA   = (205, 390, 680, 447)
REGIAO_NOME_FORA   = (1068, 390, 1543, 447)
REGIAO_PREJOGO     = (795, 905, 1125, 965)   # botao "Inicio" da tela pre-jogo

# Quanto o verde precisa dominar o vermelho e o azul para o pixel contar
# como texto. 25 funcionou bem nos testes.
MARGEM_VERDE = 25

# Limiares de decisao (medidos nos prints reais, nao chutados):
#   fim de jogo : telas de fim deram 0-5, a mais parecida que nao era deu 47
#   nome do time: mesmo time deu IoU 0.997, times diferentes deram 0.19
LIMIAR_FIM_DE_JOGO = 15
LIMIAR_NOME_TIME   = 0.75


def capturar_tela() -> Image.Image:
    """Tira um print da tela inteira."""
    return ImageGrab.grab(all_screens=True).convert("RGB")


# ---------------------------------------------------------------------------
# Tecnica 1: comparacao direta (tela de fim de jogo)
# ---------------------------------------------------------------------------

def diferenca_de_pixels(regiao_da_tela: Image.Image,
                        template: Image.Image) -> float:
    """Media da diferenca de brilho pixel a pixel. 0 = imagens identicas."""
    if regiao_da_tela.size != template.size:
        raise ValueError(
            f"Tamanho incompativel: tela {regiao_da_tela.size} x "
            f"template {template.size}. O jogo esta em outra resolucao?"
        )
    dif = ImageChops.difference(regiao_da_tela, template).convert("L")
    pixels = list(dif.get_flattened_data())
    return sum(pixels) / len(pixels)


def eh_fim_de_jogo(tela: Image.Image, template: Image.Image) -> bool:
    """True se a tela de fim de partida estiver aparecendo."""
    recorte = tela.crop(REGIAO_FIM_DE_JOGO)
    return diferenca_de_pixels(recorte, template) < LIMIAR_FIM_DE_JOGO


# ---------------------------------------------------------------------------
# Tecnica 2: mascara de texto verde (nome do time selecionado)
# ---------------------------------------------------------------------------

def mascara_texto_verde(imagem: Image.Image,
                        margem: int = MARGEM_VERDE) -> list:
    """Transforma a imagem numa lista de True/False: True onde ha texto verde.

    Para cada pixel eu comparo o canal verde com o maior entre vermelho e azul.
    Num cinza qualquer os tres sao parecidos, entao a conta da perto de zero.
    No verde do PES o G e bem maior, entao passa da margem.
    """
    return [
        (g - max(r, b)) > margem
        for r, g, b in imagem.convert("RGB").get_flattened_data()
    ]


def sobreposicao(mascara_a: list, mascara_b: list) -> float:
    """Quanto dois textos se sobrepoem: 1.0 = identicos, 0.0 = nada em comum.

    E a conta chamada IoU (interseccao dividida pela uniao): dos pixels que
    sao texto em pelo menos uma das duas, quantos sao texto nas DUAS.

    Comparar so os acertos totais nao serviria: a regiao e quase toda fundo,
    entao dois nomes diferentes ja bateriam 94% so pelos pixels vazios.
    """
    if len(mascara_a) != len(mascara_b):
        raise ValueError("As duas mascaras tem tamanhos diferentes.")
    interseccao = sum(a and b for a, b in zip(mascara_a, mascara_b))
    uniao = sum(a or b for a, b in zip(mascara_a, mascara_b))
    return interseccao / uniao if uniao else 0.0


def regiao_do_painel(painel: str) -> tuple:
    """Devolve a regiao do nome do time para 'casa' ou 'fora'."""
    if painel == "casa":
        return REGIAO_NOME_CASA
    if painel == "fora":
        return REGIAO_NOME_FORA
    raise ValueError(f"Painel deve ser 'casa' ou 'fora', recebi '{painel}'.")


def ler_nome_selecionado(painel: str, tela: Image.Image = None) -> list:
    """Captura a regiao do nome do time e devolve a mascara do texto."""
    if tela is None:
        tela = capturar_tela()
    return mascara_texto_verde(tela.crop(regiao_do_painel(painel)))


def carregar_template(caminho) -> Image.Image:
    """Le um template do disco, com mensagem clara se nao existir."""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(f"Template nao encontrado: {arquivo.resolve()}")
    return Image.open(arquivo).convert("RGB")


def tem_texto(mascara: list, minimo: int = 100) -> bool:
    """True se a mascara achou texto de verdade, e nao so fundo vazio.

    Existe porque sobreposicao() devolve 0.0 em DOIS casos muito diferentes:
    quando os textos sao completamente diferentes, e quando nao ha texto
    nenhum. Sem essa checagem, "nao consegui ler a tela" se disfarca de
    "os nomes sao diferentes" - e o script tira a conclusao errada.
    """
    return sum(mascara) >= minimo


def ler_regiao(regiao: tuple, tentativas: int = 3, espera: float = 0.4,
               minimo: int = 100) -> list:
    """Le uma regiao da tela, insistindo se a captura vier vazia.

    Existe por causa de uma falha real observada em teste: o ImageGrab as vezes
    devolve um quadro em branco em jogo DirectX em tela cheia. Aconteceu entre
    duas leituras separadas por 0.6s, sem nenhuma tecla no meio - ou seja, nao
    era animacao de menu, era a captura falhando.

    Sem esta retentativa, um unico quadro ruim derrubaria o loop inteiro na hora
    de conferir uma tela. Devolve a ultima mascara lida, mesmo vazia, para quem
    chamou decidir o que fazer.
    """
    mascara = []
    for tentativa in range(tentativas):
        mascara = mascara_texto_verde(capturar_tela().crop(regiao))
        if tem_texto(mascara, minimo):
            return mascara
        if tentativa < tentativas - 1:
            time.sleep(espera)
    return mascara


# ---------------------------------------------------------------------------
# Paineis de intervalo e fim de jogo
# ---------------------------------------------------------------------------

# Duas manchas DENTRO do painel verde, em lados opostos da tela, escolhidas
# por serem verde LISO: no painel real dao fracao 1.000 e desvio 0.0.
#
# Por que duas manchas e por que medir textura: a versao anterior usava uma
# faixa larga e so olhava "quanta cor verde tem ali". Isso disparou 41 vezes
# durante uma partida num estadio de arquibancada verde - e cada disparo
# mandava um Enter, ate que um deles caiu num replay e abriu o editor.
#
# Arquibancada, gramado e painel de publicidade sao verdes, mas TEXTURADOS:
# torcida, degraus, listras do campo. O painel do jogo e cor chapada. Exigir
# desvio quase zero em DOIS pontos distantes elimina o falso positivo - um
# estadio teria que ser liso nos dois lugares ao mesmo tempo.
#
# As duas manchas ficam na faixa de CIMA do painel (y 200-330), acima dos
# escudos, e espelhadas em relacao ao centro da tela. A mancha da direita ja
# desceu ate y 700, colada no escudo do time de fora: o escudo redondo do
# Cruzeiro, mais largo que os outros, invadiu a mancha, a textura estourou e o
# painel nunca foi reconhecido - a partida ficou parada no Intervalo.
# Nada de escudo, nome ou estatistica pode cair dentro destas regioes.
REGIOES_PAINEL_VERDE = [(250, 200, 420, 330), (1500, 200, 1670, 330)]
LIMIAR_PAINEL_VERDE = 0.95   # fracao de pixels verdes exigida em cada mancha
LIMIAR_TEXTURA_PAINEL = 5.0  # desvio maximo: acima disso e textura, nao painel


def fracao_verde(imagem: Image.Image) -> float:
    """Que fracao da imagem e do verde forte do painel do PES (0.0 a 1.0)."""
    pixels = list(imagem.convert("RGB").get_flattened_data())
    verdes = sum(1 for r, g, b in pixels
                 if g > 70 and g - r > 35 and g - b > 35)
    return verdes / len(pixels) if pixels else 0.0


def textura(imagem: Image.Image) -> float:
    """Quanto a imagem varia de brilho. 0 = cor chapada."""
    cinza = list(imagem.convert("L").get_flattened_data())
    media = sum(cinza) / len(cinza)
    return (sum((c - media) ** 2 for c in cinza) / len(cinza)) ** 0.5


def ha_painel_verde(tela: Image.Image) -> bool:
    """True se o painel verde (Intervalo OU Fim de jogo) esta na tela.

    De proposito NAO distingue os dois: a acao e a mesma nos dois casos -
    confirmar para avancar. Quem decide o que acontece depois e o painel
    ESCURO que aparece em seguida, e aquele e facil de diferenciar.

    Detectar a COR em vez do TEXTO e mais robusto aqui, porque o painel verde e
    semitransparente e o estadio ao fundo muda os pixels do texto de uma
    partida para outra.
    """
    for regiao in REGIOES_PAINEL_VERDE:
        recorte = tela.crop(regiao)
        if fracao_verde(recorte) < LIMIAR_PAINEL_VERDE:
            return False
        if textura(recorte) >= LIMIAR_TEXTURA_PAINEL:
            return False
    return True


def eh_intervalo(tela: Image.Image, template: Image.Image) -> bool:
    """True se o painel ESCURO de intervalo (com o botao '2o tempo') esta na tela."""
    recorte = tela.crop(REGIAO_FIM_DE_JOGO)   # mesma posicao do titulo
    return diferenca_de_pixels(recorte, template) < LIMIAR_FIM_DE_JOGO


# Topo da caixa escura de informacao que aparece nos replays ("Chute", nome do
# jogador, minuto). Uso o TOPO da caixa, que nao tem texto: e so o padrao
# hexagonal do fundo, igual em qualquer replay. A caixa e opaca, entao o
# gramado atras nao atrapalha - medido: 1.53 entre dois frames do mesmo replay
# com cameras diferentes, contra 42 a 158 em qualquer outra tela.
REGIAO_REPLAY = (555, 850, 1230, 900)


def eh_replay(tela: Image.Image, template: Image.Image) -> bool:
    """True se um replay/melhor momento esta passando na tela."""
    return diferenca_de_pixels(tela.crop(REGIAO_REPLAY), template) < LIMIAR_FIM_DE_JOGO


# Faixa do titulo da aba no painel de fim de jogo / intervalo:
# "Pontuacao dos jogadores", "Eventos da partida", etc. O L1/R1 troca entre elas.
REGIAO_TITULO_ABA = (760, 288, 1160, 328)

LIMITE_BRANCO = 185


def mascara_texto_branco(imagem: Image.Image, limite: int = LIMITE_BRANCO) -> list:
    """Marca os pixels quase brancos - o texto claro sobre painel escuro.

    A versao verde nao serve aqui: dentro da partida os titulos sao brancos.
    Comparar o FORMATO do texto continua sendo a ideia, so muda a cor que
    identifica o texto.
    """
    return [
        r > limite and g > limite and b > limite
        for r, g, b in imagem.convert("RGB").get_flattened_data()
    ]


def ler_titulo_da_aba(tela: Image.Image = None) -> list:
    """Le o titulo da aba ativa no painel de fim de jogo."""
    if tela is None:
        tela = capturar_tela()
    return mascara_texto_branco(tela.crop(REGIAO_TITULO_ABA))


# Palavra "TECNICO" na barra de baixo da tela de FORMACAO (escalacao).
# O recorte e justo: o T e o O encostam nas bordas. Nao atrapalha, porque a
# captura ao vivo e cortada igual - mas se um dia a formacao deslocar alguns
# pixels, alargar esta regiao (e recapturar o template) e a primeira coisa
# a tentar.
# Escolhida porque e o unico texto daquela tela que NAO muda: o ano, o escudo,
# os nomes dos jogadores e o estadio ao fundo mudam a cada partida; ela nao.
#
# A comparacao aqui e de PIXELS, nao de mascara de texto: as letras sao cinza
# escuro sobre barra cinza clara, e nenhuma mascara de cor as isola bem.
# Funciona porque a barra e opaca - o estadio ao fundo nao atravessa.
REGIAO_FORMACAO = (890, 984, 1100, 1034)


def eh_formacao(tela: Image.Image, template: Image.Image) -> bool:
    """True se a tela de formacao (escalacao) esta aparecendo.

    O quadro da formacao entra com uma animacao 3D. Enquanto ele desliza, o
    texto nao esta na posicao final e isto devolve False - o que e bom: quero
    detectar o quadro JA ASSENTADO, que e um momento consistente entre partidas.
    """
    recorte = tela.crop(REGIAO_FORMACAO)
    return diferenca_de_pixels(recorte, template) < LIMIAR_FIM_DE_JOGO


# ---------------------------------------------------------------------------
# Telas de abertura do jogo (do logo ate a escolha de lado)
# ---------------------------------------------------------------------------

# Uma regiao por tela, cada uma num pedaco que so aquela tela tem. Comparacao
# de PIXELS, como nos paineis: sao todas imagens fixas do tema "Menu 2".
# Medido nos prints da abertura de 2026-09-16: cada regiao da 0.0 na propria
# tela e 28 ou mais em qualquer outra (a mais parecida foi o aviso contra a
# escolha de lado: 30.3). O limiar de 15 fica no meio.
#
# Nenhuma regiao encosta no topo da tela: nos primeiros segundos o ReShade
# (canto superior esquerdo) e a NVIDIA (canto superior direito) mostram avisos
# por cima do jogo.
REGIOES_ABERTURA = {
    "titulo":  (600, 700, 1360, 940),   # logo "PES 2021 / THE 08/09 SEASON"
                                        # (sem o "Pressione qualquer botao",
                                        #  que pisca)
    "aviso":   (420, 270, 1500, 480),   # texto "O servico online esta indisponivel"
    "kickoff": (700, 200, 1000, 300),   # "KICK OFF" do menu principal
    "submenu": (800, 250, 1280, 420),   # "Partida local" em destaque
}


def eh_tela_de_abertura(tela: Image.Image, nome: str,
                        template: Image.Image) -> bool:
    """True se a tela `nome` (uma das chaves de REGIOES_ABERTURA) esta aparecendo."""
    recorte = tela.crop(REGIOES_ABERTURA[nome])
    return diferenca_de_pixels(recorte, template) < LIMIAR_FIM_DE_JOGO


# Escolha de lado ("Em casa" / "Fora"): as tres posicoes do controle do
# Usuario 1. Aqui NAO uso template: a linha e quase toda cinza liso, e a
# diferenca de pixels entre "controle na esquerda" e "controle no meio" deu so
# 11 a 25 - perto demais do limiar para confiar.
#
# O que diferencia de verdade e o CONTORNO CIANO do controle ativo (os
# inativos sao cinza). Medido: ~870 pixels ciano na posicao do controle e 0 nas
# outras duas, e 0 em todas as outras telas da abertura.
POSICOES_CONTROLE = {
    "esquerda": (400, 160, 560, 240),
    "meio":     (880, 160, 1040, 240),
    "direita":  (1360, 160, 1520, 240),
}
MINIMO_CIANO = 400   # medido ~870 no controle; 0 onde nao ha controle


def pixels_ciano(imagem: Image.Image) -> int:
    return sum(1 for r, g, b in imagem.convert("RGB").get_flattened_data()
               if r < 90 and g > 150 and b > 170)


def posicao_do_controle(tela: Image.Image):
    """Na escolha de lado, diz onde esta o controle: 'esquerda', 'meio',
    'direita' - ou None se nao for essa tela.

    Exige ciano em EXATAMENTE uma posicao. Duas ao mesmo tempo nao existe na
    tela real; se acontecer, e outra coisa, e na duvida a resposta e None.
    """
    achadas = [nome for nome, regiao in POSICOES_CONTROLE.items()
               if pixels_ciano(tela.crop(regiao)) >= MINIMO_CIANO]
    return achadas[0] if len(achadas) == 1 else None
