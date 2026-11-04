"""
studio.py  --  Auto_PES21 / youtube

Tudo que clica no YouTube Studio fica aqui.

Por que navegador e nao a API do YouTube: a API nao cria ESTREIA (nem
contagem regressiva, nem tema), e projeto novo na API sobe video travado como
privado ate passar por auditoria do Google.

Por que o Chrome e aberto "na mao" e so depois conectado: o Google bloqueia
login em navegador aberto direto pela automacao. Abrindo o Chrome normal, com
porta de depuracao, o login funciona e o Playwright so pega carona.

REGRA DE OURO (a mesma do Auto_PES21): na duvida, PARAR.
Cada campo preenchido e lido de volta. Se nao bater, levanta ErroStudio e o
video NAO e programado.

Os seletores ficam juntos em SELETORES. Quando o YouTube mudar a tela, e ali
que se ajusta.
"""

import re
import subprocess
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Error as ErroPlaywright
from playwright.sync_api import sync_playwright

import config

URL_STUDIO = "https://studio.youtube.com"
URL_UPLOAD = "https://www.youtube.com/upload"

SELETORES = {
    "arquivo": 'input[type="file"]',
    "titulo": "#title-textarea #textbox",
    "descricao": "#description-textarea #textbox",
    "playlist_abrir": "ytcp-video-metadata-playlists ytcp-dropdown-trigger",
    # Os componentes ytcp-* do Studio sao "cascas" sem tamanho: para o
    # Playwright eles nunca ficam visiveis. O que aparece e o paper-dialog de dentro.
    "playlist_dialogo": "ytcp-playlist-dialog tp-yt-paper-dialog",
    "playlist_pesquisa": "ytcp-playlist-dialog ytcp-search-bar input",
    "playlist_linha": "ytcp-playlist-dialog li.row",
    "playlist_concluir": "ytcp-playlist-dialog ytcp-button.done-button",
    "playlist_vazia": "ytcp-playlist-dialog >> text=/Nenhuma playlist/i",
    "nao_infantil": 'tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]',
    "proximo": "#next-button",
    "privacidade_expandir": "#first-container-expand-button",
    "privado": 'tp-yt-paper-radio-button[name="PRIVATE"]',
    "programar_expandir": "#second-container-expand-button",
    "data_abrir": "#datepicker-trigger",
    "data_campo": "ytcp-date-picker tp-yt-paper-input input",
    "hora_campo": "#time-of-day-container input",
    "estreia": "#schedule-type-checkbox",
    "configurar_estreia": 'button[aria-label="Configurar Estreia"]',
    "dialogo_estreia": "tp-yt-paper-dialog, [role='dialog']",
    "opcao_dropdown": "tp-yt-paper-item, [role='option'], [role='menuitem'], [role='menuitemradio']",
    "concluir": "#done-button",
    "ok_verificando": "ytcp-prechecks-warning-dialog #primary-action-button button",
    "fechar_aviso": ("ytcp-video-share-dialog #close-button, "
                     "ytcp-uploads-still-processing-dialog #close-button"),
}

MESES = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.",
         "jul.", "ago.", "set.", "out.", "nov.", "dez."]
MESES_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Acha um <input type=file> da janela de upload, entrando em shadow DOM se preciso.
# O do video aceita qualquer arquivo; o da miniatura aceita so imagem.
JS_ACHAR_INPUT = """
(() => {
  const serve = (el) => %s;
  const busca = (raiz) => {
    for (const el of raiz.querySelectorAll('input[type="file"]')) if (serve(el)) return el;
    for (const n of raiz.querySelectorAll('*')) {
      if (n.shadowRoot) { const r = busca(n.shadowRoot); if (r) return r; }
    }
    return null;
  };
  return busca(document);
})()
"""
JS_INPUT_VIDEO = JS_ACHAR_INPUT % 'true'
JS_INPUT_MINIATURA = JS_ACHAR_INPUT % '(el.accept || "").includes("image")'

# Confere se a miniatura entrou: devolve o texto da area e quantas imagens ela tem.
JS_CONFERIR_MINIATURA = """
(() => {
  const busca = (raiz) => {
    const el = raiz.querySelector('ytcp-thumbnail-uploader, ytcp-thumbnails-compact-editor');
    if (el) return el;
    for (const n of raiz.querySelectorAll('*')) {
      if (n.shadowRoot) { const r = busca(n.shadowRoot); if (r) return r; }
    }
    return null;
  };
  const area = busca(document);
  if (!area) return null;
  const imgs = [...area.querySelectorAll('img')].filter(i => i.src && i.clientWidth > 40);
  return {texto: (area.innerText || '').trim(), imagens: imgs.length};
})()
"""

# O link do video (https://youtu.be/<id>) que a janela de upload mostra na
# lateral assim que aceita o arquivo. So dentro da janela: atras dela, a
# lista do Studio tem links de outros videos.
JS_LINK_DO_VIDEO = r"""
(() => {
  const link = /^https:\/\/(youtu\.be\/|(www\.)?youtube\.com\/watch\?v=)[A-Za-z0-9_-]{11}/;
  const busca = (raiz) => {
    for (const a of raiz.querySelectorAll('a[href]')) if (link.test(a.href)) return a.href;
    for (const n of raiz.querySelectorAll('*')) {
      if (n.shadowRoot) { const r = busca(n.shadowRoot); if (r) return r; }
    }
    return null;
  };
  const janela = document.querySelector('ytcp-uploads-dialog');
  return janela ? busca(janela) : null;
})()
"""

# Situacao de um upload que segue numa aba depois do Programar. A janela de
# upload fechou, entao le os rotulos de progresso que sobram na pagina (a
# linha do video na lista); sem nenhum, o painel de uploads do canto.
JS_SITUACAO_UPLOAD = """
(() => {
  const textos = (sel) => {
    const r = [];
    const busca = (raiz) => {
      for (const el of raiz.querySelectorAll(sel)) {
        const t = (el.innerText || el.textContent || '').trim();
        if (t) r.push(t);
      }
      for (const n of raiz.querySelectorAll('*')) if (n.shadowRoot) busca(n.shadowRoot);
    };
    busca(document);
    return r;
  };
  const rotulos = textos('ytcp-video-upload-progress .progress-label');
  return rotulos.length ? rotulos : textos('ytcp-multi-progress-monitor, ytcp-uploads-mini-indicator');
})()
"""

MS_CURTO = 15_000
MS_LONGO = 60_000

# Depois do Programar, uma aba que passa este tempo sem mostrar NENHUM rotulo
# de progresso e dada como "nao sei": o arquivo nao e movido (pode estar
# subindo ainda) e o robo segue.
MINUTOS_SEM_SINAL = 5


def _classificar_upload(texto: str) -> str:
    """'erro', 'enviando', 'terminou' ou 'sem sinal'.

    So conta como terminado com texto POSITIVO de fim de envio. Texto
    desconhecido = sem sinal (ja errei achando que "Envio em 24%" era fim,
    porque esperava "Enviando 24%")."""
    if re.search(r"falh|erro|cancelad|rejeitad", texto, re.I):
        return "erro"
    if re.search(r"envio em|enviando|carregando|fazendo (o )?upload|uploading", texto, re.I):
        return "enviando"
    if re.search(r"conclu|processa|verifica", texto, re.I):
        return "terminou"
    return "sem sinal"


class ErroStudio(Exception):
    def __init__(self, etapa: str, detalhe: str = ""):
        super().__init__(f"[{etapa}] {detalhe}".strip())
        self.etapa = etapa
        self.detalhe = detalhe


# ==========================================================================
# CHROME
# ==========================================================================

def _chrome_respondendo() -> bool:
    url = f"http://127.0.0.1:{config.PORTA_DEPURACAO}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except OSError:
        return False


def abrir_chrome(url: str) -> None:
    """Abre o Chrome do robo (ou reaproveita, se ja estiver aberto)."""
    if _chrome_respondendo():
        return
    if not Path(config.CHROME).is_file():
        raise ErroStudio("abrir Chrome", f"nao achei o Chrome em {config.CHROME}")
    subprocess.Popen([
        config.CHROME,
        f"--remote-debugging-port={config.PORTA_DEPURACAO}",
        f"--user-data-dir={config.PERFIL_CHROME}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ])
    for _ in range(30):
        if _chrome_respondendo():
            return
        time.sleep(1)
    raise ErroStudio("abrir Chrome", "o Chrome abriu mas nao respondeu na porta de depuracao")


# ==========================================================================
# AJUDANTES
# ==========================================================================

def _normalizar(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFC", texto).split())


def formatar_data(quando: datetime) -> str:
    """Formato do campo de data do Studio em pt-BR: '16 de set. de 2026'."""
    return f"{quando.day} de {MESES[quando.month - 1]} de {quando.year}"


def _marcado(locator) -> bool:
    """Radio/checkbox do Studio: o aria-checked fica no proprio elemento ou num filho."""
    if locator.get_attribute("aria-checked") == "true":
        return True
    if locator.get_attribute("checked") is not None:
        return True
    return locator.locator('[aria-checked="true"]').count() > 0


# ==========================================================================
# STUDIO
# ==========================================================================

class Studio:
    """Uso:  with Studio() as s:  s.enviar(...)"""

    def __enter__(self):
        abrir_chrome(URL_STUDIO)
        self._pw = sync_playwright().start()
        self._navegador = self._pw.chromium.connect_over_cdp(
            f"http://127.0.0.1:{config.PORTA_DEPURACAO}")
        self._contexto = self._navegador.contexts[0]
        self.pagina = self._contexto.new_page()
        self.etapa = "inicio"
        # Videos ja programados cujo upload continua na propria aba. Cada video
        # sobe numa aba: abrir a tela de upload de novo na mesma aba cancelaria
        # o envio que ainda esta rodando.
        self.enviando: list[dict] = []
        return self

    def __exit__(self, *_):
        # O Chrome fica aberto de proposito: da para conferir o resultado, e
        # um upload que ainda nao terminou continua na aba dele.
        self._pw.stop()

    # ---------------------------------------------------------------------

    def _passo(self, etapa: str) -> None:
        self.etapa = etapa
        print(f"      - {etapa}")

    def _erro(self, detalhe: str) -> ErroStudio:
        return ErroStudio(self.etapa, detalhe)

    def _visivel(self, seletor: str, ms: int = MS_CURTO):
        loc = self.pagina.locator(seletor).first
        try:
            loc.wait_for(state="visible", timeout=ms)
        except ErroPlaywright:
            raise self._erro(f"nao apareceu na tela: {seletor}")
        return loc

    def _escrever(self, loc, texto: str) -> None:
        """Substitui o conteudo de uma caixa de texto do Studio e confere."""
        loc.click()
        self.pagina.keyboard.press("Control+A")
        self.pagina.keyboard.press("Delete")
        for i, linha in enumerate(texto.split("\n")):
            if i:
                self.pagina.keyboard.press("Enter")
            if linha:
                self.pagina.keyboard.insert_text(linha)
        self.pagina.wait_for_timeout(500)
        lido = loc.inner_text()
        if _normalizar(lido) != _normalizar(texto):
            raise self._erro(f"texto nao conferiu.\n  esperado: {texto[:120]!r}\n  na tela:  {lido[:120]!r}")

    def _escolher_dropdown(self, dialogo, rotulo: str, opcao: str) -> None:
        """Dentro de `dialogo`, abre o dropdown com o texto `rotulo` e escolhe `opcao`.

        Vai pelo texto e nao pelo nome do componente: a janela Configurar
        Estreia so e criada depois do clique, entao nao deu para ver o HTML dela.
        """
        campo = dialogo.get_by_text(rotulo, exact=True).filter(visible=True)
        if campo.count() == 0:
            raise self._erro(f'nao achei o campo "{rotulo}"')
        campo.first.click()
        item = self.pagina.locator(SELETORES["opcao_dropdown"]).filter(
            has_text=re.compile(rf"^\s*{re.escape(opcao)}\s*$")).filter(visible=True)
        try:
            item.first.wait_for(state="visible", timeout=MS_CURTO)
        except ErroPlaywright:
            raise self._erro(f'abri "{rotulo}" mas nao achei a opcao "{opcao}"')
        item.first.click()
        self.pagina.wait_for_timeout(800)
        texto = _normalizar(dialogo.inner_text())
        if not re.search(rf"{re.escape(rotulo)} {re.escape(opcao)}\b", texto):
            raise self._erro(f'"{rotulo}" nao ficou como "{opcao}"')

    # ---------------------------------------------------------------------

    def salvar_diagnostico(self) -> Path | None:
        try:
            config.PASTA_DIAGNOSTICO.mkdir(exist_ok=True)
            base = config.PASTA_DIAGNOSTICO / datetime.now().strftime("%Y%m%d_%H%M%S")
            self.pagina.screenshot(path=f"{base}.png", full_page=True)
            Path(f"{base}.html").write_text(self.pagina.content(), encoding="utf-8")
            return Path(f"{base}.png")
        except Exception:
            return None

    def verificar_login(self) -> None:
        self._passo("conferir login")
        self.pagina.goto(URL_STUDIO)
        self.pagina.wait_for_load_state("domcontentloaded")
        self.pagina.wait_for_timeout(3000)
        if "accounts.google.com" in self.pagina.url:
            raise self._erro("o Chrome do robo nao esta logado. Rode: python login.py")

    def enviar(self, video: Path, titulo: str, descricao: str, playlist: str | None,
               estreia: datetime | None, miniatura: Path | None = None,
               pausar: bool = False) -> str | None:
        """estreia=None sobe o video como PRIVADO, sem agendar nada.

        Clica em Programar sem esperar o upload chegar a 100%: o envio continua
        na aba, que fica em self.enviando, e o proximo video abre em outra.
        aguardar_uploads() espera eles no fim.

        Devolve o link do video, ou None se a janela nao mostrou (nao para o
        envio: o link pode ser colado depois no painel)."""
        if any(e["pagina"] is self.pagina for e in self.enviando):
            self.pagina = self._contexto.new_page()
        p = self.pagina

        self._passo("abrir tela de upload")
        p.goto(URL_UPLOAD)
        if "accounts.google.com" in p.url:
            raise self._erro("deslogado. Rode: python login.py")
        arquivo = p.locator(SELETORES["arquivo"]).first
        try:
            arquivo.wait_for(state="attached", timeout=MS_LONGO)
        except ErroPlaywright:
            raise self._erro("a janela de upload nao abriu")

        self._passo("selecionar arquivo")
        self._selecionar_arquivo(video)

        self.preencher(titulo, descricao, playlist, estreia, miniatura)

        if estreia is not None and estreia < datetime.now() + timedelta(minutes=config.MINUTOS_MARGEM_MINIMA):
            raise self._erro(f"a estreia ({estreia:%H:%M}) ficou perto demais do horario atual")

        link = self.ler_link()

        if pausar:
            input("      >> Confira a tela. Enter para clicar em PROGRAMAR (Ctrl+C cancela)... ")

        self.programar(privado=estreia is None)
        self.enviando.append({"pagina": p, "video": video, "estreia": estreia,
                              "ultimo": "", "sem_sinal_desde": None, "avisou_estreia": False})
        return link

    def ler_link(self) -> str | None:
        self._passo("ler o link do video")
        limite = time.time() + 30
        while time.time() < limite:
            link = self.pagina.evaluate(JS_LINK_DO_VIDEO)
            if link:
                return link
            self.pagina.wait_for_timeout(1000)
        print("      AVISO: a janela de upload nao mostrou o link do video; cole ele depois no painel.")
        return None

    def _selecionar_arquivo(self, arquivo: Path, js_campo: str = JS_INPUT_VIDEO) -> None:
        """Entrega o arquivo ao campo direto pelo Chrome (protocolo CDP).

        O set_input_files do Playwright, conectado a um Chrome ja aberto, copia
        o arquivo pela conexao e recusa mais de 50 MB - os jogos tem 2-4 GB.
        Pelo CDP so vai o CAMINHO: o proprio Chrome le o arquivo do disco.
        """
        cdp = self.pagina.context.new_cdp_session(self.pagina)
        try:
            achado = cdp.send("Runtime.evaluate", {"expression": js_campo})
            objeto = achado.get("result", {}).get("objectId")
            if not objeto:
                raise self._erro("nao achei o campo de arquivo na janela de upload")
            cdp.send("DOM.setFileInputFiles", {"files": [str(arquivo.resolve())], "objectId": objeto})
        finally:
            cdp.detach()

    def _conferir_miniatura(self, miniatura: Path) -> None:
        """Espera a miniatura aparecer na tela (pelo nome do arquivo ou pela imagem)."""
        limite = time.time() + 30
        visto = None
        while time.time() < limite:
            visto = self.pagina.evaluate(JS_CONFERIR_MINIATURA)
            if visto and (miniatura.name in visto["texto"] or visto["imagens"] > 0):
                return
            self.pagina.wait_for_timeout(1000)
        if visto is None:
            raise self._erro("nao achei a area de miniatura na tela")
        raise self._erro(f"a miniatura {miniatura.name} nao apareceu na tela "
                         f"(texto da area: {visto['texto'][:80]!r})")

    def preencher(self, titulo: str, descricao: str, playlist: str | None,
                  estreia: datetime | None, miniatura: Path | None = None) -> None:
        """Tudo da janela de upload aberta, menos o clique final."""
        p = self.pagina

        self._passo("titulo")
        self._escrever(self._visivel(SELETORES["titulo"], MS_LONGO), titulo)

        self._passo("descricao")
        self._escrever(self._visivel(SELETORES["descricao"]), descricao)

        if miniatura is not None:
            self._passo(f"miniatura: {miniatura.name}")
            self._selecionar_arquivo(miniatura, JS_INPUT_MINIATURA)
            self._conferir_miniatura(miniatura)

        if playlist is None:
            print("      - sem playlist (competicao sem playlist no canal)")
        else:
            self._playlist(playlist)

        self._passo("nao e conteudo para criancas")
        radio = self._visivel(SELETORES["nao_infantil"])
        radio.click()
        if not _marcado(radio):
            raise self._erro("a opcao nao ficou marcada")

        self._passo("avancar ate Visibilidade")
        # Na ultima etapa (Visibilidade) o botao Avancar some.
        for _ in range(6):
            proximo = p.locator(SELETORES["proximo"]).first
            if not proximo.is_visible():
                break
            proximo.click()
            p.wait_for_timeout(1500)
        else:
            raise self._erro("nao cheguei na etapa Visibilidade")

        if estreia is None:
            self._passo("visibilidade: privado")
            privado = p.locator(SELETORES["privado"]).first
            if not privado.is_visible():
                # "Salvar ou publicar" ja vem aberto; so expande se um dia nao vier.
                expandir = p.locator(SELETORES["privacidade_expandir"]).first
                if expandir.count() and expandir.is_visible():
                    expandir.click()
                    p.wait_for_timeout(800)
            privado = self._visivel(SELETORES["privado"])
            privado.click()
            if not _marcado(privado):
                raise self._erro('a opcao "Privado" nao ficou marcada')
            return

        self._agendar_estreia(estreia)

    def _playlist(self, playlist: str) -> None:
        p = self.pagina
        self._passo("playlist")
        # As vezes a janela abre com "Nenhuma playlist disponivel" mesmo com o
        # canal cheio delas: a lista nao carregou. Fecha e abre de novo.
        for tentativa in range(3):
            self._visivel(SELETORES["playlist_abrir"]).click()
            dialogo = self._visivel(SELETORES["playlist_dialogo"])
            pesquisa = p.locator(SELETORES["playlist_pesquisa"]).first
            vazia = p.locator(SELETORES["playlist_vazia"]).first
            limite = time.time() + MS_CURTO / 1000
            while time.time() < limite and not pesquisa.is_visible() and not vazia.is_visible():
                p.wait_for_timeout(500)
            if pesquisa.is_visible():
                break
            print("        a janela de playlists veio vazia; abrindo de novo")
            self._visivel(SELETORES["playlist_concluir"]).click()
            dialogo.wait_for(state="hidden", timeout=MS_CURTO)
            p.wait_for_timeout(5000 * (tentativa + 1))
        else:
            raise self._erro('a janela de playlists veio vazia ("Nenhuma playlist disponivel") 3 vezes. '
                             f'Confira no Studio se a playlist "{playlist}" existe e se a conta nao pede '
                             "para confirmar a identidade.")
        # A lista so desenha as playlists que cabem na tela: pesquisa antes.
        pesquisa.fill(playlist)
        p.wait_for_timeout(1500)
        linha = p.locator(SELETORES["playlist_linha"]).filter(
            has=p.get_by_text(playlist, exact=True))
        if linha.count() != 1:
            raise self._erro(f'achei {linha.count()} playlist(s) chamada(s) "{playlist}" (esperava 1). '
                             "Ela ja foi criada no canal?")
        caixa = linha.first.locator("ytcp-checkbox-lit")
        if not _marcado(caixa):
            caixa.click()
        if not _marcado(caixa):
            raise self._erro("a caixa da playlist nao ficou marcada")
        self._visivel(SELETORES["playlist_concluir"]).click()
        dialogo.wait_for(state="hidden", timeout=MS_CURTO)
        if _normalizar(playlist) not in _normalizar(p.locator(SELETORES["playlist_abrir"]).first.inner_text()):
            raise self._erro("a playlist nao ficou marcada")

    def _agendar_estreia(self, estreia: datetime) -> None:
        p = self.pagina
        self._passo(f"programar para {estreia:%d/%m/%Y %H:%M}")
        self._visivel(SELETORES["programar_expandir"]).click()
        self._visivel(SELETORES["data_abrir"]).click()
        campo_data = self._visivel(SELETORES["data_campo"])
        campo_data.fill(formatar_data(estreia))
        campo_data.press("Enter")
        p.wait_for_timeout(800)
        texto_data = _normalizar(p.locator(SELETORES["data_abrir"]).first.inner_text())
        if not (re.search(rf"\b{estreia.day}\b", texto_data) and str(estreia.year) in texto_data):
            raise self._erro(f"a data nao conferiu (na tela: {texto_data!r})")

        campo_hora = self._visivel(SELETORES["hora_campo"])
        campo_hora.click()
        campo_hora.fill(f"{estreia:%H:%M}")
        campo_hora.press("Enter")
        p.wait_for_timeout(800)
        if campo_hora.input_value().strip() != f"{estreia:%H:%M}":
            raise self._erro(f"a hora nao conferiu (na tela: {campo_hora.input_value()!r})")

        self._passo("definir como estreia")
        estreia_box = self._visivel(SELETORES["estreia"])
        if not _marcado(estreia_box):
            estreia_box.click()
        if not _marcado(estreia_box):
            raise self._erro("a caixa de estreia nao ficou marcada")

        self._passo("abrir Configurar Estreia")
        self._visivel(SELETORES["configurar_estreia"]).click()
        dialogo = p.locator(SELETORES["dialogo_estreia"]).filter(
            has_text="Tema da contagem regressiva").filter(visible=True).last
        try:
            dialogo.wait_for(state="visible", timeout=MS_CURTO)
        except ErroPlaywright:
            raise self._erro("a janela Configurar Estreia nao abriu")
        # A janela repete a data e a hora: segunda conferencia do agendamento.
        esperado = (f"{estreia.day} de {MESES_EXTENSO[estreia.month - 1]} de {estreia.year} "
                    f"às {estreia:%H:%M}")
        if esperado not in _normalizar(dialogo.inner_text()):
            raise self._erro(f'a janela Configurar Estreia nao mostra "{esperado}"')

        self._passo(f"tema: {config.TEMA_ESTREIA}")
        self._escolher_dropdown(dialogo, "Tema da contagem regressiva", config.TEMA_ESTREIA)

        self._passo(f"duracao da contagem: {config.CONTAGEM_REGRESSIVA}")
        self._escolher_dropdown(dialogo, "Duração da contagem regressiva", config.CONTAGEM_REGRESSIVA)

        self._passo("salvar Configurar Estreia")
        dialogo.get_by_role("button", name="Salvar", exact=True).click()
        try:
            dialogo.wait_for(state="hidden", timeout=MS_CURTO)
        except ErroPlaywright:
            raise self._erro("a janela Configurar Estreia nao fechou depois de Salvar")

    def programar(self, privado: bool = False) -> None:
        p = self.pagina
        self._passo("clicar em Salvar" if privado else "clicar em Programar")
        botao = self._visivel(SELETORES["concluir"])
        # Com o upload no comeco o botao ja vem liberado; se um dia nao vier,
        # espera o Studio liberar em vez de clicar num botao morto.
        limite = time.time() + config.MINUTOS_LIMITE_UPLOAD * 60
        avisou = False
        while botao.get_attribute("aria-disabled") == "true" or botao.get_attribute("disabled") is not None:
            if not avisou:
                print("        o botao ainda esta desabilitado; esperando o Studio liberar")
                avisou = True
            if time.time() > limite:
                raise self._erro(f"o botao nao liberou em {config.MINUTOS_LIMITE_UPLOAD} minutos")
            p.wait_for_timeout(5000)
        botao.click()
        limite = time.time() + MS_LONGO / 1000
        while time.time() < limite:
            # "Ainda estamos verificando seu conteudo" (verificacao de direitos
            # autorais em andamento): so informativo, e so clicar em Ok.
            ok_verificando = p.locator(SELETORES["ok_verificando"]).filter(visible=True)
            if ok_verificando.count():
                print("        aviso 'Ainda estamos verificando seu conteudo' -> Ok")
                ok_verificando.first.click()
                p.wait_for_timeout(1500)
                continue
            aviso = p.locator(SELETORES["fechar_aviso"]).first
            if aviso.is_visible():
                aviso.click()
                return
            if not p.locator(SELETORES["concluir"]).first.is_visible():
                return
            p.wait_for_timeout(1000)
        raise self._erro("o Studio nao confirmou (a janela continuou aberta)")

    def _situacao_upload(self, pagina) -> tuple[str, str]:
        """(estado, texto) do upload que segue numa aba; ver _classificar_upload."""
        try:
            textos = pagina.evaluate(JS_SITUACAO_UPLOAD)
        except ErroPlaywright as erro:
            return "erro", f"a aba do upload fechou ou travou ({str(erro).splitlines()[0]})"
        texto = _normalizar(" | ".join(textos or []))
        return _classificar_upload(texto), texto

    def aguardar_uploads(self) -> list[tuple[Path, bool, str]]:
        """Espera os uploads que continuaram nas abas depois do Programar.

        Devolve (video, terminou, detalhe) de cada um. terminou=False quando o
        upload deu erro ou quando nao deu para ver o fim: nesses casos o arquivo
        nao pode sair da pasta (o Chrome pode estar lendo ele ainda)."""
        resultado = []
        if not self.enviando:
            return resultado
        self.etapa = "aguardar uploads em segundo plano"
        print(f"\nEsperando {len(self.enviando)} upload(s) terminar(em) nas abas do Chrome...")
        limite = time.time() + config.MINUTOS_LIMITE_UPLOAD * 60
        while self.enviando and time.time() < limite:
            for envio in list(self.enviando):
                nome = envio["video"].stem
                estado, texto = self._situacao_upload(envio["pagina"])
                if texto and texto != envio["ultimo"]:
                    print(f"  {nome}: {texto}")
                    envio["ultimo"] = texto
                if estado == "sem sinal":
                    envio["sem_sinal_desde"] = envio["sem_sinal_desde"] or time.time()
                    if time.time() - envio["sem_sinal_desde"] > MINUTOS_SEM_SINAL * 60:
                        resultado.append((envio["video"], False,
                                          f"a aba passou {MINUTOS_SEM_SINAL} min sem mostrar o progresso"))
                        self.enviando.remove(envio)
                    continue
                envio["sem_sinal_desde"] = None
                if estado == "erro":
                    resultado.append((envio["video"], False, f"o upload deu problema: {texto}"))
                    self.enviando.remove(envio)
                elif estado == "terminou":
                    print(f"  {nome}: upload terminou")
                    resultado.append((envio["video"], True, texto))
                    self.enviando.remove(envio)
                elif (envio["estreia"] is not None and not envio["avisou_estreia"]
                      and datetime.now() + timedelta(minutes=2) > envio["estreia"]):
                    print(f"  AVISO: {nome} estreia as {envio['estreia']:%H:%M} e o upload ainda nao terminou")
                    envio["avisou_estreia"] = True
            if self.enviando:
                time.sleep(10)
        for envio in self.enviando:
            resultado.append((envio["video"], False,
                              f"o upload passou de {config.MINUTOS_LIMITE_UPLOAD} minutos"))
        self.enviando = []
        return resultado
