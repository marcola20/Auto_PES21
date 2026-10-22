// Painel do Auto_PES21. Conversa com o painel.py (mesmo endereco) por /api/*.

const $ = (seletor) => document.querySelector(seletor);

const estado = {
  times: [],
  rodadas: [],       // da competicao escolhida
  fila: [],
  tarefa: { numero: 0, linhas: [], rodando: false },
};

// ------------------------------------------------------------------ util

async function api(caminho, corpo) {
  const opcoes = corpo === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  };
  const resposta = await fetch(caminho, opcoes);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || `Erro ${resposta.status}`);
  return dados;
}

let temporizadorAviso;
function avisar(texto, erro = false) {
  const el = $("#aviso");
  el.textContent = texto;
  el.classList.toggle("erro", erro);
  el.classList.remove("escondido");
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => el.classList.add("escondido"), erro ? 6000 : 3000);
}

function criar(tag, atributos = {}, ...filhos) {
  const el = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "class") el.className = valor;
    else if (chave.startsWith("on")) el.addEventListener(chave.slice(2), valor);
    else if (valor === true) el.setAttribute(chave, "");
    else if (valor !== false && valor != null) el.setAttribute(chave, valor);
  }
  for (const filho of filhos.flat()) {
    if (filho == null) continue;
    el.append(filho instanceof Node ? filho : document.createTextNode(filho));
  }
  return el;
}

function confronto(casa, fora) {
  return criar("span", { class: "confronto" }, casa, criar("span", { class: "x" }, "x"), fora);
}

function dataCurta(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

// ------------------------------------------------------------------ abas

document.querySelectorAll(".abas button").forEach((botao) => {
  botao.addEventListener("click", () => mostrarAba(botao.dataset.aba));
});

function mostrarAba(nome) {
  document.querySelectorAll(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  document.querySelectorAll(".painel-aba").forEach((s) => s.classList.toggle("escondido", s.id !== `aba-${nome}`));
  if (nome === "videos") carregarVideos();
  if (nome === "config") carregarConfig();
  try { localStorage.setItem("aba", nome); } catch {}
}

// ------------------------------------------------------------------ competicoes e rodadas

async function carregarCompeticoes() {
  const select = $("#competicao");
  const aviso = $("#aviso-site");
  select.innerHTML = "<option>Buscando no site… (pode levar até 1 min se ele estiver dormindo)</option>";
  select.disabled = true;
  aviso.classList.add("escondido");
  try {
    const ligas = await api("/api/competicoes");
    select.innerHTML = "";
    for (const liga of ligas) select.append(criar("option", { value: liga.id }, liga.nome));
    if (!ligas.length) select.append(criar("option", {}, "Nenhuma competição ativa no site"));
    select.disabled = !ligas.length;
    let anterior = null;
    try { anterior = localStorage.getItem("competicao"); } catch {}
    if (anterior && ligas.some((l) => l.id === anterior)) select.value = anterior;
    if (ligas.length) await carregarRodadas();
  } catch (erro) {
    select.innerHTML = "<option>Sem competições</option>";
    aviso.textContent = erro.message;
    aviso.classList.remove("escondido");
    $("#partidas").innerHTML = "";
  }
}

async function carregarRodadas() {
  const liga = $("#competicao").value;
  try { localStorage.setItem("competicao", liga); } catch {}
  const select = $("#rodada");
  select.disabled = true;
  select.innerHTML = "<option>Carregando…</option>";
  $("#partidas").innerHTML = "";
  try {
    estado.rodadas = await api(`/api/rodadas?liga=${encodeURIComponent(liga)}`);
  } catch (erro) {
    avisar(erro.message, true);
    estado.rodadas = [];
  }
  select.innerHTML = "";
  estado.rodadas.forEach((r, i) => {
    const pendentes = r.partidas.filter((p) => p.situacao === "pendente").length;
    const nome = r.titulo || `Rodada ${r.numero}`;
    const data = r.data ? ` · ${dataCurta(r.data)}` : "";
    const resumo = pendentes ? ` · ${pendentes} pendente(s)` : " · completa";
    select.append(criar("option", { value: i }, nome + data + resumo));
  });
  select.disabled = !estado.rodadas.length;
  // Abre na primeira rodada que ainda tem jogo para fazer.
  const primeira = estado.rodadas.findIndex((r) => r.partidas.some((p) => p.situacao === "pendente"));
  select.value = primeira >= 0 ? primeira : Math.max(0, estado.rodadas.length - 1);
  mostrarPartidas();
}

const TEXTO_SITUACAO = {
  pendente: "pendente",
  gravado: "já gravado",
  jogado: "jogado",
  sem_time: "time fora do PES",
};

function mostrarPartidas() {
  const lista = $("#partidas");
  lista.innerHTML = "";
  const rodada = estado.rodadas[$("#rodada").value];
  if (!rodada) {
    lista.append(criar("li", { class: "vazio" }, "Nenhuma rodada."));
    atualizarBotaoAdicionar();
    return;
  }
  rodada.partidas.forEach((p, i) => {
    const inativa = p.situacao === "sem_time";
    let selo = TEXTO_SITUACAO[p.situacao];
    if (p.situacao === "jogado") selo = p.wo ? "W.O." : `jogado ${p.placar}`;
    const naFila = estado.fila.some((j) => j.casa === p.casa && j.fora === p.fora);
    const id = `partida-${i}`;
    const titulo = inativa
      ? `O site chama de "${p.casa_site} x ${p.fora_site}" e não achei ${!p.casa ? p.casa_site : p.fora_site} no times.py`
      : null;
    lista.append(criar("li", { class: `partida${inativa ? " inativa" : ""}`, title: titulo },
      criar("label", { for: id },
        criar("input", {
          type: "checkbox", id, "data-indice": i, disabled: inativa,
          checked: p.situacao === "pendente" && !naFila,
          onchange: atualizarBotaoAdicionar,
        }),
        confronto(p.casa || p.casa_site, p.fora || p.fora_site),
        naFila ? criar("span", { class: "selo ok" }, "na fila") : null,
        criar("span", { class: `selo ${p.situacao}` }, selo),
      ),
    ));
  });
  atualizarBotaoAdicionar();
}

function marcados() {
  return [...document.querySelectorAll("#partidas input:checked")].map((c) => Number(c.dataset.indice));
}

function atualizarBotaoAdicionar() {
  const n = marcados().length;
  const botao = $("#adicionar-marcados");
  botao.disabled = !n;
  botao.textContent = n ? `Adicionar ${n} à fila` : "Adicionar à fila";
}

function marcar(filtro) {
  const rodada = estado.rodadas[$("#rodada").value];
  document.querySelectorAll("#partidas input").forEach((c) => {
    if (!c.disabled) c.checked = filtro(rodada.partidas[c.dataset.indice]);
  });
  atualizarBotaoAdicionar();
}

$("#competicao").addEventListener("change", carregarRodadas);
$("#rodada").addEventListener("change", mostrarPartidas);
$("#recarregar-competicoes").addEventListener("click", carregarCompeticoes);
$("#marcar-pendentes").addEventListener("click", () => marcar((p) => p.situacao === "pendente"));
$("#desmarcar-todos").addEventListener("click", () => marcar(() => false));

$("#adicionar-marcados").addEventListener("click", async () => {
  const rodada = estado.rodadas[$("#rodada").value];
  const competicao = $("#competicao").selectedOptions[0]?.textContent || null;
  const novos = marcados().map((i) => rodada.partidas[i]).map((p) => ({
    casa: p.casa, fora: p.fora, competicao,
    rodada: rodada.titulo || `Rodada ${rodada.numero}`,
  }));
  await adicionarNaFila(novos);
});

// ------------------------------------------------------------------ jogo avulso

function preencherAvulso() {
  for (const id of ["#avulso-casa", "#avulso-fora"]) {
    const select = $(id);
    select.innerHTML = "";
    for (const t of estado.times) select.append(criar("option", { value: t }, t));
  }
  $("#avulso-fora").selectedIndex = Math.min(1, estado.times.length - 1);
}

$("#adicionar-avulso").addEventListener("click", async () => {
  const casa = $("#avulso-casa").value;
  const fora = $("#avulso-fora").value;
  if (casa === fora) return avisar("Escolha dois times diferentes.", true);
  await adicionarNaFila([{ casa, fora, competicao: $("#avulso-competicao").value.trim() || null, rodada: null }]);
});

// ------------------------------------------------------------------ fila

async function carregarFila() {
  try {
    estado.fila = await api("/api/fila");
  } catch (erro) {
    avisar(erro.message, true);
  }
  mostrarFila();
}

async function salvarFila(fila) {
  try {
    estado.fila = await api("/api/fila", { fila });
  } catch (erro) {
    avisar(erro.message, true);
  }
  mostrarFila();
  if (estado.rodadas.length) mostrarPartidas();
}

async function adicionarNaFila(novos) {
  const igual = (a, b) => a.casa === b.casa && a.fora === b.fora && (a.competicao || null) === (b.competicao || null);
  const filtrados = novos.filter((n) => !estado.fila.some((j) => igual(j, n)));
  const repetidos = novos.length - filtrados.length;
  if (!filtrados.length) return avisar("Esses jogos já estão na fila.");
  await salvarFila([...estado.fila, ...filtrados]);
  avisar(`${filtrados.length} jogo(s) na fila${repetidos ? ` (${repetidos} já estava(m))` : ""}.`);
}

function mostrarFila() {
  const lista = $("#fila");
  lista.innerHTML = "";
  $("#contagem-fila").textContent = estado.fila.length;
  if (!estado.fila.length) {
    lista.append(criar("li", { class: "vazio" }, "Fila vazia. Marque jogos da rodada acima e clique em “Adicionar à fila”."));
  }
  estado.fila.forEach((j, i) => {
    const origem = [j.competicao, j.rodada].filter(Boolean).join(" · ");
    lista.append(criar("li", { class: "item-fila" },
      criar("div", { class: "jogo-fila" },
        confronto(j.casa, j.fora),
        origem ? criar("span", { class: "origem", title: origem }, origem) : null),
      j.gravado ? criar("span", { class: "selo gravado", title: "Já existe um vídeo ou .json com esse nome na pasta de vídeos" }, "gravado") : null,
      criar("span", { class: "mover" },
        criar("button", { title: "Subir", "aria-label": "Subir", disabled: i === 0, onclick: () => mover(i, -1) }, "↑"),
        criar("button", { title: "Descer", "aria-label": "Descer", disabled: i === estado.fila.length - 1, onclick: () => mover(i, 1) }, "↓"),
        criar("button", { class: "tirar", title: "Tirar da fila", "aria-label": "Tirar da fila", onclick: () => tirar(i) }, "✕"),
      ),
    ));
  });
  const n = estado.fila.length;
  $("#detalhe-rodar").textContent = n ? `${n} jogo(s) da fila` : "fila vazia";
  atualizarBotoesAcao();
}

function mover(i, delta) {
  const fila = [...estado.fila];
  const [jogo] = fila.splice(i, 1);
  fila.splice(i + delta, 0, jogo);
  salvarFila(fila);
}

function tirar(i) {
  salvarFila(estado.fila.filter((_, k) => k !== i));
}

$("#tirar-gravados").addEventListener("click", () => {
  const sobram = estado.fila.filter((j) => !j.gravado);
  if (sobram.length === estado.fila.length) return avisar("Nenhum jogo da fila foi gravado ainda.");
  salvarFila(sobram);
});

$("#limpar-fila").addEventListener("click", () => {
  if (estado.fila.length && confirm("Tirar todos os jogos da fila?")) salvarFila([]);
});

// ------------------------------------------------------------------ videos

const TEXTO_JSON = {
  ok: "pronto para enviar",
  revisar: "revisar",
  ilegivel: ".json com erro",
};

async function carregarVideos() {
  const corpo = $("#videos");
  corpo.innerHTML = "<tr><td colspan='3' class='nota'>Carregando…</td></tr>";
  let dados;
  try {
    dados = await api("/api/videos");
  } catch (erro) {
    corpo.innerHTML = "";
    return avisar(erro.message, true);
  }
  $("#pasta-videos").textContent = dados.existe ? dados.pasta : `A pasta não existe: ${dados.pasta}. Confira na aba Configuração.`;
  corpo.innerHTML = "";
  if (!dados.jogos.length) {
    corpo.append(criar("tr", {}, criar("td", { colspan: 3, class: "nota" }, "Nenhum vídeo nem .json na pasta.")));
    return;
  }
  for (const jogo of [...dados.jogos].reverse()) {
    const j = jogo.json;
    let classe, texto;
    if (!j) { classe = "pendente"; texto = "falta extrair"; }
    else if (j.envio === "enviado") { classe = "enviado"; texto = "enviado"; }
    else if (j.envio === "mudou" && j.status === "ok") { classe = "mudou"; texto = "mudou — reenviar"; }
    else if (j.status === "ok") { classe = "ok"; texto = TEXTO_JSON.ok; }
    else if (j.status === "revisar") { classe = "revisar"; texto = "revisar"; }
    else { classe = "erro"; texto = TEXTO_JSON[j.status] || String(j.status); }

    const arquivos = [jogo.video, j?.arquivo].filter(Boolean).join(" + ");
    corpo.append(criar("tr", {},
      criar("td", {}, criar("div", {}, jogo.nome), criar("div", { class: "arquivos" }, arquivos)),
      criar("td", {}, j?.placar || "—",
        j?.avisos?.length ? criar("ul", { class: "avisos" }, j.avisos.map((a) => criar("li", {}, a))) : null),
      criar("td", {}, criar("span", { class: `selo ${classe}` }, texto)),
    ));
  }
}

$("#recarregar-videos").addEventListener("click", carregarVideos);

// ------------------------------------------------------------------ configuracao

async function carregarConfig() {
  try {
    mostrarConfig(await api("/api/config"));
  } catch (erro) {
    avisar(erro.message, true);
  }
}

function mostrarConfig(config) {
  $("#arquivo-ini").textContent = config.arquivo;
  for (const [chave, valor] of Object.entries(config.valores)) {
    const input = document.getElementById(chave);
    if (input && document.activeElement !== input) input.value = valor;
  }
  for (const [chave, c] of Object.entries(config.conferencia)) {
    const el = document.querySelector(`[data-campo="${chave}"] .conferencia`);
    if (!el) continue;
    el.textContent = c.texto;
    el.className = "conferencia" + (c.ok === true ? " ok" : c.ok === false ? " falha" : "");
  }
  $("#token").placeholder = config.conferencia.token.ok ? "já guardado — deixe vazio para manter" : "cole o token aqui";
}

$("#form-config").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const valores = Object.fromEntries(new FormData(evento.target));
  try {
    const config = await api("/api/config", valores);
    $("#token").value = "";
    mostrarConfig(config);
    $("#config-salva").textContent = `Salvo às ${new Date().toLocaleTimeString("pt-BR")}`;
    avisar("Configuração salva.");
  } catch (erro) {
    avisar(erro.message, true);
  }
});

// ------------------------------------------------------------------ tarefas

async function iniciar(tarefa, extra = {}) {
  try {
    const dados = await api("/api/tarefa", { tarefa, ...extra });
    estado.tarefa = { ...dados, linhas: [] };
    $("#fotos").innerHTML = "";
    receberTarefa(dados);
    acompanhar();
  } catch (erro) {
    avisar(erro.message, true);
  }
}

$("#acao-rodar").addEventListener("click", () => {
  const n = estado.fila.length;
  if (!n) return avisar("A fila está vazia: adicione jogos na aba Jogos.", true);
  const gravados = estado.fila.filter((j) => j.gravado).length;
  const extra = gravados ? `\n\n${gravados} deles já tem vídeo na pasta e vai ser gravado de novo.` : "";
  const ok = confirm(
    `Rodar ${n} jogo(s)?\n\n` +
    "• PES fechado: abro o sider e o jogo.\n" +
    "• PES aberto na seleção de times ou no menu: continuo de lá.\n" +
    "• PES aberto em outra tela: não aperto nada e aviso.\n\n" +
    "Depois de OK, o PES vem para a frente. Não mexa no mouse nem no teclado até acabar." + extra);
  if (ok) iniciar("rodar");
});
$("#acao-extrair").addEventListener("click", () => iniciar("extrair"));
$("#acao-simular").addEventListener("click", () => iniciar("enviar", { simular: true }));
$("#acao-enviar").addEventListener("click", () => {
  if (confirm("Enviar para o site os resultados novos ou corrigidos?\n\n(.json em \"revisar\" é pulado.)")) iniciar("enviar");
});
$("#acao-parar").addEventListener("click", async () => {
  const aviso = estado.tarefa.nome === "rodar"
    ? "Parar agora? Se estiver no meio de uma partida, a gravação da NVIDIA pode ficar ligada."
    : "Parar a tarefa agora?";
  if (!confirm(aviso)) return;
  try { await api("/api/tarefa/parar", {}); } catch (erro) { avisar(erro.message, true); }
});

function classeDaLinha(linha) {
  if (linha.startsWith("[painel]")) return "l-painel";
  if (/\b(ERRO|FALHOU|PAREI|Com erro)\b/.test(linha)) return "l-erro";
  if (/\b(AVISO|ATENCAO|PULADO|revisar)\b/i.test(linha)) return "l-aviso";
  if (/^\s*(OK\b|.*\bOK - |TERMINOU|Pronto|Preparo conferido)/.test(linha)) return "l-ok";
  if (/^\s*(JOGO \d+\/\d+|AUTO_PES21)/.test(linha)) return "l-titulo";
  return null;
}

function receberTarefa(dados) {
  const t = estado.tarefa;
  if (dados.numero !== t.numero) {
    // Tarefa nova (talvez iniciada em outra aba do navegador): comeca do zero.
    t.linhas = [];
    $("#fotos").innerHTML = "";
  }
  Object.assign(t, { ...dados, linhas: t.linhas });
  t.linhas.length = Math.min(t.linhas.length, dados.desde);
  t.linhas.push(...dados.linhas);
  desenharConsole();
  procurarFotos(dados.linhas);
  atualizarBotoesAcao();
}

function desenharConsole() {
  const t = estado.tarefa;
  const console_ = $("#console");
  $("#titulo-console").textContent = t.titulo ? `Saída — ${t.titulo}` : "Saída";
  if (!t.numero) return;
  const fragmento = document.createDocumentFragment();
  for (const linha of t.linhas) {
    const classe = classeDaLinha(linha);
    fragmento.append(classe ? criar("span", { class: classe }, linha) : linha, "\n");
  }
  console_.replaceChildren(fragmento);
  if ($("#rolar-sozinho").checked) console_.scrollTop = console_.scrollHeight;

  const pilula = $("#pilula");
  if (t.rodando) { pilula.className = "pilula rodando"; pilula.textContent = t.titulo; }
  else if (t.codigo === 0) { pilula.className = "pilula ok"; pilula.textContent = `${t.titulo}: terminou`; }
  else if (t.codigo != null) { pilula.className = "pilula falhou"; pilula.textContent = t.parada ? `${t.titulo}: parado` : `${t.titulo}: parou com erro`; }
}

const fotosMostradas = new Set();
function procurarFotos(linhas) {
  for (const linha of linhas) {
    const m = linha.match(/foto[^:]*:\s*(\S*diagnostico\S*\.png)/i);
    if (!m || fotosMostradas.has(m[1])) continue;
    fotosMostradas.add(m[1]);
    $("#fotos").append(criar("figure", {},
      criar("a", { href: `/foto?p=${encodeURIComponent(m[1])}`, target: "_blank" },
        criar("img", { src: `/foto?p=${encodeURIComponent(m[1])}`, alt: "O que estava na tela" })),
      criar("figcaption", {}, `O que estava na tela: ${m[1]}`)));
  }
}

function atualizarBotoesAcao() {
  const rodando = estado.tarefa.rodando;
  for (const id of ["#acao-rodar", "#acao-extrair", "#acao-simular", "#acao-enviar"]) $(id).disabled = rodando;
  if (!rodando && !estado.fila.length) $("#acao-rodar").disabled = true;
  $("#acao-parar").classList.toggle("escondido", !rodando);
}

let acompanhando = false;
async function acompanhar() {
  if (acompanhando) return;
  acompanhando = true;
  try {
    while (true) {
      let dados = await api(`/api/tarefa?desde=${estado.tarefa.linhas.length}`);
      // Outra tarefa comecou (em outra aba do navegador): busca desde o inicio.
      if (dados.numero !== estado.tarefa.numero && dados.desde > 0) dados = await api("/api/tarefa?desde=0");
      receberTarefa(dados);
      if (!dados.rodando) break;
      await new Promise((r) => setTimeout(r, 700));
    }
    // Acabou: o que mudou na pasta aparece na fila e na aba Videos.
    await carregarFila();
    if (!$("#aba-videos").classList.contains("escondido")) carregarVideos();
    if (estado.rodadas.length && estado.tarefa.nome === "rodar") carregarRodadas();
  } catch (erro) {
    avisar(`Perdi o contato com o painel.py: ${erro.message}`, true);
  } finally {
    acompanhando = false;
  }
}

// ------------------------------------------------------------------ inicio

(async function iniciarPainel() {
  try {
    estado.times = await api("/api/times");
    preencherAvulso();
  } catch (erro) {
    avisar(`Não consegui falar com o painel.py: ${erro.message}`, true);
  }
  await carregarFila();
  // Se uma tarefa ja estava rodando (pagina recarregada), retoma a saida.
  try {
    const dados = await api("/api/tarefa?desde=0");
    if (dados.numero) { receberTarefa(dados); if (dados.rodando) acompanhar(); }
  } catch {}
  let aba = "jogos";
  try { aba = localStorage.getItem("aba") || "jogos"; } catch {}
  mostrarAba(aba);
  carregarCompeticoes();
})();
