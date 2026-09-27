"""
abrir_jogo.py  --  Auto_PES21

Abre o PES do zero e leva o menu ate a escolha de liga da Partida local, com
o controle no MEIO (CPU x CPU). E ali que o rodar_jogos.py sabe continuar.

O caminho, medido nos prints de 2026-09-16:

    sider.exe -> PES2021.exe -> logo Konami -> titulo ("Pressione qualquer
    botao") -> "Dados do sistema carregando" -> aviso "servico online
    indisponivel" -> menu KICK OFF -> submenu "Partida local" -> escolha de
    lado (controle comeca na ESQUERDA) -> paineis de liga (Brasileirao)

POR QUE NAO E UMA SEQUENCIA FIXA DE TECLAS: o tempo de carregamento varia, e
uma tecla mandada cedo demais se perde sem aviso - dai em diante todas as
outras caem na tela errada. Aqui o script olha a tela, reconhece ONDE esta e
so entao aperta a tecla daquela tela. Logo e carregamento nao sao reconhecidos
de proposito: nelas o certo e esperar.

COMO USAR:
    python abrir_jogo.py           abre o jogo e navega ate os paineis de liga
    python abrir_jogo.py --medir   NAO abre nem aperta nada: so mostra, a cada
                                   segundo, qual tela reconheceu. Rode e abra o
                                   jogo na mao para conferir a deteccao.

O PES precisa estar FECHADO (o script nao fecha um jogo aberto por voce).
"""

# ==========================================================================
# CONFIGURACOES
# ==========================================================================

PASTA_PES   = r"D:\PES\eFootball PES 2021"
PASTA_SIDER = r"D:\PES\eFootball PES 2021\PES 2009 Remake"
PES_EXE     = PASTA_PES + r"\PES2021.exe"
SIDER_EXE   = PASTA_SIDER + r"\sider.exe"
SIDER_LOG   = PASTA_SIDER + r"\sider.log"

# O sider sorteia o menu entre as pastas de content\rndmenu. So o "Menu 2"
# bate com os templates - o "PES 2009 Menu" troca as fontes. A pasta errada
# foi tirada de la; se ela voltar, o script para antes de abrir o jogo.
MENU_CERTO = "Menu 2"
PASTA_MENUS = PASTA_SIDER + r"\content\rndmenu"

SEGUNDOS_APOS_ABRIR_SIDER = 5     # o sider precisa estar de pe antes do PES
SEGUNDOS_LIMITE_LOG_SIDER = 90    # espera o sider registrar o menu sorteado
SEGUNDOS_LIMITE_ABERTURA  = 300   # do .exe ate os paineis de liga

# Tela sem reconhecer por este tempo = algo inesperado. Logo e "carregando"
# duram bem menos; o aviso de conexao pode demorar, mas depois ele aparece e
# conta como reconhecido.
SEGUNDOS_SEM_RECONHECER = 120

INTERVALO_OLHAR = 1.0      # de quanto em quanto tempo fotografar a tela
PAUSA_APOS_TECLA = 1.5     # deixa a animacao da troca de tela terminar

# Depois de apertar a tecla de uma tela, espero ela SAIR. Se continuar a mesma
# por este tempo, a tecla se perdeu (ex.: o titulo ainda nao aceitava input) e
# eu aperto de novo - no maximo MAX_REPETICOES vezes.
#
# Isto existe para NAO apertar duas vezes durante uma transicao lenta: um
# Enter a mais no submenu cairia na escolha de lado e confirmaria com o
# controle na ESQUERDA - voce viraria jogador em vez de ser CPU x CPU.
SEGUNDOS_ANTES_DE_REPETIR = 6
MAX_REPETICOES = 3

PASTA_DIAGNOSTICO = "diagnostico_abertura"

# ==========================================================================

import ctypes
import csv
import io
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from PIL import Image

import teclado
import visao

TEMPLATE_LIGA_CASA = "templates/liga_casa_brasileirao.png"

# user32.dll e a parte do Windows que cuida de janelas e teclado.
user32 = ctypes.windll.user32
SW_RESTORE = 9
VK_ALT = 0x12
KEYEVENTF_KEYUP = 0x0002

# Se o PES nao estiver na frente, tento traze-lo de novo so a cada tantos
# segundos - insistir sem parar ficaria tocando Alt o tempo todo.
SEGUNDOS_ENTRE_TENTATIVAS_FOCO = 5

# Tela reconhecida -> tecla. A ordem nao importa: quem decide o que fazer e a
# tela que esta aparecendo, nao o passo anterior.
ACOES = {
    "titulo":          ("confirmar", teclado.confirmar),
    "aviso":           ("confirmar", teclado.confirmar),
    "kickoff":         ("confirmar", teclado.confirmar),
    "submenu":         ("confirmar", teclado.confirmar),
    "lado_esquerda":   ("direita",   teclado.direita),
    "lado_direita":    ("esquerda",  teclado.esquerda),
    "lado_meio":       ("confirmar", teclado.confirmar),
}


def detalhe(mensagem: str) -> None:
    print(f"      {mensagem}")


def salvar_diagnostico(tela: Image.Image, rotulo: str) -> Path:
    pasta = Path(PASTA_DIAGNOSTICO)
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{rotulo}_{datetime.now():%H%M%S}.png"
    tela.save(destino)
    return destino


# --------------------------------------------------------------------------
# Reconhecer a tela
# --------------------------------------------------------------------------

def carregar_templates() -> dict:
    templates = {nome: visao.carregar_template(f"templates/abertura_{nome}.png")
                 for nome in visao.REGIOES_ABERTURA}
    templates["liga"] = visao.mascara_texto_verde(Image.open(TEMPLATE_LIGA_CASA))
    return templates


def reconhecer(tela: Image.Image, templates: dict):
    """Diz em que tela da abertura o jogo esta, ou None se nao reconhecer.

    'ligas' e o destino final: o painel casa com o Brasileirao em destaque.
    """
    for nome in visao.REGIOES_ABERTURA:
        if visao.eh_tela_de_abertura(tela, nome, templates[nome]):
            return nome

    lado = visao.posicao_do_controle(tela)
    if lado:
        return f"lado_{lado}"

    mascara = visao.mascara_texto_verde(tela.crop(visao.REGIAO_NOME_CASA))
    if visao.tem_texto(mascara) and \
            visao.sobreposicao(mascara, templates["liga"]) >= visao.LIMIAR_NOME_TIME:
        return "ligas"
    return None


# --------------------------------------------------------------------------
# Abrir os programas
# --------------------------------------------------------------------------

def esta_rodando(exe: str) -> bool:
    """Pergunta ao Windows (tasklist) se ha um processo com esse nome."""
    return bool(pids_do_processo(exe))


def pids_do_processo(exe: str) -> set:
    """Os numeros de processo (PID) de todos os processos com esse nome."""
    nome = Path(exe).name.lower()
    saida = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {Path(exe).name}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="ignore",
    ).stdout
    return {int(campos[1]) for campos in csv.reader(io.StringIO(saida))
            if len(campos) > 1 and campos[0].lower() == nome}


def pid_da_janela(janela) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(janela, ctypes.byref(pid))
    return pid.value


def janela_principal(pids: set):
    """A maior janela visivel que pertence a um desses processos, ou None."""
    candidatas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def olhar(janela, _):
        if user32.IsWindowVisible(janela) and pid_da_janela(janela) in pids:
            r = wintypes.RECT()
            user32.GetWindowRect(janela, ctypes.byref(r))
            candidatas.append(((r.right - r.left) * (r.bottom - r.top), janela))
        return True

    user32.EnumWindows(olhar, 0)
    return max(candidatas)[1] if candidatas else None


def em_primeiro_plano(pids: set) -> bool:
    """True se a janela da frente (a que recebe as teclas) e desses processos."""
    return pid_da_janela(user32.GetForegroundWindow()) in pids


def trazer_para_frente(pids: set) -> bool:
    """Poe a janela desses processos na frente. Devolve se deu certo.

    Existe por causa do primeiro teste real: o PES abriu ATRAS do terminal.
    O script passou 2 minutos fotografando a area de trabalho, e as teclas
    teriam ido para o PowerShell.

    O toque no Alt e um truque conhecido: o Windows so deixa um programa
    trocar a janela da frente logo depois de uma tecla, para impedir que
    qualquer programa roube o foco enquanto voce digita. Alt sozinho nao faz
    nada no PES nem no terminal.
    """
    janela = janela_principal(pids)
    if janela is None:
        return False
    if user32.IsIconic(janela):              # minimizada
        user32.ShowWindow(janela, SW_RESTORE)
    user32.keybd_event(VK_ALT, 0, 0, 0)
    user32.keybd_event(VK_ALT, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(janela)
    time.sleep(1)
    return em_primeiro_plano(pids)


def abrir_programa(exe: str) -> None:
    """Abre o programa como um clique duplo faria, na pasta dele.

    os.startfile em vez de subprocess porque imita o clique duplo: se o
    programa pedir permissao de administrador, o Windows mostra o aviso
    normal em vez de dar erro.
    """
    os.startfile(exe, cwd=str(Path(exe).parent))


def menu_sorteado_no_log(desde: float):
    """Le no sider.log qual menu o sider sorteou nesta abertura.

    So vale um log gravado DEPOIS de `desde`: o arquivo antigo, da abertura
    anterior, tambem tem essa linha e daria uma resposta velha.
    """
    log = Path(SIDER_LOG)
    try:
        if log.stat().st_mtime < desde:
            return None
        for linha in log.read_text(errors="ignore").splitlines():
            if "Current Menu is =" in linha:
                return linha.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def conferir_preparo() -> bool:
    for exe in (SIDER_EXE, PES_EXE):
        if not Path(exe).is_file():
            print(f"ERRO: nao achei {exe}")
            return False
    try:
        carregar_templates()
    except FileNotFoundError as erro:
        print(f"ERRO: {erro}")
        return False

    pastas = sorted(p.name for p in Path(PASTA_MENUS).iterdir() if p.is_dir()) \
        if Path(PASTA_MENUS).is_dir() else []
    if pastas and pastas != [MENU_CERTO]:
        print(f"ERRO: o sider vai sortear entre {pastas}.")
        print(f"So '{MENU_CERTO}' funciona com os templates. Tire as outras de:")
        print(f"  {PASTA_MENUS}")
        return False

    if esta_rodando(PES_EXE):
        print("ERRO: o PES ja esta aberto. Feche o jogo e rode de novo.")
        return False
    return True


def abrir_sider_e_pes() -> bool:
    print("  [1] Abrindo o sider")
    if esta_rodando(SIDER_EXE):
        detalhe("ja estava aberto - aproveitando")
    else:
        abrir_programa(SIDER_EXE)
        time.sleep(SEGUNDOS_APOS_ABRIR_SIDER)
        # So aviso, nao paro: com o PES aberto o sider ja foi visto FORA da
        # lista de processos, entao a ausencia dele nao prova nada. A prova de
        # que ele agiu e o sider.log atualizado, conferido no passo [3].
        if esta_rodando(SIDER_EXE):
            detalhe("OK")
        else:
            detalhe("AVISO - o sider nao aparece na lista de processos.")

    print("  [2] Abrindo o PES")
    inicio = time.time()
    abrir_programa(PES_EXE)

    print("  [3] Conferindo o menu sorteado pelo sider")
    limite = inicio + SEGUNDOS_LIMITE_LOG_SIDER
    while time.time() < limite:
        menu = menu_sorteado_no_log(inicio)
        if menu is not None:
            if menu != MENU_CERTO:
                detalhe(f"FALHOU - o sider sorteou '{menu}', e so '{MENU_CERTO}' "
                        f"funciona. Feche o PES e confira a pasta rndmenu.")
                return False
            detalhe(f"OK - '{menu}'")
            return True
        time.sleep(1)
    # Sem a linha no log nao da para saber, mas tambem nao e motivo para parar:
    # se o tema estiver errado, nenhuma tela vai ser reconhecida e o passo
    # seguinte para com foto.
    detalhe("AVISO - o sider.log nao registrou o menu; sigo pela imagem.")
    return True


# --------------------------------------------------------------------------
# Navegar pelas telas
# --------------------------------------------------------------------------

def navegar_ate_as_ligas(templates: dict) -> bool:
    print("  [4] Navegando ate os paineis de liga")
    limite = time.time() + SEGUNDOS_LIMITE_ABERTURA
    ultimo_reconhecimento = time.time()
    ultima_acao = None          # tela em que apertei a ultima tecla
    momento_da_acao = 0.0
    repeticoes = 0
    ultima_tentativa_foco = 0.0

    while time.time() < limite:
        # O PES precisa estar NA FRENTE: a foto e da tela visivel e as teclas
        # vao para a janela da frente. Sem ele la, nao fotografo nem aperto.
        pids = pids_do_processo(PES_EXE)
        if not pids:
            print(" " * 70, end="\r")
            detalhe("FALHOU - o PES fechou (o processo sumiu).")
            return False
        if not em_primeiro_plano(pids):
            if time.time() - ultima_tentativa_foco >= SEGUNDOS_ENTRE_TENTATIVAS_FOCO:
                ultima_tentativa_foco = time.time()
                if trazer_para_frente(pids):
                    print(" " * 70, end="\r")
                    detalhe("trouxe a janela do PES para a frente")
                    continue
            parado = time.time() - ultimo_reconhecimento
            if parado > SEGUNDOS_SEM_RECONHECER:
                print(" " * 70, end="\r")
                destino = salvar_diagnostico(visao.capturar_tela(), "pes_atras")
                detalhe(f"FALHOU - {parado:.0f}s sem conseguir trazer o PES "
                        f"para a frente.")
                detalhe(f"foto: {destino}")
                return False
            print(f"      o PES nao esta na frente, tentando trazer... "
                  f"{parado:4.0f}s", end="\r", flush=True)
            time.sleep(INTERVALO_OLHAR)
            continue

        tela = visao.capturar_tela()
        nome = reconhecer(tela, templates)

        if nome == "ligas":
            print(" " * 70, end="\r")
            detalhe("OK - painel casa na lista de ligas, Brasileirao em destaque")
            return True

        if nome is None:
            parado = time.time() - ultimo_reconhecimento
            if parado > SEGUNDOS_SEM_RECONHECER:
                print(" " * 70, end="\r")
                destino = salvar_diagnostico(tela, "tela_desconhecida")
                detalhe(f"FALHOU - {parado:.0f}s sem reconhecer nenhuma tela.")
                detalhe(f"foto do que estava na tela: {destino}")
                return False
            print(f"      esperando (logo/carregamento)... {parado:4.0f}s",
                  end="\r", flush=True)
            time.sleep(INTERVALO_OLHAR)
            continue

        ultimo_reconhecimento = time.time()

        # Ainda na tela em que acabei de apertar: e transicao, nao tecla
        # perdida. So repito depois de um bom tempo parado nela.
        if nome == ultima_acao:
            if time.time() - momento_da_acao < SEGUNDOS_ANTES_DE_REPETIR:
                time.sleep(INTERVALO_OLHAR)
                continue
            repeticoes += 1
            if repeticoes >= MAX_REPETICOES:
                print(" " * 70, end="\r")
                destino = salvar_diagnostico(tela, f"tecla_sem_efeito_{nome}")
                detalhe(f"FALHOU - apertei {MAX_REPETICOES}x na tela '{nome}' "
                        f"e ela nao saiu.")
                detalhe("A janela do PES esta em primeiro plano? "
                        "As teclas podem estar indo para outro programa.")
                detalhe(f"foto: {destino}")
                return False
        else:
            repeticoes = 0

        rotulo, apertar = ACOES[nome]
        print(" " * 70, end="\r")
        extra = f" (de novo, {repeticoes + 1}a vez)" if repeticoes else ""
        detalhe(f"tela '{nome}' -> {rotulo}{extra}")
        apertar()
        ultima_acao = nome
        momento_da_acao = time.time()
        time.sleep(PAUSA_APOS_TECLA)

    destino = salvar_diagnostico(visao.capturar_tela(), "tempo_esgotado")
    detalhe(f"FALHOU - passaram {SEGUNDOS_LIMITE_ABERTURA}s sem chegar nas ligas.")
    detalhe(f"foto: {destino}")
    return False


def abrir_ate_as_ligas() -> bool:
    """Tudo junto. E esta funcao que o rodar_jogos.py chama."""
    if not conferir_preparo():
        return False
    templates = carregar_templates()
    return abrir_sider_e_pes() and navegar_ate_as_ligas(templates)


# --------------------------------------------------------------------------
# Modo --medir
# --------------------------------------------------------------------------

def medir() -> int:
    """So observa. Grava tambem num arquivo, para eu ler depois sem voce copiar."""
    templates = carregar_templates()
    pasta = Path(PASTA_DIAGNOSTICO)
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"medicao_{datetime.now():%H%M%S}.txt"
    print(f"Medindo (Ctrl+C para parar). Gravando em {arquivo}\n")

    with open(arquivo, "w", encoding="utf-8") as saida:
        anterior = "?"
        inicio = time.time()
        while True:
            tela = visao.capturar_tela()
            difs = {nome: visao.diferenca_de_pixels(
                        tela.crop(regiao), templates[nome])
                    for nome, regiao in visao.REGIOES_ABERTURA.items()}
            ciano = {pos: visao.pixels_ciano(tela.crop(regiao))
                     for pos, regiao in visao.POSICOES_CONTROLE.items()}
            nome = reconhecer(tela, templates)

            linha = (f"{time.time() - inicio:6.1f}s  {str(nome):14s}  "
                     + "  ".join(f"{k}={v:5.1f}" for k, v in difs.items())
                     + "  ciano=" + "/".join(str(v) for v in ciano.values())
                     + f"  tamanho={tela.size[0]}x{tela.size[1]}"
                     + f"  pes_na_frente={em_primeiro_plano(pids_do_processo(PES_EXE))}")
            saida.write(linha + "\n")
            saida.flush()
            # Na tela so mostro quando muda, para nao virar uma cascata.
            if nome != anterior:
                print(linha)
                anterior = nome
            time.sleep(INTERVALO_OLHAR)


def main() -> int:
    if "--medir" in sys.argv:
        return medir()

    print("=" * 66)
    print("  AUTO_PES21  --  abrir o jogo")
    print("=" * 66)
    if not abrir_ate_as_ligas():
        print("\nPAREI. O jogo pode ter ficado aberto no meio do caminho.")
        return 1
    print("\nPronto: o PES esta nos paineis de liga, controle no meio.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except KeyboardInterrupt:
        print("\n\nInterrompido por voce (Ctrl+C).")
        codigo = 1
    sys.exit(codigo)
