"use strict";

const COTA_USD = 500;
const POR_PAGINA = 48;
const CHAVE_LISTA = "precos-rivera-lista";

let DADOS = null;
let produtos = [];
let porId = new Map();
let filtrados = [];
let mostrando = POR_PAGINA;
let cotacao = null;
let lista = carregarLista();
const filtro = { categoria: "", loja: "" };

const $ = (id) => document.getElementById(id);
const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const usd = (v) => "US$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const brl = (v) => (cotacao ? (v * cotacao).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "");
const nomeLoja = (l) => (DADOS && DADOS.lojas[l] ? DADOS.lojas[l].nome : l);
const dataBR = (iso) => iso.slice(0, 10).split("-").reverse().join("/");
const ponto = (loja) => `<i class="ponto ponto--${esc(loja)}" aria-hidden="true"></i>`;
const ICONE_PACOTE = '<svg class="card__semimg" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/></svg>';
// imagens da Siñeriz: a variante /26/ é minúscula, a /28/ tem resolução melhor
const imagem = (url) => (url || "").replace(/(cloudfront\.net\/images\/\d+)\/26\//, "$1/28/");

function carregarLista() {
  try { return JSON.parse(localStorage.getItem(CHAVE_LISTA)) || {}; } catch { return {}; }
}
function salvarLista() {
  try { localStorage.setItem(CHAVE_LISTA, JSON.stringify(lista)); } catch { /* sem armazenamento, a lista vale só nesta visita */ }
}

function esqueleto() {
  const um = '<div class="card esqueleto"><div class="card__img"></div><div class="card__corpo"><div class="linha-fake" style="width:40%"></div><div class="linha-fake" style="width:90%;margin-top:6px"></div><div class="linha-fake" style="width:55%;height:20px;margin-top:14px"></div></div></div>';
  $("grade").innerHTML = um.repeat(8);
}

async function iniciar() {
  esqueleto();
  try {
    const resp = await fetch("dados.json", { cache: "no-store" });
    if (!resp.ok) throw new Error(resp.status);
    DADOS = await resp.json();
  } catch (e) {
    $("grade").innerHTML = `<div class="vazio"><strong>Ainda não há preços para mostrar</strong>
      Rode o coletor (<code>python3 coletor/coletar.py</code>) e abra o site pelo servidor local.</div>`;
    return;
  }
  cotacao = DADOS.cotacao && DADOS.cotacao.valor;

  produtos = DADOS.produtos.map((p) => {
    const ofertas = p.ofertas.slice().sort((a, b) => a.preco - b.preco);
    const menor = ofertas[0].preco;
    const maior = ofertas[ofertas.length - 1].preco;
    let queda = 0;
    for (const o of ofertas) {
      const h = o.historico;
      if (h.length > 1) {
        const anterior = h[h.length - 2][1];
        const atual = h[h.length - 1][1];
        if (atual < anterior) queda = Math.max(queda, (anterior - atual) / anterior);
      }
    }
    const texto = norm([p.nome, p.categoria, ...ofertas.map((o) => o.nome + " " + o.marca)].join(" "));
    return { ...p, imagem: imagem(p.imagem), ofertas, menor, maior, economia: maior - menor, queda, texto };
  });
  porId = new Map(produtos.map((p) => [p.id, p]));

  desenharInfo();
  desenharCategorias();
  desenharAbas();

  $("busca").addEventListener("input", () => { mostrando = POR_PAGINA; aplicar(); });
  $("ordem").addEventListener("change", () => { mostrando = POR_PAGINA; aplicar(); });
  $("abas-loja").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-loja]");
    if (!b) return;
    filtro.loja = b.dataset.loja;
    for (const x of $("abas-loja").children) x.setAttribute("aria-selected", String(x === b));
    mostrando = POR_PAGINA;
    aplicar();
  });
  $("categorias").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (!b) return;
    filtro.categoria = b.dataset.cat;
    for (const x of $("categorias").children) x.setAttribute("aria-pressed", String(x === b));
    mostrando = POR_PAGINA;
    aplicar();
  });
  $("carregar-mais").addEventListener("click", () => { mostrando += POR_PAGINA; desenhar(); });
  $("grade").addEventListener("click", (e) => { const c = e.target.closest(".card[data-id]"); if (c) abrirDetalhe(c.dataset.id); });
  $("abrir-lista").addEventListener("click", abrirLista);
  $("fechar-lista").addEventListener("click", fecharLista);
  $("fundo-lista").addEventListener("click", fecharLista);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("lista").hidden) fecharLista(); });
  $("detalhe").addEventListener("click", (e) => { if (e.target === $("detalhe")) $("detalhe").close(); });

  for (const id of Object.keys(lista)) if (!porId.has(id)) delete lista[id];
  atualizarContador();
  aplicar();
}

function desenharInfo() {
  const partes = [];
  if (cotacao) partes.push(`<span class="pilula pilula--destaque">Dólar hoje <b>R$ ${cotacao.toFixed(2).replace(".", ",")}</b></span>`);
  const duplas = produtos.filter((p) => p.ofertas.length > 1).length;
  partes.push(`<span class="pilula"><b>${produtos.length.toLocaleString("pt-BR")}</b> produtos</span>`);
  const nLojas = new Set(produtos.flatMap((p) => p.ofertas.map((o) => o.loja))).size;
  partes.push(`<span class="pilula"><b>${nLojas}</b> lojas</span>`);
  if (duplas) partes.push(`<span class="pilula"><b>${duplas.toLocaleString("pt-BR")}</b> em mais de uma loja</span>`);
  partes.push(`<span class="pilula">Atualizado <b>${dataBR(DADOS.atualizado)} ${DADOS.atualizado.slice(11, 16)}</b></span>`);
  $("info").innerHTML = partes.join("");
}

function desenharAbas() {
  // só mostra lojas que têm produtos nos dados, na ordem de quem tem mais
  const contagem = {};
  for (const p of produtos) for (const o of p.ofertas) contagem[o.loja] = (contagem[o.loja] || 0) + 1;
  const lojas = Object.keys(contagem).sort((a, b) => contagem[b] - contagem[a]);
  const aba = (valor, rotulo, sel) => `<button role="tab" type="button" data-loja="${esc(valor)}" aria-selected="${sel}">${rotulo}</button>`;
  $("abas-loja").innerHTML = aba("", "Todas", true) + aba("ambas", "Em várias", false) +
    lojas.map((l) => aba(l, `${ponto(l)} ${esc(nomeLoja(l))}`, false)).join("");
}

function desenharCategorias() {
  const contagem = {};
  for (const p of produtos) contagem[p.categoria] = (contagem[p.categoria] || 0) + 1;
  const cats = Object.keys(contagem).sort((a, b) => contagem[b] - contagem[a]);
  $("categorias").innerHTML =
    `<button class="chip" type="button" data-cat="" aria-pressed="true">Todas</button>` +
    cats.map((c) => `<button class="chip" type="button" data-cat="${esc(c)}" aria-pressed="false">${esc(c)}<small>${contagem[c]}</small></button>`).join("");
}

function aplicar() {
  const termos = norm($("busca").value).split(/\s+/).filter(Boolean);
  const ordem = $("ordem").value;
  const { categoria, loja } = filtro;

  filtrados = produtos.filter((p) => {
    if (categoria && p.categoria !== categoria) return false;
    if (loja === "ambas" && p.ofertas.length < 2) return false;
    if (loja && loja !== "ambas" && !p.ofertas.some((o) => o.loja === loja)) return false;
    if (ordem === "queda" && !p.queda) return false;
    return termos.every((t) => p.texto.includes(t));
  });

  const ordens = {
    menor: (a, b) => a.menor - b.menor,
    maior: (a, b) => b.menor - a.menor,
    economia: (a, b) => b.economia - a.economia,
    queda: (a, b) => b.queda - a.queda,
    relevancia: (a, b) => (b.ofertas.length - a.ofertas.length) ||
      (termos.length ? (norm(b.nome).startsWith(termos[0]) - norm(a.nome).startsWith(termos[0])) : 0) ||
      a.nome.localeCompare(b.nome, "pt"),
  };
  filtrados.sort(ordens[ordem]);
  desenhar();
}

function desenhar() {
  const total = filtrados.length;
  if (!total) {
    $("resumo").textContent = "";
    $("grade").innerHTML = `<div class="vazio"><strong>Nenhum produto encontrado</strong>Tente outra palavra ou limpe os filtros.</div>`;
    $("carregar-mais").hidden = true;
    return;
  }
  const busca = $("busca").value.trim();
  $("resumo").textContent = `${total.toLocaleString("pt-BR")} ${total === 1 ? "produto" : "produtos"}${busca ? ` para “${busca}”` : ""}`;
  $("grade").innerHTML = filtrados.slice(0, mostrando).map(card).join("");
  $("carregar-mais").hidden = mostrando >= total;
  $("carregar-mais").textContent = `Mostrar mais (${(total - Math.min(mostrando, total)).toLocaleString("pt-BR")} restantes)`;
}

function card(p) {
  const melhor = p.ofertas[0];
  const tags = [];
  if (p.ofertas.length > 1 && p.economia >= 0.5) tags.push(`<span class="tag tag--economia">−${usd(p.economia)}</span>`);
  if (p.queda) tags.push(`<span class="tag tag--queda">Baixou ${Math.round(p.queda * 100)}%</span>`);
  const comparacao = p.ofertas.length > 1
    ? `<div class="comparacao">${p.ofertas.slice(0, 3).map((o, i) => `
        <div class="comparacao__linha ${i === 0 && p.economia > 0 ? "comparacao__linha--melhor" : ""}">
          <span>${ponto(o.loja)}${esc(nomeLoja(o.loja))}</span><b>${usd(o.preco)}</b>
        </div>`).join("")}${p.ofertas.length > 3 ? `<div class="comparacao__linha">+${p.ofertas.length - 3} lojas</div>` : ""}</div>`
    : `<div class="card__loja">${ponto(melhor.loja)}${esc(nomeLoja(melhor.loja))}</div>`;
  return `
    <button class="card" type="button" data-id="${esc(p.id)}">
      <div class="card__img">${ICONE_PACOTE}${p.imagem ? `<img src="${esc(p.imagem)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}</div>
      ${tags.length ? `<div class="card__tags">${tags.join("")}</div>` : ""}
      <div class="card__corpo">
        <div class="card__cat">${esc(p.categoria)}</div>
        <div class="card__nome">${esc(p.nome)}</div>
        <div class="card__preco"><strong>${usd(p.menor)}</strong><span>${brl(p.menor)}</span></div>
        ${comparacao}
      </div>
    </button>`;
}

function abrirDetalhe(id) {
  const p = porId.get(id);
  if (!p) return;
  const varias = p.ofertas.length > 1;
  const ofertas = p.ofertas.map((o, i) => `
    <div class="oferta ${i === 0 && varias && p.economia > 0 ? "oferta--melhor" : ""}">
      <div>
        <div class="oferta__loja">${ponto(o.loja)}${esc(nomeLoja(o.loja))}${i === 0 && varias && p.economia > 0 ? '<span class="selo-melhor">Mais barato</span>' : ""}</div>
        <div class="oferta__nome">${esc([o.marca, o.nome].filter(Boolean).join(" · "))}</div>
        ${o.informado ? `<div class="oferta__manual">Preço informado em ${dataBR(o.informado)} · confirme na loja</div>` : ""}
      </div>
      <div class="oferta__preco"><strong>${usd(o.preco)}</strong><small>${brl(o.preco)}</small></div>
      ${o.url ? `<a href="${esc(o.url)}" target="_blank" rel="noopener">${/instagram\.com/.test(o.url) ? "Ver Instagram ↗" : "Ver na loja ↗"}</a>` : "<span></span>"}
    </div>`).join("");
  const naLista = !!lista[p.id];
  $("detalhe").innerHTML = `
    <div class="detalhe__topo">
      <div class="detalhe__img">${ICONE_PACOTE}${p.imagem ? `<img src="${esc(p.imagem)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}</div>
      <div class="detalhe__info">
        <div class="card__cat">${esc(p.categoria)}</div>
        <h2>${esc(p.nome)}</h2>
        ${varias && p.economia > 0
          ? `<div class="aviso-economia">Na <b>${esc(nomeLoja(p.ofertas[0].loja))}</b> você economiza <b>${usd(p.economia)}</b>${cotacao ? ` (${brl(p.economia)})` : ""}.</div>`
          : ""}
      </div>
      <button class="botao-icone" type="button" data-fechar aria-label="Fechar">×</button>
    </div>
    <div class="detalhe__corpo">
      <div class="ofertas">${ofertas}</div>
      <p class="nota" style="margin-top:10px">${varias
        ? "As lojas foram comparadas automaticamente pelo nome do produto. Confira o nome em cada uma antes de comprar."
        : "Só encontramos este produto em uma loja. Ele pode estar em outras com um nome diferente."}</p>
      <h3>Histórico de preço</h3>
      <div class="grafico">${grafico(p)}</div>
      <div class="acoes">
        <button class="botao ${naLista ? "" : "botao--principal"}" type="button" data-lista>${naLista ? "Remover da lista" : "Adicionar à lista"}</button>
      </div>
    </div>`;
  $("detalhe").querySelector("[data-fechar]").onclick = () => $("detalhe").close();
  $("detalhe").querySelector("[data-lista]").onclick = () => {
    if (lista[p.id]) delete lista[p.id]; else lista[p.id] = 1;
    salvarLista(); atualizarContador(); abrirDetalhe(p.id);
  };
  if (!$("detalhe").open) $("detalhe").showModal();
}

function grafico(p) {
  const fim = DADOS.atualizado.slice(0, 10);
  const series = p.ofertas.map((o) => ({ loja: o.loja, pontos: [...o.historico, [fim, o.preco]] }));
  const inicio = series.flatMap((s) => s.pontos.map((x) => x[0])).reduce((a, b) => (a < b ? a : b));
  if (inicio === fim) {
    return '<p class="nota">O acompanhamento começou hoje. O gráfico aparece quando houver preços de dias diferentes.</p>';
  }
  const W = 640, H = 200, ml = 50, mr = 12, mt = 12, mb = 26;
  const t0 = Date.parse(inicio), t1 = Date.parse(fim);
  const valores = series.flatMap((s) => s.pontos.map((x) => x[1]));
  let vmin = Math.min(...valores), vmax = Math.max(...valores);
  if (vmin === vmax) { vmin *= 0.9; vmax *= 1.1; }
  const pad = (vmax - vmin) * 0.12;
  vmin -= pad; vmax += pad;
  const X = (d) => ml + ((Date.parse(d) - t0) / (t1 - t0)) * (W - ml - mr);
  const Y = (v) => mt + (1 - (v - vmin) / (vmax - vmin)) * (H - mt - mb);
  const linhas = series.map((s) => {
    const d = s.pontos.map(([data, v], i) => (i === 0 ? `M${X(data)},${Y(v)}` : `H${X(data)}V${Y(v)}`)).join("");
    return `<path d="${d}" stroke="var(--${esc(s.loja)}, var(--primaria))" stroke-width="2.5"/>`;
  }).join("");
  const marcas = [vmin + pad, (vmin + vmax) / 2, vmax - pad].map((v) =>
    `<line class="eixo" x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${ml - 8}" y="${Y(v) + 4}" text-anchor="end">${v.toFixed(2)}</text>`
  ).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Histórico de preço em dólar">
      ${marcas}
      <text x="${ml}" y="${H - 6}">${dataBR(inicio)}</text>
      <text x="${W - mr}" y="${H - 6}" text-anchor="end">${dataBR(fim)}</text>
      ${linhas}
    </svg>
    <div class="legenda">${series.map((s) => `<span>${ponto(s.loja)}${esc(nomeLoja(s.loja))}</span>`).join("")}<span>valores em US$</span></div>`;
}

function atualizarContador() {
  const n = Object.values(lista).reduce((a, b) => a + b, 0);
  $("lista-contador").textContent = n;
  $("lista-contador").dataset.zero = String(n === 0);
}

function abrirLista() { $("lista").hidden = false; $("fundo-lista").hidden = false; desenharLista(); }
function fecharLista() { $("lista").hidden = true; $("fundo-lista").hidden = true; }

function desenharLista() {
  const itens = Object.entries(lista).map(([id, qtd]) => ({ p: porId.get(id), qtd })).filter((i) => i.p);
  if (!itens.length) {
    $("lista-itens").innerHTML = `<div class="lista-vazia">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h15l-1.5 9h-12z"/><path d="M6 6 5 3H2"/><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/></svg>
      <p>Sua lista está vazia.</p><p>Abra um produto e toque em <b>Adicionar à lista</b> para ver quanto da cota você já usou.</p></div>`;
    $("lista-total").innerHTML = "";
    return;
  }
  $("lista-itens").innerHTML = itens.map(({ p, qtd }) => `
    <div class="item">
      <div class="item__img">${p.imagem ? `<img src="${esc(p.imagem)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}</div>
      <div>
        <div class="item__nome">${esc(p.nome)}</div>
        <div class="item__loja">${ponto(p.ofertas[0].loja)}${esc(nomeLoja(p.ofertas[0].loja))} · ${usd(p.menor)}</div>
      </div>
      <div class="item__lado">
        <b>${usd(p.menor * qtd)}</b>
        <div class="item__qtd">
          <button type="button" data-menos="${esc(p.id)}" aria-label="Diminuir">−</button><span>${qtd}</span><button type="button" data-mais="${esc(p.id)}" aria-label="Aumentar">+</button>
        </div>
      </div>
    </div>`).join("");
  $("lista-itens").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const { mais, menos } = b.dataset;
    if (mais) lista[mais] += 1;
    if (menos) { lista[menos] -= 1; if (lista[menos] <= 0) delete lista[menos]; }
    if (mais || menos) { salvarLista(); atualizarContador(); desenharLista(); }
  };

  const total = itens.reduce((s, { p, qtd }) => s + p.menor * qtd, 0);
  const porLoja = {};
  for (const { p, qtd } of itens) porLoja[p.ofertas[0].loja] = (porLoja[p.ofertas[0].loja] || 0) + p.menor * qtd;
  const passou = total > COTA_USD;
  $("lista-total").innerHTML = `
    <div class="total-linha"><span>Total</span><strong>${usd(total)}</strong></div>
    ${cotacao ? `<div class="total-linha cota"><span>em reais</span><span>${brl(total)}</span></div>` : ""}
    <div class="barra ${passou ? "passou" : ""}"><div style="width:${Math.min(100, (total / COTA_USD) * 100)}%"></div></div>
    <div class="cota ${passou ? "passou" : ""}">${passou
      ? `Passou ${usd(total - COTA_USD)} da cota de ${usd(COTA_USD)} por pessoa`
      : `Ainda cabem ${usd(COTA_USD - total)} na cota de ${usd(COTA_USD)} por pessoa`}</div>
    <div class="cota" style="margin-top:8px">${Object.entries(porLoja).map(([l, v]) => `${ponto(l)} ${esc(nomeLoja(l))}: ${usd(v)}`).join(" &nbsp; ")}</div>`;
}

iniciar();
