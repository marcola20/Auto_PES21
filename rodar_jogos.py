# ==========================================================================
# CONFIGURACOES
# ==========================================================================

# A lista de partidas: (time da casa, time de fora).
# Os nomes precisam existir em times.py. Acento e maiuscula sao opcionais.
#
# Jogo que NAO e da liga ganha um terceiro item com o nome da competicao, que
# vai para o nome do video no lugar da serie: ("Santos", "Cruzeiro", "Supercopa")
# -> "Santos vs Cruzeiro ｜ Supercopa.mp4". Importa porque o site da liga
# descobre a competicao pelo nome do video: sem isso, uma final da Supercopa
# entre dois times da Serie A seria procurada na Serie A.
JOGOS = [
    ("Santos", "Cruzeiro", "Supercopa"),
]

CONFLITOS_DE_UNIFORME = {
    "Vasco":   ["Corinthians", "Botafogo", "Coritiba", "Santos",
                "Figueirense", "Sport", "São Paulo"],
    "Vitória": ["Corinthians", "Botafogo", "Coritiba", "Santos",
                "Figueirense", "Sport", "São Paulo", "Flamengo"],
}

PASTA_GRAVACOES = r"C:\Users\Marcola\Videos\NVIDIA\eFootball PES 2021"
EXTENSOES_VIDEO = (".mp4", ".mkv", ".mov", ".avi")

SEGUNDOS_CONTAGEM = 10       # tempo para voltar ao PES no inicio
MINUTOS_LIMITE_PARTIDA = 30  # se passar disso sem fim de jogo, aborta

SEGUNDOS_APOS_CONFIRMAR  = 1.5  # espera a tela trocar depois de um Enter

SEGUNDOS_ANTES_DE_GRAVAR = [80, 70, 50]

SEGUNDOS_LIMITE_FORMACAO = 180
SEGUNDOS_APOS_PARAR      = 8    # espera a NVIDIA fechar o arquivo
SEGUNDOS_BUSCA_EXTRA     = 25   # procura o video novo por mais esse tempo

# O Windows nao aceita "|" em nome de arquivo. Esta e a barra "cheia" (U+FF5C),
# que e permitida e na tela fica igual: "Corinthians vs Vitória ｜ Série B".
SEPARADOR_SERIE = " ｜ "

TENTATIVAS_RENOMEAR                = 10
SEGUNDOS_ENTRE_TENTATIVAS_RENOMEAR = 3

INTERVALO_CHECAGEM_FIM = 2.0    # de quanto em quanto tempo olhar a tela
PAUSA_APOS_PAINEL      = 2.5    # espera depois de confirmar um painel do jogo
PAUSA_MENU_UNIFORME    = 0.8    # entre as teclas dentro da tela "Uniforme"
PAUSA_APOS_REPLAY      = 1.2    # espera depois de pular um replay (troca rapido)

# Quanto tempo um replay precisa ficar na tela antes de o script mexer nele.
#
# Isto existe para NAO tocar no replay de gol durante a partida. Naquele
# contexto o Enter nao avanca o replay: ele ABRE o editor de replay do PES
# (aquele com "Salvar replay" e controles de reproducao), e o jogo trava ali.
#
# A distincao e a mesma que ja uso no fim de jogo: replay de gol termina
# sozinho em poucos segundos, enquanto os melhores momentos do final ficam
# esperando input para sempre. Se o script so age depois de o replay
# PERSISTIR, ele nunca encosta no replay de gol.
# Medido na pratica: um replay de gol ja passou de 25s na tela e o script
# encostou nele, abrindo o editor. 50s da folga sem tornar o fim de partida
# lento demais. Se acontecer de novo, aumente - o custo de errar para cima e
# so alguns segundos a mais de video no final.
SEGUNDOS_ESPERAR_REPLAY = 50

# Se a tela ficar PARADA por este tempo durante a partida, algo deu errado.
# Uma partida rodando nunca congela: ou a bola se mexe, ou a torcida, ou o
# relogio. Tela imovel por um minuto significa que o jogo esta esperando algo
# que o script nao sabe que precisa fazer.
SEGUNDOS_TELA_PARADA = 60
PASTA_DIAGNOSTICO = "diagnostico_travou"

# Antes de parar a gravacao, mostrar a aba de EVENTOS DA PARTIDA no video.
# So funciona depois de TECLA_R1 estar definida em teclado.py; enquanto for
# None, o script pula esta etapa inteira.
VEZES_R1 = 2                     # quantas abas avancar a partir da inicial
VEZES_BAIXO_NOS_EVENTOS = 10     # rolar a lista de eventos ate o fim
PAUSA_BAIXO_NOS_EVENTOS = 1.0    # entre um Baixo e outro: devagar, para o
                                 # video mostrar a lista inteira, e nao so o
                                 # topo e o fim
SEGUNDOS_MOSTRANDO_EVENTOS = 8   # quanto tempo deixar a aba na tela

# ==========================================================================

import sys
import time
from pathlib import Path

from PIL import Image

import abrir_jogo
import navegar
import teclado
import times
import visao

TEMPLATE_FIM       = "templates/fim_de_jogo.png"
TEMPLATE_INTERVALO = "templates/intervalo_escuro.png"
TEMPLATE_REPLAY    = "templates/replay_caixa.png"
TEMPLATE_LIGA      = "templates/liga_fora_brasileirao.png"
TEMPLATE_LIGA_CASA = "templates/liga_casa_brasileirao.png"
TEMPLATE_INICIO    = "templates/prejogo_inicio.png"
TEMPLATE_FORMACAO  = "templates/formacao.png"


# --------------------------------------------------------------------------
# Verificacao de tela
# --------------------------------------------------------------------------

def tela_confere(caminho_template: str, regiao: tuple, minimo: int = 100) -> tuple:
    """Confere se a tela atual bate com um template, pela mascara de texto verde.

    Serve para qualquer tela cujo elemento-chave seja texto verde: o nome da
    liga destacada, o botao "Inicio", etc. Devolve (bateu, semelhanca).
    """
    alvo = visao.mascara_texto_verde(Image.open(caminho_template))
    atual = visao.ler_regiao(regiao, minimo=minimo)
    if not visao.tem_texto(atual, minimo):
        return False, 0.0
    semelhanca = visao.sobreposicao(atual, alvo)
    return semelhanca >= visao.LIMIAR_NOME_TIME, semelhanca


# --------------------------------------------------------------------------
# Arquivos de video
# --------------------------------------------------------------------------

def listar_videos(pasta: Path) -> set:
    """Todos os videos da pasta e subpastas. Set porque so importa QUAIS existem."""
    return {
        c for c in pasta.rglob("*")
        if c.is_file() and c.suffix.lower() in EXTENSOES_VIDEO
    }


def esperar_video_novo(pasta: Path, antes: set):
    """Espera aparecer um video que nao existia antes. Devolve None se nao vier."""
    time.sleep(SEGUNDOS_APOS_PARAR)
    limite = time.time() + SEGUNDOS_BUSCA_EXTRA
    while True:
        novos = listar_videos(pasta) - antes
        if novos:
            return sorted(novos)[0]
        if time.time() > limite:
            return None
        time.sleep(2)


def esperar_arquivo_estabilizar(caminho: Path, tentativas: int = 15) -> bool:
    """Espera o arquivo parar de crescer, sinal de que a NVIDIA terminou de salvar."""
    anterior = -1
    for _ in range(tentativas):
        try:
            atual = caminho.stat().st_size
        except OSError:
            return False
        if atual == anterior and atual > 0:
            return True
        anterior = atual
        time.sleep(1)
    return False


def renomear_video(caminho: Path, casa: str, fora: str, competicao: str = None):
    """Troca o nome que a NVIDIA deu ao video pelo nome do jogo.

    'eFootball PES 2021 2026.09.16 - 11.07.14.13.mp4'
        -> 'Corinthians vs Vitória ｜ Série B.mp4'

    A serie so entra quando os dois times sao da mesma: um jogo A x B (ou com
    um time que so completa a liga) nao e de serie nenhuma. Se o jogo for de
    outra competicao (ex. "Supercopa"), ela entra no lugar da serie.

    Devolve o caminho novo, ou None se nao conseguiu. NUNCA levanta erro: o
    video ja esta salvo, e um nome feio nao pode derrubar o loop.
    """
    base = f"{times.nome_oficial(casa)} vs {times.nome_oficial(fora)}"
    serie = times.serie_do_time(casa)
    if competicao:
        base += f"{SEPARADOR_SERIE}{competicao}"
    elif serie and serie == times.serie_do_time(fora):
        base += f"{SEPARADOR_SERIE}Série {serie}"

    # Mesmo jogo gravado de novo: nao sobrescreve, numera.
    destino = caminho.with_name(base + caminho.suffix)
    numero = 2
    while destino.exists():
        destino = caminho.with_name(f"{base} ({numero}){caminho.suffix}")
        numero += 1

    # Se a NVIDIA ainda estiver segurando o arquivo, o Windows recusa a troca
    # de nome (PermissionError). Da mais algumas chances antes de desistir.
    for tentativa in range(TENTATIVAS_RENOMEAR):
        try:
            return caminho.rename(destino)
        except OSError as erro:
            ultimo_erro = erro
            time.sleep(SEGUNDOS_ENTRE_TENTATIVAS_RENOMEAR)
    detalhe(f"(nao consegui renomear o video: {ultimo_erro})")
    return None


# --------------------------------------------------------------------------
# Passos de uma partida
# --------------------------------------------------------------------------

def detalhe(mensagem: str) -> None:
    print(f"      {mensagem}")


def falhar_com_foto(mensagem: str, rotulo: str) -> None:
    """Registra a falha e guarda a foto da tela naquele instante.

    Toda verificacao de tela que aborta passa por aqui. Sem a foto, uma falha
    vira so um numero no terminal e o diagnostico depende de voce reproduzir o
    problema na minha frente - que e exatamente o que mais custou tempo neste
    projeto.
    """
    detalhe(mensagem)
    destino = salvar_diagnostico(visao.capturar_tela(), rotulo)
    detalhe(f"foto do que estava na tela: {destino}")


def salvar_diagnostico(tela, rotulo: str) -> Path:
    """Guarda uma foto da tela quando algo da errado.

    Sem isso, uma falha vira so uma mensagem no terminal e voce fica sem saber
    em QUE tela o jogo estava parado. Com a foto, da para descobrir depois.
    """
    pasta = Path(PASTA_DIAGNOSTICO)
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{rotulo}_{time.strftime('%H%M%S')}.png"
    tela.save(destino)
    return destino


def esperar_mostrando(segundos: float, rotulo: str) -> None:
    """Espera contando na tela, para esperas longas nao parecerem travamento."""
    restante = int(segundos)
    while restante > 0:
        print(f"      {rotulo} {restante // 60}:{restante % 60:02d}",
              end="\r", flush=True)
        time.sleep(1)
        restante -= 1
    time.sleep(segundos - int(segundos))   # a fracao de segundo que sobrou
    print(" " * 70, end="\r")


def preparar_painel_casa(max_voltas: int = 3) -> bool:
    """Leva o menu ate a LISTA DE TIMES do painel casa, venha de onde vier.

    A selecao tem varios niveis, e a execucao anterior pode ter parado em
    qualquer um deles:

        lista de times CASA      <- onde eu quero chegar
        lista de ligas CASA      -> Confirmar entra na lista de times
        time da casa CONFIRMADO,
          foco no painel FORA    -> Voltar devolve o foco para o painel casa

    Antes eu exigia o estado certo e abortava no resto. Mas nenhum desses
    estados e ambiguo: em todos eu sei onde estou e qual e a saida. Exigir que
    voce arrumasse a tela na mao era rigidez, nao seguranca.
    """
    for tentativa in range(max_voltas + 1):
        nome, s = navegar.qual_time_esta_selecionado("casa")
        if nome:
            if tentativa:
                detalhe(f"painel casa pronto apos {tentativa} passo(s) - "
                        f"cursor em '{nome}' ({s:.3f})")
            return True

        bateu, s = tela_confere(TEMPLATE_LIGA_CASA, visao.REGIAO_NOME_CASA)
        if bateu:
            detalhe(f"painel casa na lista de LIGAS ({s:.3f}) - entrando nos times")
            teclado.confirmar()
            time.sleep(SEGUNDOS_APOS_CONFIRMAR)
            continue

        if tentativa < max_voltas:
            detalhe("nao reconheci o painel casa - voltando um nivel")
            teclado.voltar()
            time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    falhar_com_foto(
        f"FALHOU - nao consegui chegar na lista de times do painel casa "
        f"depois de {max_voltas} tentativa(s)", "painel_casa")
    detalhe("Se o TEMA VISUAL do jogo mudou, rode:  python calibrar_times.py casa")
    return False


def garantir_lista_de_times(painel: str) -> bool:
    """Garante que o painel esta na LISTA DE TIMES, e nao na de LIGAS.

    Cada painel tem dois niveis: liga -> time. Dependendo de onde a execucao
    anterior parou, o jogo pode reabrir num nivel ou no outro, e a diferenca
    nao e culpa de ninguem - e so o estado em que o menu ficou.

    Antes o script simplesmente desistia quando nao reconhecia um time. Agora
    ele faz o que uma pessoa faria: se o que esta destacado e a LIGA certa,
    confirma para entrar na lista de times e segue.
    """
    nome, _ = navegar.qual_time_esta_selecionado(painel)
    if nome:
        return True

    template = TEMPLATE_LIGA_CASA if painel == "casa" else TEMPLATE_LIGA
    bateu, s = tela_confere(template, visao.regiao_do_painel(painel))
    if not bateu:
        detalhe(f"FALHOU - o painel '{painel}' nao mostra nem time nem a liga "
                f"certa (semelhanca com a liga: {s:.3f})")
        detalhe("Causas possiveis, da mais provavel para a menos:")
        detalhe("  - o PES nao esta na tela de selecao de times")
        detalhe("  - o painel errado esta ativo")
        detalhe(f"  - o TEMA VISUAL do jogo mudou: os templates guardam o")
        detalhe(f"    formato das letras, entao outra fonte nao bate mais.")
        detalhe(f"    Nesse caso rode:  python calibrar_times.py {painel}")
        salvar_diagnostico(visao.capturar_tela(), f"painel_{painel}")
        return False

    detalhe(f"o painel '{painel}' estava na lista de LIGAS "
            f"(Brasileirao, {s:.3f}) - entrando na lista de times")
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    nome, _ = navegar.qual_time_esta_selecionado(painel)
    if not nome:
        detalhe("FALHOU - confirmei a liga mas continuo sem ver time nenhum")
        return False
    return True


def escolher_times(casa: str, fora: str) -> bool:
    """Seleciona os dois times. Espera comecar na LISTA DE TIMES do painel casa."""
    print("  [1] Time da casa")
    if not preparar_painel_casa():
        return False
    if not navegar.ir_para_time("casa", casa, falar=lambda m: print("  " + m)):
        return False
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    # Confirmado o time da casa, o foco cai na LISTA DE LIGAS do painel fora.
    print("  [2] Liga do visitante")
    bateu, s = tela_confere(TEMPLATE_LIGA, visao.REGIAO_NOME_FORA)
    if not bateu:
        falhar_com_foto(
            f"FALHOU - a liga destacada nao e o Brasileirao (semelhanca {s:.3f})",
            "liga_visitante")
        return False
    detalhe(f"OK - Brasileirao Serie A (semelhanca {s:.3f})")
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    print("  [3] Time visitante")
    if not navegar.ir_para_time("fora", fora, falar=lambda m: print("  " + m)):
        return False
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)
    return True


def precisa_ajustar_uniforme(casa: str, fora: str) -> bool:
    """Diz se esta partida cai num dos pares de uniformes que se confundem.

    Confere nos dois sentidos: tanto faz quem esta em casa, o par e o mesmo.
    Compara com os nomes normalizados para aceitar acento e maiuscula.
    """
    a, b = times.normalizar(casa), times.normalizar(fora)
    for base, adversarios in CONFLITOS_DE_UNIFORME.items():
        base = times.normalizar(base)
        rivais = {times.normalizar(r) for r in adversarios}
        if (a == base and b in rivais) or (b == base and a in rivais):
            return True
    return False


def ajustar_uniforme() -> bool:
    """Troca o uniforme do time de BAIXO (linha "Fora") na tela "Uniforme".

    Caminho, partindo da tela pre-jogo com "Inicio" destacado:
        <- <-     Inicio -> Estadio -> Uniforme
        Enter     entra na tela Uniforme
        v         seleciona a linha "Fora" (o time de baixo)
        <-        troca o uniforme
        Esc       volta para a tela pre-jogo
        -> ->     Uniforme -> Estadio -> Inicio

    No fim eu confiro que voltei mesmo para a tela pre-jogo com "Inicio"
    destacado. O que eu NAO consigo conferir e se o uniforme trocou de fato:
    para isso precisaria de um template da propria tela "Uniforme".
    """
    detalhe("uniformes se confundem nesta partida - ajustando")

    teclado.esquerda(2)
    time.sleep(PAUSA_MENU_UNIFORME)
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    teclado.baixo()
    time.sleep(PAUSA_MENU_UNIFORME)
    teclado.esquerda()
    time.sleep(PAUSA_MENU_UNIFORME)

    teclado.voltar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)
    teclado.direita(2)
    time.sleep(PAUSA_MENU_UNIFORME)

    # Mesma ancora do garantir_botao_inicio: se os dois "Direita" nao caírem
    # no lugar, ainda da para achar o botao contando desde a ponta esquerda.
    return garantir_botao_inicio()


def espera_antes_de_gravar(indice: int) -> int:
    """Quantos segundos esperar antes de gravar, na partida numero `indice`.

    Passou do fim da lista? Repete o ultimo valor. Assim uma fila de 20 jogos
    funciona com uma lista de 3 valores, sem eu precisar repetir o ultimo
    dezessete vezes.
    """
    if not SEGUNDOS_ANTES_DE_GRAVAR:
        return 0
    return SEGUNDOS_ANTES_DE_GRAVAR[min(indice - 1, len(SEGUNDOS_ANTES_DE_GRAVAR) - 1)]


def esperar_a_formacao() -> bool:
    """Espera a tela de escalacao aparecer. Devolve False se nao aparecer.

    Por que isto substitui o cronometro: o carregamento fica mais rapido a cada
    partida (cache de disco), e mais rapido de um jeito que nenhuma lista de
    segundos acompanha - na pratica, a 3a partida ja caiu no lugar errado com o
    valor que parecia certo. Esperar a TELA e imune a isso: nao importa se o
    carregamento levou 40 ou 90 segundos, a gravacao comeca no mesmo ponto.
    """
    template = visao.carregar_template(TEMPLATE_FORMACAO)
    inicio = time.time()
    limite = inicio + SEGUNDOS_LIMITE_FORMACAO

    while time.time() < limite:
        if visao.eh_formacao(visao.capturar_tela(), template):
            print(" " * 70, end="\r")
            detalhe(f"formacao detectada ({time.time() - inicio:.0f}s de carregamento)")
            return True
        print(f"      esperando a formacao aparecer... "
              f"{time.time() - inicio:3.0f}s", end="\r", flush=True)
        time.sleep(1)

    print(" " * 70, end="\r")
    return False


def esperar_ate_a_hora_de_gravar(indice: int) -> None:
    """Segura o script ate o momento de comecar a gravar.

    Usa a deteccao da formacao quando o template existe; senao, cai no
    cronometro antigo. Assim o projeto continua funcionando enquanto o template
    nao foi capturado.
    """
    if not Path(TEMPLATE_FORMACAO).is_file():
        segundos = espera_antes_de_gravar(indice)
        detalhe(f"(sem {TEMPLATE_FORMACAO} - usando o cronometro de {segundos}s)")
        esperar_mostrando(segundos, "carregando a partida, gravacao comeca em")
        return

    if esperar_a_formacao():
        return

    # Nao achei a formacao. Gravo assim mesmo: o risco aqui e um video mal
    # cortado, nao uma partida perdida - e abortar custaria mais do que isso.
    # Se a partida realmente nao comecou, as redes de seguranca de dentro do
    # acompanhar_partida pegam depois.
    detalhe(f"AVISO - formacao nao apareceu em {SEGUNDOS_LIMITE_FORMACAO}s, "
            f"gravando assim mesmo")


def garantir_botao_inicio() -> bool:
    """Deixa o cursor no botao "Inicio" da tela pre-jogo.

    A fileira de botoes e [Uniforme] [Estadio] [Inicio] [Plano de jogo] ... e
    ela ROLA: o ultimo aparece cortado na tela. Entao, se o cursor voltar numa
    posicao diferente da esperada, a fileira desliza e outro botao ocupa o
    lugar onde eu procuro o "Inicio".

    Em vez de exigir que ele ja esteja certo, faco o mesmo que na lista de
    times: ANCORO na ponta esquerda (varios "Esquerda" seguidos, que param no
    primeiro botao), CONTO dois para a direita, e CONFIRO por imagem.
    """
    bateu, s = tela_confere(TEMPLATE_INICIO, visao.REGIAO_PREJOGO, minimo=80)
    if bateu:
        detalhe(f"OK - botao 'Inicio' destacado (semelhanca {s:.3f})")
        return True

    detalhe(f"'Inicio' nao esta no lugar esperado (semelhanca {s:.3f}) - ancorando")
    teclado.esquerda(5)          # gruda no primeiro botao ("Uniforme")
    time.sleep(PAUSA_MENU_UNIFORME)
    teclado.direita(2)           # Uniforme -> Estadio -> Inicio
    time.sleep(PAUSA_MENU_UNIFORME)

    bateu, s = tela_confere(TEMPLATE_INICIO, visao.REGIAO_PREJOGO, minimo=80)
    if bateu:
        detalhe(f"OK - 'Inicio' alcancado pela ancora (semelhanca {s:.3f})")
        return True

    falhar_com_foto(
        f"FALHOU - nao achei o botao 'Inicio' nem ancorando (semelhanca {s:.3f})",
        "tela_prejogo")
    return False


def iniciar_partida(casa: str, fora: str, indice: int) -> bool:
    """Confere que chegou na tela pre-jogo, ajusta uniforme se precisar, e comeca."""
    print("  [4] Tela pre-jogo")
    if not garantir_botao_inicio():
        return False

    if precisa_ajustar_uniforme(casa, fora) and not ajustar_uniforme():
        return False

    teclado.confirmar()
    esperar_ate_a_hora_de_gravar(indice)
    return True


def acompanhar_partida() -> bool:
    """Acompanha a partida do apito inicial ate o fim, confirmando o intervalo.

    A partida nao corre sozinha: no INTERVALO o jogo para e espera dois
    confirmes, um em cada painel:

        painel VERDE "Intervalo"   -> confirmar
        painel ESCURO "Intervalo"  -> confirmar (botao "2o tempo")

    O fim de jogo tem a MESMA estrutura de dois paineis, mas ali o painel
    escuro e o nosso sinal de parada - ele fica esperando input para sempre,
    entao e impossivel perder.

    Por isso a ordem das checagens importa: o fim de jogo e testado PRIMEIRO,
    para nunca confirmarmos por engano aquele painel. Confirmar nele apertaria
    "Jogar novamente" e comecaria uma partida nova por cima da gravacao.
    """
    template_fim = visao.carregar_template(TEMPLATE_FIM)
    template_intervalo = visao.carregar_template(TEMPLATE_INTERVALO)
    template_replay = visao.carregar_template(TEMPLATE_REPLAY)

    inicio = time.time()
    limite = inicio + MINUTOS_LIMITE_PARTIDA * 60
    confirmados = 0
    replays = 0

    # Para detectar tela congelada. Guardo uma versao BEM reduzida da tela: a
    # comparacao fica barata e mudancas pequenas (um jogador andando ao fundo)
    # ainda aparecem, enquanto uma tela realmente parada da diferenca zero.
    tela_anterior = None
    momento_da_ultima_mudanca = inicio

    # Desde quando um replay esta na tela sem parar. None = nao tem replay.
    replay_visivel_desde = None

    def minutos():
        return (time.time() - inicio) / 60

    def limpar_linha():
        print(" " * 70, end="\r")

    while time.time() < limite:
        tela = visao.capturar_tela()

        # A tela ainda esta se mexendo? (miniatura de 192x108 basta)
        miniatura = tela.resize((192, 108))
        if tela_anterior is None or \
                visao.diferenca_de_pixels(miniatura, tela_anterior) > 1.5:
            momento_da_ultima_mudanca = time.time()
        tela_anterior = miniatura

        # 1) Fim de jogo - sempre testado primeiro.
        if visao.eh_fim_de_jogo(tela, template_fim):
            limpar_linha()
            detalhe(f"fim de jogo detectado ({minutos():.1f} min, "
                    f"{confirmados} painel(eis) e {replays} replay(s) no caminho)")
            return True

        # 2) Painel escuro do intervalo: confirmar leva ao 2o tempo.
        if visao.eh_intervalo(tela, template_intervalo):
            limpar_linha()
            detalhe(f"intervalo: painel escuro, indo para o 2o tempo ({minutos():.1f} min)")
            teclado.confirmar()
            confirmados += 1
            time.sleep(PAUSA_APOS_PAINEL)
            continue

        # 3) Painel verde (Intervalo ou Fim de jogo): confirmar avanca.
        if visao.ha_painel_verde(tela):
            # Olho a tela de novo antes de apertar. O painel verde dura poucos
            # segundos, e se ele tiver virado o painel escuro de FIM DE JOGO
            # bem nesse instante, o confirme cairia em "Jogar novamente".
            if visao.eh_fim_de_jogo(visao.capturar_tela(), template_fim):
                limpar_linha()
                detalhe(f"fim de jogo detectado ({minutos():.1f} min)")
                return True
            limpar_linha()
            detalhe(f"painel verde na tela, confirmando ({minutos():.1f} min)")
            teclado.confirmar()
            confirmados += 1
            time.sleep(PAUSA_APOS_PAINEL)
            continue

        # 4) Replay. Aqui o script ESPERA antes de agir, de proposito.
        #    Replay de gol some sozinho; se eu apertar Enter nele, abro o
        #    editor de replay e travo a partida. Melhor momento do final fica
        #    parado esperando - e so nesse caso que o tempo de espera estoura.
        if visao.eh_replay(tela, template_replay):
            if replay_visivel_desde is None:
                replay_visivel_desde = time.time()

            parado_ha = time.time() - replay_visivel_desde
            if parado_ha < SEGUNDOS_ESPERAR_REPLAY:
                print(f"      replay na tela ha {parado_ha:4.0f}s "
                      f"(so mexo depois de {SEGUNDOS_ESPERAR_REPLAY}s)",
                      end="\r", flush=True)
                time.sleep(INTERVALO_CHECAGEM_FIM)
                continue

            replays += 1
            limpar_linha()
            detalhe(f"replay parado ha {parado_ha:.0f}s, avancando "
                    f"(#{replays}, {minutos():.1f} min)")
            teclado.confirmar()
            replay_visivel_desde = None
            time.sleep(PAUSA_APOS_REPLAY)
            continue

        # Saiu da tela de replay sozinho: era replay de gol, e eu fiz certo
        # em nao ter mexido nele.
        replay_visivel_desde = None

        # 5) Nada reconhecido E a tela nao se mexe ha um tempao: travou numa
        #    tela que eu nao sei tratar. Melhor parar agora, guardando a foto
        #    para diagnostico, do que ficar esperando ate o limite de 30 min.
        parada_ha = time.time() - momento_da_ultima_mudanca
        if parada_ha > SEGUNDOS_TELA_PARADA:
            limpar_linha()
            destino = salvar_diagnostico(tela, "tela_travada")
            detalhe(f"FALHOU - a tela esta parada ha {parada_ha:.0f}s "
                    f"({minutos():.1f} min de partida)")
            detalhe(f"foto do que estava na tela: {destino}")
            return False

        print(f"      jogando... {minutos():5.1f} min"
              f"   (parada ha {parada_ha:4.0f}s)", end="\r", flush=True)
        time.sleep(INTERVALO_CHECAGEM_FIM)

    limpar_linha()
    destino = salvar_diagnostico(visao.capturar_tela(), "tempo_esgotado")
    detalhe(f"FALHOU - {MINUTOS_LIMITE_PARTIDA} min sem detectar o fim de jogo")
    detalhe(f"foto do que estava na tela: {destino}")
    return False


def mostrar_eventos_da_partida() -> bool:
    """No fim de jogo, troca para a aba de eventos e deixa ela um tempo na tela.

    Serve para o VIDEO terminar com um resumo da partida. Roda antes de parar a
    gravacao, e por isso uma falha aqui NAO derruba o jogo: a partida ja foi
    gravada, e perder um resumo bonito nao justifica perder o video.

    Confere o efeito em vez de confiar nas teclas: le o titulo da aba antes e
    depois, e so segue se ele realmente mudou.
    """
    if teclado.TECLA_R1 is None:
        return True   # etapa desativada ate a tecla ser descoberta

    antes = visao.ler_titulo_da_aba()
    if not visao.tem_texto(antes):
        detalhe("AVISO - nao achei o titulo da aba, pulando o resumo")
        return False

    teclado.apertar(teclado.TECLA_R1, VEZES_R1, pausa=0.6)
    time.sleep(1.0)

    depois = visao.ler_titulo_da_aba()
    parecenca = visao.sobreposicao(antes, depois)
    if not visao.tem_texto(depois) or parecenca >= visao.LIMIAR_NOME_TIME:
        detalhe(f"AVISO - a aba nao mudou (semelhanca {parecenca:.3f}), "
                f"pulando o resumo")
        return False

    # Varios "Baixo" em vez de um: um clique so nao chega ao fim da lista, e o
    # cursor simplesmente para quando acaba - descer demais nao faz mal.
    # Um de cada vez e com pausa: em rajada a lista pulava do topo direto para
    # o fim, e os eventos do meio nunca apareciam no video.
    teclado.apertar(teclado.TECLA_BAIXO, VEZES_BAIXO_NOS_EVENTOS,
                    pausa=PAUSA_BAIXO_NOS_EVENTOS)
    detalhe(f"mostrando os eventos da partida por {SEGUNDOS_MOSTRANDO_EVENTOS}s")
    time.sleep(SEGUNDOS_MOSTRANDO_EVENTOS)
    return True


def voltar_para_selecao() -> bool:
    """Do menu de fim de jogo, volta para a lista de times do painel casa.

    O menu de fim de jogo abre com "Jogar novamente" marcado. Uma Direita leva a
    "Selecionar time", que cai direto na selecao - sem passar pelo menu
    principal. De la, dois "Voltar" sobem ate a lista de times da casa:
        lista de times FORA  ->  lista de ligas FORA  ->  lista de times CASA
    """
    print("  [7] Voltando para a selecao de times")
    teclado.direita()
    time.sleep(0.4)
    teclado.confirmar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR * 2)

    teclado.voltar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)
    teclado.voltar()
    time.sleep(SEGUNDOS_APOS_CONFIRMAR)

    # Se o cursor esta marcando um time reconhecivel no painel casa, chegamos
    # no lugar certo. Isso tambem confirma que os dois "Voltar" pegaram.
    # Mesma tolerancia do inicio: a volta pode parar em qualquer nivel.
    if not preparar_painel_casa():
        return False
    nome, s = navegar.qual_time_esta_selecionado("casa")
    detalhe(f"OK - painel casa ativo, cursor em '{nome}' ({s:.3f})")
    return True


def rodar_um_jogo(casa: str, fora: str, indice: int, total: int,
                  pasta: Path, competicao: str = None) -> tuple:
    """Roda uma partida. Devolve (seguiu_tudo_bem, gravou_o_video).

    Sao DUAS informacoes porque elas falham separado: a partida pode ter sido
    gravada direitinho e so a volta para o proximo jogo dar errado. Antes eu
    devolvia um unico True/False, e ai o resumo dizia "0 jogos gravados" mesmo
    com o video salvo na pasta - um relatorio errado bem na hora em que voce
    mais precisa saber o que aconteceu.
    """
    print("\n" + "=" * 66)
    print(f"  JOGO {indice}/{total}:  {casa}  x  {fora}")
    print("=" * 66)

    if not escolher_times(casa, fora):
        return False, False
    if not iniciar_partida(casa, fora, indice):
        return False, False

    antes = listar_videos(pasta)
    print(f"  [5] Iniciando gravacao ({len(antes)} videos ja na pasta)")
    teclado.alternar_gravacao()

    if not acompanhar_partida():
        detalhe("(a gravacao pode ter ficado LIGADA - confira na NVIDIA)")
        return False, False

    # Ainda gravando: mostra o resumo da partida no final do video.
    mostrar_eventos_da_partida()

    print("  [6] Parando gravacao")
    teclado.alternar_gravacao()

    novo = esperar_video_novo(pasta, antes)
    if novo is None:
        detalhe("FALHOU - nenhum video novo apareceu na pasta.")
        return False, False

    esperar_arquivo_estabilizar(novo)
    tamanho = novo.stat().st_size / (1024 * 1024)
    detalhe(f"OK - {novo.name}  ({tamanho:.0f} MB)")
    # Daqui para baixo o video ja esta salvo: o que falhar agora nao apaga isso.

    renomeado = renomear_video(novo, casa, fora, competicao)
    if renomeado is not None:
        detalhe(f"Renomeado para: {renomeado.name}")

    # No ultimo jogo nao ha proximo, entao nao precisa voltar para a selecao.
    if indice < total and not voltar_para_selecao():
        return False, True
    return True, True


# --------------------------------------------------------------------------

def contagem_regressiva(segundos: int) -> None:
    for restante in range(segundos, 0, -1):
        print(f"  Volte para o PES...  {restante:2d}s ", end="\r", flush=True)
        time.sleep(1)
    print("  Comecando!                       ")


def jogos_da_fila() -> list:
    """JOGOS sempre como (casa, fora, competicao); competicao None = liga."""
    return [(j[0], j[1], j[2] if len(j) > 2 else None) for j in JOGOS]


def conferir_preparo(pasta: Path) -> bool:
    """Checagens antes de comecar, para falhar cedo em vez de no meio do loop."""
    if not pasta.is_dir():
        print(f"ERRO: pasta de gravacoes nao existe:\n  {pasta}")
        return False

    for template in (TEMPLATE_FIM, TEMPLATE_INTERVALO, TEMPLATE_REPLAY,
                     TEMPLATE_LIGA, TEMPLATE_LIGA_CASA, TEMPLATE_INICIO):
        if not Path(template).is_file():
            print(f"ERRO: falta o template {template}")
            return False

    # Nomes e templates de TODOS os jogos, conferidos antes do primeiro apito:
    # melhor descobrir um nome errado agora do que na 8a partida, de madrugada.
    for casa, fora, _ in jogos_da_fila():
        for painel, nome in (("casa", casa), ("fora", fora)):
            try:
                times.indice_do_time(nome)
                navegar.mascara_do_template(painel, nome)
            except (ValueError, FileNotFoundError) as erro:
                print(f"ERRO na lista de jogos: {erro}")
                return False
    return True


def main() -> int:
    pasta = Path(PASTA_GRAVACOES)

    print("=" * 66)
    print("  AUTO_PES21  --  loop completo")
    print("=" * 66)
    print(f"\n{len(JOGOS)} jogo(s) na fila:")
    for i, (casa, fora, competicao) in enumerate(jogos_da_fila(), 1):
        extra = f"  ({competicao})" if competicao else ""
        print(f"  {i:2d}. {casa}  x  {fora}{extra}")

    print()
    if not conferir_preparo(pasta):
        return 1
    print("Preparo conferido: pasta, templates e nomes dos times estao OK.")

    if "--abrir" in sys.argv:
        # Com --abrir o script parte do PES FECHADO: abre sider e jogo e para
        # nos paineis de liga, que o primeiro jogo ja sabe atravessar.
        print("\nModo --abrir: o PES precisa estar FECHADO.\n")
        if not abrir_jogo.abrir_ate_as_ligas():
            print("\nPAREI antes do primeiro jogo: o jogo nao chegou nos paineis de liga.")
            return 1
    else:
        print("\nO PES precisa estar na LISTA DE TIMES do painel 'Em casa', com o")
        print("controle ja deixado no meio na tela de escolha de lado.")
        print("(Ou rode com --abrir, com o PES fechado, para abrir o jogo sozinho.)\n")
        contagem_regressiva(SEGUNDOS_CONTAGEM)

    gravados = 0
    for i, (casa, fora, competicao) in enumerate(jogos_da_fila(), 1):
        seguiu, gravou = rodar_um_jogo(casa, fora, i, len(JOGOS), pasta,
                                       competicao)
        if gravou:
            gravados += 1

        if not seguiu:
            print("\n" + "!" * 66)
            print(f"  PAREI no jogo {i}/{len(JOGOS)}  ({casa} x {fora})")
            print("!" * 66)
            print(f"  Videos gravados nesta sessao: {gravados}")
            if gravou:
                # Distincao que importa: o video DESTE jogo esta salvo, a falha
                # foi so na passagem para o proximo. Nao precisa regravar.
                print(f"  O video do jogo {i} FOI salvo - a falha foi na volta")
                print(f"  para a selecao de times. Nao precisa refazer esse jogo.")
                print(f"  Para continuar, tire os {i} primeiros da lista JOGOS.")
            print("  Confira o estado da gravacao na NVIDIA antes de rodar de novo.")
            return 1

    print("\n" + "=" * 66)
    print(f"  TERMINOU: {gravados}/{len(JOGOS)} jogos gravados.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        print("ATENCAO: a gravacao pode ter ficado ligada. Confira na NVIDIA.")
        codigo = 1
    sys.exit(codigo)
