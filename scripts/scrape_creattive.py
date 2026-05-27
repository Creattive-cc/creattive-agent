"""
scripts/scrape_creattive.py — Scraper do site da Creattive.
O site é uma SPA React; o conteúdo é extraído diretamente do bundle JS.
Salva conteúdo estruturado em knowledge/creattive.md.
"""

import re
import httpx
import pathlib

BASE_URL = "https://creattive.cc/"
OUTPUT = pathlib.Path("knowledge/creattive.md")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_bundle(client: httpx.Client) -> str:
    home = client.get(BASE_URL)
    home.raise_for_status()
    # Localizar URL do bundle principal
    m = re.search(r'src="(/assets/index-[^"]+\.js)"', home.text)
    if not m:
        raise RuntimeError("Bundle JS não encontrado na página inicial.")
    bundle_url = BASE_URL.rstrip("/") + m.group(1)
    print(f"  Bundle: {bundle_url}")
    resp = client.get(bundle_url)
    resp.raise_for_status()
    return resp.text


def unique(lst: list) -> list:
    return list(dict.fromkeys(lst))


def extract_strings(js: str, pattern: str, min_words: int = 3) -> list[str]:
    CODE_CHARS = set("{}[];=<>/\\")
    matches = re.findall(pattern, js)
    result = []
    for s in matches:
        words = s.split()
        if len(words) < min_words:
            continue
        code_ratio = sum(1 for c in s if c in CODE_CHARS) / max(len(s), 1)
        if code_ratio > 0.08:
            continue
        letter_ratio = sum(1 for c in s if c.isalpha()) / max(len(s), 1)
        if letter_ratio < 0.45:
            continue
        result.append(s.strip())
    return unique(result)


def extract_product_cards(js: str) -> list[dict]:
    """Extrai cards de produto no formato {image:..., description:..., link:...}"""
    cards = []
    for m in re.finditer(
        r'\{image:"([^"]+)",description:"([^"]+)",link:"([^"]+)"\}', js
    ):
        cards.append({"image": m.group(1), "description": m.group(2), "link": m.group(3)})
    return cards


def extract_value_props(js: str) -> list[dict]:
    """Extrai pares {title, description} de diferenciais/valores."""
    pairs = []
    for m in re.finditer(r'title:"([^"]{10,150})",description:"([^"]{20,400})"', js):
        t, d = m.group(1).strip(), m.group(2).strip()
        if len(t.split()) < 2 or len(d.split()) < 4:
            continue
        code_chars = sum(1 for c in t + d if c in "{}[];=<>/\\")
        if code_chars > (len(t) + len(d)) * 0.06:
            continue
        pairs.append({"title": t, "description": d})
    return unique_dicts(pairs)


def unique_dicts(lst: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for d in lst:
        key = tuple(d.values())
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


PRODUCT_ROUTES = {
    "/creattive_minds": "Creattive Minds",
    "/farol360": "Farol 360",
    "/integra": "Integra+",
    "/sentinela_digital": "Sentinela Digital",
    "/guardiao_creattive": "Guardião Creattive",
    "/data_safe_point": "Data Safe Point",
    "/google_partner": "Google Partner",
    "/creattive": "Sobre a Creattive",
    "/parceiros": "Parceiros",
    "/trabalhe_conosco": "Trabalhe Conosco",
    "/contato": "Contato",
}

# Palavras que descartam strings de UI genérico
UI_NOISE_PREFIXES = (
    "Selecione", "Essa é a imagem", "Nenhum post", "Nenhum artigo",
    "Faça login", "Entrar no Painel", "Sair do Sistema", "Criar nova",
    "Conteúdo do Post", "Categoria do Post", "Gerencie suas",
    "©", "Política de Privacidade", "Canal de Denúncias",
)
UI_NOISE_EXACT = {
    "saiba qual é o seu plano ideal",
    "Descubra como a Creattive pode simplificar sua tecnologia!",
}


def is_noise(s: str) -> bool:
    if len(s) < 20:
        return True
    sl = s.lower()
    if sl in {n.lower() for n in UI_NOISE_EXACT}:
        return True
    return any(s.startswith(p) for p in UI_NOISE_PREFIXES)


# ── Extração por seção ────────────────────────────────────────────────────────

def extract_section(js: str, route: str) -> list[str]:
    """
    Extrai strings de texto em torno da definição de rota no bundle.
    Janela de ±30000 chars em volta da primeira menção à rota.
    """
    idx = js.find(f'"{route}"')
    if idx == -1:
        idx = js.find(f"'{route}'")
    if idx == -1:
        return []
    window = js[max(0, idx - 5000): idx + 30000]

    lines: list[str] = []
    for pat in [
        r'children:"([^"]{15,500})"',
        r'description:"([^"]{20,400})"',
        r'title:"([^"]{10,200})"',
        r'subtitle:"([^"]{10,300})"',
        r'label:"([^"]{10,200})"',
        r'text:"([^"]{15,400})"',
        r'content:"([^"]{20,500})"',
    ]:
        lines.extend(extract_strings(window, pat, min_words=3))
    return [s for s in unique(lines) if not is_noise(s)]


# ── Builder do Markdown ───────────────────────────────────────────────────────

def build_markdown(js: str) -> str:
    sections: list[str] = []

    # ── Cabeçalho ──
    sections.append("# Creattive — Base de Conhecimento\n")
    sections.append(
        "*Conteúdo extraído automaticamente do site https://creattive.cc/*\n"
    )

    # ── Visão geral da empresa (home) ──
    home_strings = extract_strings(
        js[: 60000],  # primeiro terço do bundle (componentes home)
        r'children:"([^"]{20,500})"',
        min_words=4,
    ) + extract_strings(js[:60000], r'description:"([^"]{30,400})"', min_words=4)
    home_strings = [s for s in unique(home_strings) if not is_noise(s)]

    if home_strings:
        sections.append("\n---\n\n## Página Inicial / Visão Geral\n")
        for s in home_strings[:30]:
            sections.append(f"- {s}")

    # ── Produtos (cards da home) ──
    cards = extract_product_cards(js)
    if cards:
        sections.append("\n---\n\n## Produtos e Soluções — Cards da Home\n")
        for c in cards:
            name = PRODUCT_ROUTES.get(c["link"], c["link"])
            sections.append(f"### {name}\n")
            sections.append(f"{c['description']}\n")

    # ── Diferenciais / valores ──
    vp = extract_value_props(js)
    if vp:
        sections.append("\n---\n\n## Diferenciais e Valores\n")
        for p in vp[:20]:
            sections.append(f"**{p['title']}:** {p['description']}")

    # ── Seção por rota (deduplica globalmente) ──
    global_seen: set[str] = set()
    for route, label in PRODUCT_ROUTES.items():
        content = extract_section(js, route)
        # Remover strings já vistas em seções anteriores
        new_content = [s for s in content if s not in global_seen]
        global_seen.update(new_content)
        if not new_content:
            continue
        sections.append(f"\n---\n\n## {label} ({route})\n")
        for line in new_content[:40]:
            sections.append(f"- {line}")

    # ── Endereço e contato (rodapé) ──
    footer_patterns = [
        r'(Rua [^"]{10,100})',
        r'(CNPJ[^"]{5,30})',
        r'(\+55[^"]{5,20})',
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
    ]
    footer_lines = []
    for pat in footer_patterns:
        footer_lines.extend(re.findall(pat, js))
    if footer_lines:
        sections.append("\n---\n\n## Informações de Contato\n")
        for fl in unique(footer_lines):
            sections.append(f"- {fl}")

    return "\n".join(sections) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Buscando bundle de {BASE_URL}…")
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        js = fetch_bundle(client)

    print(f"Bundle carregado ({len(js):,} chars). Extraindo conteúdo…")
    md = build_markdown(js)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(md, encoding="utf-8")

    lines = md.count("\n")
    words = len(md.split())
    print(f"Salvo em {OUTPUT} ({lines} linhas, {words} palavras).")
