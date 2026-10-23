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
  if (nome === "youtube") carregarYoutube();
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

// ------------------------------------------------------------------ youtube

estado.yt = { dados: null, itens: [] };

async function carregarYoutube() {
  const alertas = $("#yt-alertas");
  let dados;
  try {
    dados = await api("/api/youtube");
  } catch (erro) {
    alertas.replaceChildren(criar("div", { class: "alerta-caixa erro" }, criar("span", {}, erro.message)));
    estado.yt.dados = null;
    mostrarPlanoYoutube();
    return;
  }
  estado.yt.dados = dados;

  // Mantem o que voce ja tinha escolhido para os videos que continuam na pasta.
  const antes = new Map(estado.yt.itens.map((i) => [i.arquivo, i]));
  const mantidos = estado.yt.itens.filter((i) => dados.videos.some((v) => v.arquivo === i.arquivo));
  const novos = dados.videos.filter((v) => !antes.has(v.arquivo)).map((v) => ({ ...v, incluido: true, junto: false }));
  estado.yt.itens = [...mantidos.map((i) => ({ ...i, ...dados.videos.find((v) => v.arquivo === i.arquivo) })), ...novos];

  const lista = [];
  if (!dados.playwright) {
    lista.push(criar("div", { class: "alerta-caixa erro" },
      criar("span", {}, "Falta instalar o Playwright, que controla o Chrome. Num terminal, rode: "),
      criar("code", {}, "pip install playwright")));
  }
  const rpa = dados.rpa_antigo || {};
  if (rpa.pasta && (rpa.perfil || rpa.historico_novas)) {
    const coisas = [rpa.perfil ? "o login do canal" : null,
      rpa.historico_novas ? `${rpa.historico_novas} linha(s) do histórico do que já subiu` : null].filter(Boolean);
    lista.push(criar("div", { class: "alerta-caixa" },
      criar("span", {}, `Achei o RPA_Youtube antigo em ${rpa.pasta}. Dá para trazer ${coisas.join(" e ")} para cá, sem fazer o login de novo.`),
      criar("button", { class: "primario", onclick: importarRpa }, "Trazer do RPA_Youtube")));
  } else if (!dados.login_feito) {
    lista.push(criar("div", { class: "alerta-caixa" },
      criar("span", {}, "Ainda não entrou na conta do canal neste PC. Clique em “Entrar na conta do canal”, faça o login no Chrome que abrir, confira o canal e feche o Chrome."),
    ));
  }
  alertas.replaceChildren(...lista);

  const select = $("#yt-competicao");
  const atual = select.value || (() => { try { return localStorage.getItem("yt-competicao"); } catch { return null; } })();
  select.replaceChildren(...dados.competicoes.map((c) => criar("option", { value: c.chave }, c.nome)));
  if (atual && dados.competicoes.some((c) => c.chave === atual)) select.value = atual;
  preencherRodadasYoutube();

  const intervalo = $("#yt-intervalo");
  if (!intervalo.value) intervalo.value = dados.intervalo_padrao;
  if (!$("#yt-data").value) sugerirHorario();
  mostrarVideosYoutube();
}

function importarRpa() {
  const rpa = estado.yt.dados?.rpa_antigo || {};
  const aviso = rpa.perfil
    ? "\n\nO login (perfil_chrome) é MOVIDO de lá para cá: o RPA_Youtube antigo deixa de estar logado. Feche o Chrome do robô antes."
    : "";
  if (!confirm(`Trazer do RPA_Youtube em ${rpa.pasta}?${aviso}`)) return;
  iniciar("youtube_importar", { pasta: rpa.pasta });
}

function competicaoYoutube() {
  return estado.yt.dados?.competicoes.find((c) => c.chave === $("#yt-competicao").value);
}

function preencherRodadasYoutube() {
  const c = competicaoYoutube();
  const select = $("#yt-rodada");
  const atual = select.value;
  select.replaceChildren(...(c?.rodadas || []).map((r) => criar("option", { value: r.valor }, r.rotulo)));
  if (c?.rodadas.some((r) => r.valor === atual)) select.value = atual;
  $("#yt-playlist").textContent = c ? (c.playlist ? `Playlist: ${c.playlist}` : "Esta competição não tem playlist.") : "";
  try { localStorage.setItem("yt-competicao", $("#yt-competicao").value); } catch {}
}

function sugerirHorario() {
  // 18:00 de hoje se ainda der tempo; senao a proxima hora cheia que respeita a margem.
  const margem = (estado.yt.dados?.margem_minutos || 10) + 5;
  const agora = new Date();
  let inicio = new Date(agora); inicio.setHours(18, 0, 0, 0);
  if (inicio - agora < margem * 60000) {
    inicio = new Date(agora.getTime() + margem * 60000);
    inicio.setMinutes(0, 0, 0);
    inicio.setHours(inicio.getHours() + 1);
  }
  const doisDigitos = (n) => String(n).padStart(2, "0");
  $("#yt-data").value = `${inicio.getFullYear()}-${doisDigitos(inicio.getMonth() + 1)}-${doisDigitos(inicio.getDate())}`;
  $("#yt-hora").value = `${doisDigitos(inicio.getHours())}:${doisDigitos(inicio.getMinutes())}`;
}

function mostrarVideosYoutube() {
  const lista = $("#yt-videos");
  const itens = estado.yt.itens;
  $("#yt-contagem").textContent = itens.filter((i) => i.incluido).length;
  lista.innerHTML = "";
  if (!itens.length) {
    const pasta = estado.yt.dados?.pasta || "pasta de vídeos";
    lista.append(criar("li", { class: "vazio" }, `Nenhum vídeo para subir em ${pasta}. Os que já subiram vão para a subpasta Enviados.`));
  }
  let primeiroIncluido = true;
  itens.forEach((item, i) => {
    const podeJuntar = item.incluido && !primeiroIncluido;
    if (item.incluido) primeiroIncluido = false;
    lista.append(criar("li", { class: `item-fila${item.incluido ? "" : " fora"}${podeJuntar && item.junto ? " colado" : ""}` },
      criar("input", { type: "checkbox", class: "incluir", checked: item.incluido, title: "Subir este vídeo",
        "aria-label": `Subir ${item.nome}`, onchange: (e) => { item.incluido = e.target.checked; mostrarVideosYoutube(); } }),
      criar("div", { class: "jogo-fila" },
        criar("span", { class: "confronto" }, item.nome),
        criar("span", { class: "origem" }, `${item.duracao || "--"} · ${item.tamanho_gb} GB · gravado ${item.gravado_em}`)),
      podeJuntar ? criar("label", { class: "junto", title: "Estreia no mesmo horário do jogo de cima" },
        criar("input", { type: "checkbox", checked: item.junto, "aria-label": `${item.nome} estreia junto com o de cima`, onchange: (e) => { item.junto = e.target.checked; mostrarVideosYoutube(); } }),
        "junto") : null,
      criar("span", { class: "mover" },
        criar("button", { title: "Subir", "aria-label": "Subir na ordem", disabled: i === 0, onclick: () => moverYoutube(i, -1) }, "↑"),
        criar("button", { title: "Descer", "aria-label": "Descer na ordem", disabled: i === itens.length - 1, onclick: () => moverYoutube(i, 1) }, "↓"),
      ),
    ));
  });
  mostrarPlanoYoutube();
}

function moverYoutube(i, delta) {
  const [item] = estado.yt.itens.splice(i, 1);
  estado.yt.itens.splice(i + delta, 0, item);
  mostrarVideosYoutube();
}

function montarPlanoYoutube() {
  const c = competicaoYoutube();
  const modo = document.querySelector("input[name=yt-modo]:checked").value;
  const horarios = [];
  for (const item of estado.yt.itens.filter((i) => i.incluido)) {
    if (item.junto && horarios.length) horarios[horarios.length - 1].push(item);
    else horarios.push([item]);
  }
  const problemas = [];
  const rodada = c?.rodadas.find((r) => r.valor === $("#yt-rodada").value);
  let inicio = null;
  const intervalo = Number($("#yt-intervalo").value) || estado.yt.dados?.intervalo_padrao || 20;
  if (modo === "estreia") {
    inicio = new Date(`${$("#yt-data").value}T${$("#yt-hora").value || "00:00"}`);
    if (!$("#yt-data").value || !$("#yt-hora").value || isNaN(inicio)) problemas.push("Escolha a data e o horário da primeira estreia.");
    else {
      const margem = estado.yt.dados?.margem_minutos || 10;
      if (inicio - new Date() < margem * 60000) problemas.push(`A primeira estreia precisa ser pelo menos ${margem} min no futuro.`);
    }
    if (intervalo < 1 || intervalo > 1440) problemas.push("O intervalo precisa ser de 1 a 1440 minutos.");
  }
  if (!horarios.length) problemas.push("Nenhum vídeo marcado para subir.");
  if (estado.yt.dados && !estado.yt.dados.playwright) problemas.push("Falta instalar o Playwright (pip install playwright).");

  const itens = [];
  horarios.forEach((grupo, g) => {
    const quando = inicio && !isNaN(inicio) ? new Date(inicio.getTime() + g * intervalo * 60000) : null;
    for (const item of grupo) {
      const titulo = `${item.nome} | ${rodada?.rotulo || "?"} | ${c?.nome || "?"}`;
      if (titulo.length > 100) problemas.push(`Título com ${titulo.length} caracteres (máximo 100): ${titulo}`);
      if (/[<>]/.test(titulo)) problemas.push(`O YouTube não aceita < ou > no título: ${titulo}`);
      itens.push({ titulo, quando, item });
    }
  });

  const doisDigitos = (n) => String(n).padStart(2, "0");
  const plano = c && rodada ? {
    competicao: c.chave,
    rodada: rodada.valor,
    modo,
    inicio: modo === "estreia" && inicio && !isNaN(inicio)
      ? `${inicio.getFullYear()}-${doisDigitos(inicio.getMonth() + 1)}-${doisDigitos(inicio.getDate())} ${doisDigitos(inicio.getHours())}:${doisDigitos(inicio.getMinutes())}`
      : null,
    intervalo,
    horarios: horarios.map((grupo) => grupo.map((i) => i.arquivo)),
  } : null;
  return { plano, itens, problemas };
}

function mostrarPlanoYoutube() {
  const { itens, problemas } = montarPlanoYoutube();
  const lista = $("#yt-plano");
  lista.innerHTML = "";
  for (const { titulo, quando } of itens) {
    const texto = quando
      ? quando.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).replace(",", "")
      : "privado";
    lista.append(criar("li", {}, criar("span", { class: "quando" }, texto), criar("span", { class: "titulo-yt" }, titulo)));
  }
  if (!itens.length) lista.append(criar("li", { class: "nota" }, "Marque os vídeos acima para ver o plano."));
  $("#yt-problemas").replaceChildren(...problemas.map((p) => criar("li", {}, p)));
  const n = itens.length;
  $("#yt-subir").textContent = n ? `Subir ${n} vídeo(s)` : "Subir";
  atualizarBotoesAcao();
}

$("#yt-competicao").addEventListener("change", () => { preencherRodadasYoutube(); mostrarPlanoYoutube(); });
$("#yt-rodada").addEventListener("change", mostrarPlanoYoutube);
for (const id of ["#yt-data", "#yt-hora", "#yt-intervalo"]) $(id).addEventListener("input", mostrarPlanoYoutube);
document.querySelectorAll("input[name=yt-modo]").forEach((r) => r.addEventListener("change", () => {
  $("#yt-campos-estreia").classList.toggle("escondido", r.value === "privado" && r.checked);
  mostrarPlanoYoutube();
}));
$("#yt-recarregar").addEventListener("click", carregarYoutube);
$("#yt-login").addEventListener("click", () => iniciar("youtube_login"));

$("#yt-simular").addEventListener("click", () => {
  const { plano, problemas } = montarPlanoYoutube();
  if (!plano || !plano.horarios.length) return avisar(problemas[0] || "Monte o plano primeiro.", true);
  iniciar("youtube", { plano, simular: true });
});

$("#yt-subir").addEventListener("click", () => {
  const { plano, itens, problemas } = montarPlanoYoutube();
  if (problemas.length || !plano) return avisar(problemas[0] || "Monte o plano primeiro.", true);
  const modo = plano.modo === "estreia" ? `como ESTREIA a partir de ${itens[0].quando.toLocaleString("pt-BR")}` : "como PRIVADO";
  if (!confirm(`Subir ${itens.length} vídeo(s) ${modo}?\n\nO Chrome do robô vai abrir e subir um por um. Não feche ele até acabar.`)) return;
  iniciar("youtube", { plano });
});

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

$("#criar-atalho").addEventListener("click", async () => {
  try {
    const { caminho } = await api("/api/atalho", {});
    avisar(`Atalho criado: ${caminho}`);
  } catch (erro) {
    avisar(erro.message, true);
  }
});

// ------------------------------------------------------------------ fechar o painel

$("#fechar-painel").addEventListener("click", async () => {
  const rodando = estado.tarefa.rodando;
  let pergunta = "Fechar o painel? Para abrir de novo, use o atalho Auto PES21.";
  if (rodando) {
    pergunta = `${estado.tarefa.titulo} ainda está rodando. Fechar o painel PARA essa tarefa agora.`;
    if (estado.tarefa.nome === "rodar") pergunta += "\n\nSe estiver no meio de uma partida, a gravação da NVIDIA pode ficar ligada.";
    pergunta += "\n\nFechar mesmo assim?";
  }
  if (!confirm(pergunta)) return;
  try {
    await api("/api/fechar", { forcar: rodando });
    $("#painel-fechado").classList.remove("escondido");
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
  $("#yt-simular").disabled = rodando;
  $("#yt-login").disabled = rodando;
  $("#yt-subir").disabled = rodando || (estado.yt ? montarPlanoYoutube().problemas.length > 0 : true);
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
    if (estado.tarefa.nome?.startsWith("youtube")) carregarYoutube();
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
