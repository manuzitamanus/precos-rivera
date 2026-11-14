#!/usr/bin/env python3
"""
Coletor de preços dos free shops de Rivera (Uruguai).

Lojas com coleta automática: Siñeriz, Neutral, Yury's e Barão.
Lojas sem site com preços (ex.: Brasil Free Shop, que só divulga no Instagram) entram pela
planilha dados/precos-manuais.csv — ou por uma planilha do Google publicada como CSV
(endereço em dados/config.json, campo "planilha_url").

Uso:
    python3 coletor/coletar.py                  # coleta tudo
    python3 coletor/coletar.py --loja neutral   # só uma loja
    python3 coletor/coletar.py --max-paginas 2  # teste rápido

Gera:
    dados/historico.json  -> histórico completo de preços (não apague)
    site/dados.json       -> o que o site lê

Só usa a biblioteca padrão do Python (nada para instalar).
"""
import argparse
import csv
import io
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from collections import Counter
from urllib.parse import quote, urljoin

RAIZ = Path(__file__).resolve().parent.parent
ARQ_HISTORICO = RAIZ / "dados" / "historico.json"
ARQ_SITE = RAIZ / "site" / "dados.json"
ARQ_MANUAIS = RAIZ / "dados" / "precos-manuais.csv"
ARQ_CONFIG = RAIZ / "dados" / "config.json"

UA = "Mozilla/5.0 (compatible; PrecosRivera/0.1; comparador de precos experimental)"
PAUSA = 0.7  # segundos entre pedidos, para não sobrecarregar os sites das lojas

LOJAS = {
    "sineriz": {"nome": "Siñeriz", "site": "https://www.sineriz.com.uy"},
    "neutral": {"nome": "Neutral", "site": "https://www.neutral.com.uy"},
    "yurys": {"nome": "Yury's", "site": "https://www.yurysfreeshop.com"},
    "barao": {"nome": "Barão", "site": "https://www.baraofreeshop.com.br"},
    "brasil": {"nome": "Brasil Free Shop", "site": "https://brasilfreeshop.com",
               "instagram": "https://www.instagram.com/shopfreebrasil/", "manual": True},
}
# de qual loja vem o nome exibido quando o produto está em várias (as primeiras escrevem nomes mais legíveis)
PREFERENCIA_NOME = ["sineriz", "barao", "yurys", "neutral"]


# ---------------------------------------------------------------- utilidades

def log(msg):
    print(msg, file=sys.stderr, flush=True)


def baixar(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                texto = resp.read().decode("utf-8", "replace")
            time.sleep(PAUSA)
            return texto
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            log(f"  ! falha ao baixar {url}: {e}")
            time.sleep(3 * (i + 1))
    return None


def limpar(texto):
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def ler_preco(texto):
    """'USD 1,299.90' -> 1299.9. Se houver mais de um valor (promoção), devolve o menor."""
    valores = []
    for bruto in re.findall(r"(?:USD|US\$|U\$S)\s*([\d.,]+)", texto, re.I):
        bruto = bruto.strip(".,")
        if "," in bruto and "." in bruto:
            bruto = bruto.replace(",", "")
        elif "," in bruto:
            inteiro, _, dec = bruto.rpartition(",")
            bruto = bruto.replace(",", "") if len(dec) == 3 else inteiro.replace(",", "") + "." + dec
        try:
            valores.append(float(bruto))
        except ValueError:
            pass
    valores = [v for v in valores if v > 0]
    return min(valores) if valores else None


CATEGORIAS = [
    ("PERFUM", "Perfumaria e cosméticos"),
    ("COSMET", "Perfumaria e cosméticos"),
    ("BELEZA", "Perfumaria e cosméticos"),
    ("BEBIDA", "Bebidas"),
    ("VINHO", "Bebidas"),
    ("COMEST", "Comestíveis"),
    ("ELETRON", "Eletrônicos"),
    ("BRINQUEDO", "Brinquedos e infantil"),
    ("INFANTIL", "Brinquedos e infantil"),
    ("RELOG", "Acessórios e relógios"),
    ("ACESSOR", "Acessórios e relógios"),
    ("BAZAR", "Casa e bazar"),
    ("ESPORT", "Esportes"),
    ("FERRAMENT", "Ferramentas"),
]


PALAVRAS_CATEGORIA = [
    ("Bebidas", "WHISKY WHISKEY VODKA GIN GIM RUM TEQUILA VINHO VINO CERVEJA CERVEZA ESPUMANTE CHAMPAGNE "
                "CHAMPANHE LICOR CONHAQUE COGNAC APERITIVO APEROL ENERGETICO PISCO JAGERMEISTER BEBIDAS"),
    ("Perfumaria e cosméticos", "PERFUME PERFUMES EDP EDT EDC EAU COLONIA SPLASH MIST SHAMPOO CONDICIONADOR CREME "
                                "SERUM MAQUIAGEM BATOM RIMEL MASCARA PROTETOR HIDRATANTE COSMETICOS PELE CABELO "
                                "MASCULINOS FEMININOS NICHO LOCAO DESODORANTE ESMALTE"),
    ("Eletrônicos", "TV TVS CELULAR CELULARES SMARTPHONE IPHONE NOTEBOOK TABLET IPAD FONE HEADPHONE SPEAKER "
                    "SOUNDBAR CAMERA DRONE CONSOLE PLAYSTATION XBOX NINTENDO ARCONDICIONADO VENTILADOR AQUECEDOR "
                    "ELETRONICOS INFORMATICA AUDIO GAMES LIQUIDIFICADOR FRITADEIRA CAFETEIRA ASPIRADOR ELETRODOMESTICOS"),
    ("Brinquedos e infantil", "BRINQUEDO BRINQUEDOS BONECA BARBIE LEGO PELUCIA PELUCIAS INFANTIL BEBE BABY FISHER "
                              "FUNKO FUNKOPOP POKEMON PLAYDOH POLLY JURASSIC PRINCESAS STITCH SUPERHEROIS MARIOBROS "
                              "STARWARS TRANSFORMERS DISNEY"),
    ("Comestíveis", "CHOCOLATE CHOCOLATES BOMBOM ALFAJOR ALFAJORES BISCOITO BISCOITOS BALA BALAS DOCE DOCES AZEITE "
                    "AZEITES CAFE CHA CHAS SALGADOS CONSERVAS CONDIMENTOS PRINGLES NUTELLA MILKA TOBLERONE KETCHUP "
                    "COMESTIVEIS"),
    ("Acessórios e relógios", "RELOGIO RELOGIOS SMARTWATCH OCULOS BOLSA BOLSAS CARTEIRA MOCHILA MOCHILAS MALA MALAS"),
    ("Casa e bazar", "COZINHA PANELA PANELAS FRIGIDEIRA TALHER TALHERES COPO COPOS TACA TACAS CANECA PRATO MESA CAMA "
                     "TOALHA LENCOL TAPETE TAPETES DECORACAO QUADRO PORCELANA PORCELANAS CRISTAIS VELA ALMOFADA "
                     "MANTA BAZAR TERMICA STANLEY MOVEIS"),
    ("Esportes", "BOLA RAQUETE PADEL BICICLETA ESPORTE ESPORTES YOGA EVERLAST FITNESS TENISEPADDEL"),
    ("Ferramentas", "FERRAMENTA FERRAMENTAS FURADEIRA PARAFUSADEIRA"),
]
PALAVRAS_CATEGORIA = [(cat, set(p.split())) for cat, p in PALAVRAS_CATEGORIA]


def categoria_por_texto(texto):
    tokens = set(re.findall(r"[A-Z]+", sem_acento(texto).upper().replace("-", " ")))
    for cat, palavras in PALAVRAS_CATEGORIA:
        if tokens & palavras:
            return cat
    return None


def categoria_produto(nome, pagina):
    """Para lojas sem categorias padronizadas: tenta pelo nome do produto, depois pelo nome da página."""
    return categoria_por_texto(nome) or categoria_por_texto(pagina) or categoria_comum(pagina)


def categoria_comum(nome):
    n = sem_acento(nome).upper()
    for chave, cat in CATEGORIAS:
        if chave in n:
            return cat
    return "Diversos"


# ------------------------------------------------------------------- Siñeriz

SIN_BASE = LOJAS["sineriz"]["site"]
RE_SIN_CARD = re.compile(r'<li class="c-product[ "][^>]*>(.*?)</li>', re.S)


def sin_cards(pagina, categoria):
    ofertas = []
    for bloco in RE_SIN_CARD.findall(pagina):
        m = re.search(r'c-product__name"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S)
        p = re.search(r'c-product__description"[^>]*>(.*?)</p>', bloco, re.S)
        if not m or not p:
            continue
        preco = ler_preco(limpar(p.group(1)))
        if preco is None:
            continue
        img = re.search(r'<img[^>]+src="([^"]+)"', bloco)
        imagem = img.group(1) if img else ""
        # a imagem padrão é minúscula (83 px); a variante /28/ tem ~200 px
        imagem = re.sub(r"/images/(\d+)/26/", r"/images/\1/28/", imagem)
        ofertas.append({
            "loja": "sineriz",
            "url": urljoin(SIN_BASE, m.group(1)),
            "nome": limpar(m.group(2)),
            "marca": "",
            "preco": preco,
            "imagem": imagem,
            "categoria": categoria,
        })
    return ofertas


def sin_grupos(pagina):
    """Lê o menu lateral: [(nome do grupo, [links das subcategorias])]."""
    nav = pagina.split('id="categoryNav"', 1)[-1].split("</nav>", 1)[0]
    grupos = []
    for pedaco in nav.split('class="c-side-nav__parent-item"')[1:]:
        rotulo = re.search(r"<label[^>]*>(.*?)</label>", pedaco, re.S)
        links = re.findall(r'href="([^"]+)"', pedaco)
        if rotulo:
            grupos.append((limpar(rotulo.group(1)), links))
    return grupos


def coletar_sineriz(max_paginas=None):
    log("Siñeriz: lendo categorias...")
    inicial = baixar(SIN_BASE + "/produtos/bebidas-1/")
    if not inicial:
        return [], {}
    grupos = sin_grupos(inicial)
    ofertas, truncadas, visitadas = {}, [], 0
    for nome, links in grupos:
        cat = categoria_comum(nome)
        # subcategorias primeiro, depois o "Tudo" (que só mostra os 50 primeiros)
        links = sorted(set(links), key=lambda h: h.endswith("-1/") or h.endswith("beleza/"))
        for href in links:
            if max_paginas and visitadas >= max_paginas:
                break
            url = urljoin(SIN_BASE, href)
            pagina = baixar(url)
            visitadas += 1
            if not pagina:
                continue
            achadas = sin_cards(pagina, cat)
            for o in achadas:
                ofertas.setdefault(o["url"], o)
            pc = re.search(r"pageCount\s*=\s*(\d+)", pagina)
            if pc and int(pc.group(1)) > 1:
                truncadas.append(href)
            log(f"  {nome} > {href}: {len(achadas)} produtos")
    if truncadas:
        log(f"  aviso: {len(truncadas)} páginas da Siñeriz têm mais de 50 produtos e só os 50 primeiros foram lidos")
    return list(ofertas.values()), {"paginas_incompletas": truncadas}


# ------------------------------------------------------------------- Neutral

NEU_BASE = LOJAS["neutral"]["site"]
RE_NEU_CARD = re.compile(r'<a [^>]*href="(?:/br)?/products/(\d+)"[^>]*>(.*?)</a>', re.S)


def neu_cards(pagina, categoria):
    ofertas = []
    for pid, bloco in RE_NEU_CARD.findall(pagina):
        textos = [limpar(t) for t in re.findall(r"<p[^>]*>(.*?)</p>", bloco, re.S)]
        idx = next((i for i, t in enumerate(textos) if ler_preco(t) is not None), None)
        if idx is None:
            continue
        marca = textos[idx - 1] if idx > 0 else ""
        nome = next((t for t in textos[idx + 1:] if t), "")
        if not nome:
            continue
        img = re.search(r'<img[^>]+src="([^"]+)"', bloco)
        ofertas.append({
            "loja": "neutral",
            "url": f"{NEU_BASE}/br/products/{pid}",
            "nome": nome,
            "marca": marca,
            "preco": ler_preco(textos[idx]),
            "imagem": img.group(1) if img else "",
            "categoria": categoria,
        })
    return ofertas


def coletar_neutral(max_paginas=None):
    log("Neutral: lendo categorias...")
    inicial = baixar(NEU_BASE + "/br")
    if not inicial:
        return [], {}
    cats = {}
    for cid, texto in re.findall(r'href="(?:/br)?/products/category/(\d+)"[^>]*>(.*?)</a>', inicial, re.S):
        nome = limpar(texto)
        if nome and cid not in cats:
            cats[cid] = nome
    m = re.search(r"D[óo]lar por R\$\s*([\d.,]+)", limpar(inicial))
    extra = {"cotacao_loja": float(m.group(1).replace(",", ".")) if m else None}

    ofertas, visitadas = {}, 0
    for cid, nome in cats.items():
        cat = categoria_comum(nome)
        pagina_n, total = 1, 1
        while pagina_n <= total:
            if max_paginas and visitadas >= max_paginas:
                break
            pagina = baixar(f"{NEU_BASE}/br/products/category/{cid}?page={pagina_n}")
            visitadas += 1
            if not pagina:
                break
            achadas = neu_cards(pagina, cat)
            if not achadas:
                break
            for o in achadas:
                ofertas.setdefault(o["url"], o)
            t = re.search(r"P[áa]gina\s+\d+\s+de\s+(\d+)", limpar(pagina))
            total = min(int(t.group(1)), 300) if t else pagina_n
            log(f"  {nome}: página {pagina_n}/{total} ({len(achadas)} produtos)")
            pagina_n += 1
    return list(ofertas.values()), extra


# ------------------------------------------------- lojas feitas no Wix (Yury's, Barão)

WIX_IGNORAR = {
    "cart", "blog", "contato", "centro-de-ajuda", "politica-de-privacidade", "yuris", "my-wishlist",
    "trabalhe-conosco", "responsabilidadesocial", "sla", "account", "termos-e-condicoes",
}
DECODIFICADOR = json.JSONDecoder()


def wix_paginas(base, inicial):
    paginas = []
    for caminho in re.findall(r'href="%s/([^"#?]*)"' % re.escape(base), inicial):
        caminho = html.unescape(caminho)
        if caminho and "/" not in caminho and "." not in caminho and caminho not in WIX_IGNORAR:
            paginas.append(caminho)
    return list(dict.fromkeys(paginas))


def wix_produtos(pagina):
    """Os produtos vêm num JSON dentro da página; pega a maior lista (a vitrine principal)."""
    listas = []
    for m in re.finditer(r'"productsWithMetaData":\{"list":', pagina):
        try:
            lista, _ = DECODIFICADOR.raw_decode(pagina, m.end())
            listas.append(lista)
        except ValueError:
            pass
    total = re.search(r'"totalCount":(\d+)', pagina)
    return (max(listas, key=len) if listas else []), (int(total.group(1)) if total else None)


def coletar_wix(loja, max_paginas=None):
    base = LOJAS[loja]["site"]
    nome_loja = LOJAS[loja]["nome"]
    log(f"{nome_loja}: lendo páginas...")
    inicial = baixar(base + "/")
    if not inicial:
        return [], {}
    paginas = wix_paginas(base, inicial)
    ofertas, incompletas = {}, []
    for n, caminho in enumerate(paginas):
        if max_paginas and n >= max_paginas:
            break
        # ?page=400 faz o Wix entregar todos os produtos da página de uma vez (até ~2000)
        pagina = baixar(f"{base}/{quote(caminho)}?page=400")
        if not pagina:
            continue
        lista, total = wix_produtos(pagina)
        novos = 0
        for p in lista:
            precos = [v for v in (p.get("price"), p.get("comparePrice")) if v]  # comparePrice = preço promocional
            if not precos or not p.get("urlPart") or p.get("isInStock") is False:
                continue
            url = f"{base}/product-page/{p['urlPart']}"
            nome = re.sub(r"\s+", " ", html.unescape(p.get("name", ""))).strip()
            if url in ofertas:
                # já visto em outra página; se lá ficou sem categoria, aproveita a desta
                if ofertas[url]["categoria"] == "Diversos":
                    ofertas[url]["categoria"] = categoria_produto(nome, caminho)
                continue
            media = p.get("media") or []
            imagem = media[0].get("fullUrl", "") if media else ""
            ofertas[url] = {
                "loja": loja, "url": url, "nome": nome, "marca": "",
                "preco": float(min(precos)),
                "imagem": imagem.replace("w_500,h_500", "w_300,h_300"),
                "categoria": categoria_produto(nome, caminho),
            }
            novos += 1
        if total and len(lista) < total:
            incompletas.append(caminho)
        if lista:
            log(f"  {caminho}: {len(lista)} produtos ({novos} novos)")
    if incompletas:
        log(f"  aviso: {len(incompletas)} páginas de {nome_loja} não vieram completas: {incompletas[:5]}")
    return list(ofertas.values()), {"paginas_incompletas": incompletas}


# ------------------------------------------------ preços informados à mão (planilha)

def slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(texto).lower()).strip("-")


def ler_planilha():
    """Lê a planilha de preços manuais: do Google (se configurado) ou do arquivo local."""
    config = json.loads(ARQ_CONFIG.read_text(encoding="utf-8")) if ARQ_CONFIG.exists() else {}
    url = (config.get("planilha_url") or "").strip()
    if url:
        texto = baixar(url)
        if texto is not None:
            log("Planilha manual: lida do Google")
            return texto
        log("  ! não consegui baixar a planilha do Google, usando o arquivo local")
    if ARQ_MANUAIS.exists():
        return ARQ_MANUAIS.read_text(encoding="utf-8-sig")
    return ""


def coletar_manuais(hoje):
    """Devolve {id_da_loja: [ofertas]} e as lojas novas que só existem na planilha."""
    por_loja = {k: [] for k, v in LOJAS.items() if v.get("manual")}
    extras = {}
    nomes = {slug(k): k for k in LOJAS} | {slug(v["nome"]): k for k, v in LOJAS.items()}
    for n, linha in enumerate(csv.DictReader(io.StringIO(ler_planilha())), start=2):
        linha = {(k or "").strip().lower(): (v or "").strip() for k, v in linha.items()}
        loja_txt, produto = linha.get("loja", ""), linha.get("produto", "")
        if not loja_txt or not produto or produto.startswith("#"):
            continue
        preco = ler_preco("USD " + linha.get("preco_usd", ""))
        if preco is None:
            log(f"  ! planilha, linha {n}: preço inválido ({linha.get('preco_usd')!r}), ignorada")
            continue
        loja = nomes.get(slug(loja_txt))
        if not loja:  # loja que ainda não existe: cria só com o nome
            loja = slug(loja_txt)
            extras[loja] = {"nome": loja_txt, "site": "", "manual": True}
            nomes[loja] = loja
        data = linha.get("data", "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
            m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", data)
            data = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else hoje
        info = LOJAS.get(loja) or extras.get(loja, {})
        por_loja.setdefault(loja, []).append({
            "loja": loja,
            "chave": f"{loja}|manual|{slug(produto)}",
            "url": linha.get("link") or info.get("instagram") or info.get("site", ""),
            "nome": produto,
            "marca": linha.get("marca", ""),
            "preco": preco,
            "imagem": linha.get("imagem", ""),
            "categoria": linha.get("categoria") or categoria_por_texto(produto) or "Diversos",
            "informado": min(data, hoje),
        })
    return por_loja, extras


# ---------------------------------------------------- juntar produtos iguais

RE_TAMANHO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ML|CC|CL|LTS?|LITROS?|L|KG|GRS?|G|OZ)\b")
UNIDADES = {
    "ML": ("ml", 1), "CC": ("ml", 1), "CL": ("ml", 10), "L": ("ml", 1000), "LT": ("ml", 1000),
    "LTS": ("ml", 1000), "LITRO": ("ml", 1000), "LITROS": ("ml", 1000),
    "G": ("g", 1), "GR": ("g", 1), "GRS": ("g", 1), "KG": ("g", 1000), "OZ": ("ml", 29.57),
}
TROCAS = [
    (r"EAU DE PARFUM", " EDP "), (r"EAU DE TOILETTE", " EDT "), (r"EAU DE COLOGNE", " EDC "),
    (r"\b(YEARS?|ANOS|YO)\b", " ANOS "),
    (r"\b(MASCULINO|MASC|HOMME|HOMBRE|MEN|MAN|P/H)\b", " MASC "),
    (r"\b(FEMININO|FEM|FEMME|MUJER|WOMAN|WOMEN|P/M)\b", " FEM "),
    (r"\b(SHAMPO|CHAMPU|XAMPU)\b", " SHAMPOO "),
    (r"\b(CONDITIONER|ACONDICIONADOR)\b", " CONDICIONADOR "),
    (r"\b(DESODORANTE|DEODORANT)\b", " DEO "),
    (r"\bSHIRAZ\b", " SYRAH "),
]
# palavras que definem o "tipo" do produto: se os dois nomes indicam tipo e os tipos diferem,
# não é o mesmo produto (shampoo x condicionador, EDP x EDT, Malbec x Merlot, versão Elixir...)
TIPOS = {
    "SHAMPOO", "CONDICIONADOR", "MASCARA", "DEO", "EDP", "EDT", "EDC", "PARFUM", "EXTRAIT", "ELIXIR",
    "INTENSE", "ABSOLU", "MASC", "FEM", "CABERNET", "MERLOT", "MALBEC", "CARMENERE", "SYRAH", "TANNAT",
    "CHARDONNAY", "PINOT", "TEMPRANILLO", "ROSE", "BLANC", "BRUT", "LIGHT", "ZERO",
}
IGNORAR = {
    "DE", "DEL", "DA", "DO", "DAS", "DOS", "LA", "EL", "LOS", "Y", "E", "CON", "COM", "THE", "AND",
    "DI", "LE", "PARA", "WHISKY", "WHISKEY", "LICOR", "VINHO", "VINO", "CERVEJA", "CERVEZA",
    "PERFUME", "LABEL", "UNIDADE", "UN",
}


def assinatura(oferta):
    texto = sem_acento(f"{oferta['marca']} {oferta['nome']}").upper()
    for padrao, troca in TROCAS:
        texto = re.sub(padrao, troca, texto)
    tamanhos = []
    for numero, unidade in RE_TAMANHO.findall(texto):
        tipo, fator = UNIDADES[unidade]
        tamanhos.append((tipo, round(float(numero.replace(",", ".")) * fator)))
    texto = RE_TAMANHO.sub(" ", texto)
    tokens = {t for t in re.findall(r"[A-Z0-9]+", texto) if t not in IGNORAR and (len(t) > 1 or t.isdigit())}
    return {
        "tipos": tokens & TIPOS,
        "preco": oferta.get("preco") or 0,
        "tam": tuple(sorted(tamanhos)),
        "nums": {t for t in tokens if t.isdigit()},
        "tok": tokens,
    }


def similaridade(a, b):
    if a["tam"] != b["tam"] or a["nums"] != b["nums"]:
        return 0
    if a["tipos"] and b["tipos"] and a["tipos"] != b["tipos"]:
        return 0
    # preço muito diferente costuma ser kit/caixa contra unidade, ou produtos diferentes
    if a["preco"] and b["preco"] and max(a["preco"], b["preco"]) > 2.5 * min(a["preco"], b["preco"]):
        return 0
    comum = len(a["tok"] & b["tok"])
    if comum < 2:
        return 0
    jaccard = comum / len(a["tok"] | b["tok"])
    contido = comum / min(len(a["tok"]), len(b["tok"]))
    # sem tamanho no nome (ml, g...) há menos garantia de ser o mesmo item: exige mais palavras em comum
    if contido < 0.8 or jaccard < (0.45 if a["tam"] else 0.8):
        return 0
    # cada lado tem uma palavra que o outro não tem (ex.: "Sunny Vanilla" x "Nectar"): provável variação diferente
    if a["tok"] - b["tok"] and b["tok"] - a["tok"] and jaccard < 0.75:
        return 0
    return jaccard + contido


def juntar(ofertas):
    """Agrupa ofertas de lojas diferentes que parecem ser o mesmo produto (no máximo uma por loja)."""
    for o in ofertas:
        o["_ass"] = assinatura(o)
    frequencia = Counter(t for o in ofertas for t in o["_ass"]["tok"])
    por_loja = {}
    for o in ofertas:
        por_loja.setdefault(o["loja"], []).append(o)
    grupos, indice = [], {}

    def indexar(g, oferta):
        for t in oferta["_ass"]["tok"]:
            indice.setdefault(t, set()).add(g)

    # começa pela loja com mais produtos; cada loja seguinte é encaixada nos grupos já formados
    for loja in sorted(por_loja, key=lambda l: -len(por_loja[l])):
        lista = por_loja[loja]
        pares = []
        for i, o in enumerate(lista):
            raros = sorted(o["_ass"]["tok"], key=lambda t: frequencia[t])[:3]
            candidatos = set()
            for t in raros:
                candidatos |= indice.get(t, set())
            for g in candidatos:
                if loja in grupos[g]["lojas"]:
                    continue
                nota = max(similaridade(o["_ass"], m["_ass"]) for m in grupos[g]["ofertas"])
                if nota:
                    pares.append((nota, i, g))
        pares.sort(key=lambda x: -x[0])
        usados, ocupados = set(), set()
        for _, i, g in pares:
            if i in usados or g in ocupados:
                continue
            usados.add(i)
            ocupados.add(g)
            grupos[g]["ofertas"].append(lista[i])
            grupos[g]["lojas"].add(loja)
            indexar(g, lista[i])
        for i, o in enumerate(lista):
            if i not in usados:
                grupos.append({"ofertas": [o], "lojas": {loja}})
                indexar(len(grupos) - 1, o)
    for o in ofertas:
        o.pop("_ass", None)
    return [g["ofertas"] for g in grupos]


# ----------------------------------------------------- histórico e exportação

def carregar_historico():
    if ARQ_HISTORICO.exists():
        return json.loads(ARQ_HISTORICO.read_text(encoding="utf-8"))
    return {"ofertas": {}, "ultima_coleta": {}, "cotacoes": {}}


def registrar(hist, ofertas, loja, hoje):
    for o in ofertas:
        reg = hist["ofertas"].setdefault(o.get("chave") or f"{o['loja']}|{o['url']}", {"precos": []})
        reg.update({k: o[k] for k in ("loja", "url", "nome", "marca", "imagem", "categoria")})
        if o.get("informado"):
            reg["informado"] = o["informado"]
        reg["visto_em"] = hoje
        # preço manual vale a partir da data em que foi informado; o coletado, a partir de hoje
        data = o.get("informado") or hoje
        if reg["precos"]:
            data = max(data, reg["precos"][-1][0])
        # guarda só as mudanças de preço: [[data, preço], ...]
        if not reg["precos"] or reg["precos"][-1][1] != o["preco"]:
            if reg["precos"] and reg["precos"][-1][0] == data:
                reg["precos"][-1][1] = o["preco"]
            else:
                reg["precos"].append([data, o["preco"]])
    hist["ultima_coleta"][loja] = hoje


def cotacao_dolar():
    try:
        dados = json.loads(baixar("https://economia.awesomeapi.com.br/json/last/USD-BRL"))
        return float(dados["USDBRL"]["bid"])
    except Exception as e:  # sem cotação o site ainda funciona, só sem reais
        log(f"  ! não consegui a cotação do dólar: {e}")
        return None


def exportar(hist, extras):
    ativas = [
        dict(o, preco=o["precos"][-1][1])
        for o in hist["ofertas"].values()
        if o.get("visto_em") and o["visto_em"] == hist["ultima_coleta"].get(o["loja"])
    ]
    produtos = []
    for grupo in juntar(ativas):
        grupo.sort(key=lambda o: o["preco"])
        principal = min(grupo, key=lambda o: PREFERENCIA_NOME.index(o["loja"]) if o["loja"] in PREFERENCIA_NOME else 99)
        nome = principal["nome"]
        if principal["marca"] and sem_acento(principal["marca"]).upper() not in sem_acento(nome).upper():
            nome = f"{principal['marca']} {nome}"
        produtos.append({
            "id": hashlib.md5(grupo[0]["url"].encode()).hexdigest()[:10],
            "nome": nome,
            "categoria": principal["categoria"],
            "imagem": next((o["imagem"] for o in grupo if o["imagem"]), ""),
            "ofertas": [
                {"loja": o["loja"], "nome": o["nome"], "marca": o["marca"], "url": o["url"],
                 "preco": o["preco"], "historico": o["precos"],
                 **({"informado": o["informado"]} if o.get("informado") else {})}
                for o in grupo
            ],
        })
    cotacoes = hist.get("cotacoes", {})
    ultima = cotacoes[max(cotacoes)] if cotacoes else None
    saida = {
        "atualizado": datetime.now().isoformat(timespec="minutes"),
        "cotacao": {"valor": ultima, "fonte": "dólar comercial (AwesomeAPI)",
                    "lojas": {k: v for k, v in hist.get("cotacao_lojas", {}).items() if v}},
        "lojas": {**hist.get("lojas_extra", {}), **LOJAS},
        "avisos": extras,
        "produtos": produtos,
    }
    ARQ_SITE.parent.mkdir(parents=True, exist_ok=True)
    ARQ_SITE.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    duplas = sum(1 for p in produtos if len(p["ofertas"]) > 1)
    log(f"site/dados.json: {len(produtos)} produtos ({duplas} encontrados em mais de uma loja)")


def main():
    ap = argparse.ArgumentParser(description="Coleta preços dos free shops de Rivera")
    ap.add_argument("--loja", choices=list(LOJAS), help="coletar só esta loja")
    ap.add_argument("--max-paginas", type=int, help="limite de páginas por loja (para testes)")
    ap.add_argument("--so-exportar", action="store_true", help="não coleta, só gera o site/dados.json")
    args = ap.parse_args()

    hoje = datetime.now().strftime("%Y-%m-%d")
    hist = carregar_historico()
    extras = {}
    if not args.so_exportar:
        coletores = {
            "sineriz": coletar_sineriz,
            "neutral": coletar_neutral,
            "yurys": lambda m: coletar_wix("yurys", m),
            "barao": lambda m: coletar_wix("barao", m),
        }
        for loja, coletar in coletores.items():
            if args.loja and args.loja != loja:
                continue
            ofertas, extra = coletar(args.max_paginas)
            extras[loja] = extra
            if ofertas:
                registrar(hist, ofertas, loja, hoje)
                log(f"{LOJAS[loja]['nome']}: {len(ofertas)} produtos coletados")
            else:
                log(f"{LOJAS[loja]['nome']}: nada coletado, mantendo os dados anteriores")
            if extra.get("cotacao_loja"):
                hist.setdefault("cotacao_lojas", {})[loja] = extra["cotacao_loja"]
        if not args.loja or LOJAS.get(args.loja, {}).get("manual"):
            manuais, novas = coletar_manuais(hoje)
            hist.setdefault("lojas_extra", {}).update(novas)
            for loja in set(manuais) | set(hist["lojas_extra"]):
                # registra mesmo vazia: assim, o que saiu da planilha some do site
                registrar(hist, manuais.get(loja, []), loja, hoje)
                if manuais.get(loja):
                    nome = (LOJAS.get(loja) or hist["lojas_extra"][loja])["nome"]
                    log(f"{nome}: {len(manuais[loja])} preços da planilha")
        valor = cotacao_dolar()
        if valor:
            hist["cotacoes"][hoje] = valor
        ARQ_HISTORICO.parent.mkdir(parents=True, exist_ok=True)
        ARQ_HISTORICO.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    exportar(hist, extras)


if __name__ == "__main__":
    main()
