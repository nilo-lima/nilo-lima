#!/usr/bin/env python3
"""
Atualiza as badges do Credly no README.md.
Busca badges dos grupos "Outro" (via Playwright) e "Credly" (via API).

Uso:
    python3 update_badges.py

Instalação única do Playwright (só na primeira vez):
    pip install playwright
    playwright install chromium

Depois de rodar:
    git add README.md
    git commit -m "chore: atualiza badges"
    git push
"""

import urllib.request
import json
import re

USER = "nilo-lima-jr"
README = "README.md"


def fetch_credly_badges():
    """Busca todas as badges do grupo Credly via API JSON."""
    badges = []
    page = 1
    while True:
        url = (
            f"https://www.credly.com/users/{USER}/badges.json"
            f"?page={page}&page_size=48&sort=newest"
        )
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        items = data.get("data", [])
        if not items:
            break

        for b in items:
            bid = b.get("id", "")
            name = b.get("badge_template", {}).get("name", "Badge")
            image = b.get("badge_template", {}).get("image", {})
            img_url = image.get("url", "") if isinstance(image, dict) else str(image)
            img_url = img_url.replace(
                "https://images.credly.com/images/",
                "https://images.credly.com/size/80x80/images/",
            )
            badges.append((bid, name, img_url, f"https://www.credly.com/badges/{bid}"))

        meta = data.get("metadata", {})
        print(f"  Credly API — página {page}/{meta.get('total_pages', 1)}, total={meta.get('total_count', '?')}")
        if page >= meta.get("total_pages", 1):
            break
        page += 1

    return badges


def fetch_outro_badges(credly_ids):
    """Busca badges do grupo Outro via Playwright (requer browser)."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  [Outro] Playwright não instalado — pulando grupo Outro.")
        print("  Para incluir: pip install playwright && playwright install chromium")
        return []

    def is_badges_response(r):
        return "credly.com" in r.url and "badges.json" in r.url and r.status == 200

    outro_raw = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visível para evitar bloqueios
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print("  [Outro] Abrindo perfil do Credly...")
        page.goto(
            f"https://www.credly.com/users/{USER}",
            wait_until="domcontentloaded",
            timeout=45000,
        )

        # Aguarda a chamada de API inicial
        try:
            page.wait_for_response(is_badges_response, timeout=25000)
            print("  [Outro] Página carregada.")
        except PWTimeout:
            print("  [Outro] Aviso: chamada inicial não capturada a tempo.")

        page.wait_for_timeout(1500)

        # Procura a aba Outro/Other
        tab_el = None
        for selector in ['[role="tab"]', "button", "li", "a"]:
            for el in page.query_selector_all(selector):
                try:
                    text = (el.inner_text() or "").strip()
                    if text.lower() in ("outro", "other", "external"):
                        tab_el = el
                        print(f"  [Outro] Aba encontrada: '{text}'")
                        break
                except Exception:
                    pass
            if tab_el:
                break

        if tab_el:
            try:
                with page.expect_response(is_badges_response, timeout=20000) as ri:
                    tab_el.click()
                first_page = ri.value.json()
                outro_raw.extend(first_page.get("data", []))
                meta = first_page.get("metadata", {})
                total_pages = meta.get("total_pages", 1)
                print(f"  [Outro] {meta.get('total_count', '?')} badges encontradas.")

                # Paginação do grupo Outro
                next_url = meta.get("next_page_url")
                p_num = 2
                while next_url and p_num <= total_pages:
                    req = urllib.request.Request(
                        next_url,
                        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(req) as resp:
                        pdata = json.loads(resp.read())
                    outro_raw.extend(pdata.get("data", []))
                    next_url = pdata.get("metadata", {}).get("next_page_url")
                    p_num += 1

            except PWTimeout:
                print("  [Outro] Aba clicada mas API não respondeu.")
        else:
            print("  [Outro] Aba 'Outro' não encontrada.")

        browser.close()

    # Filtra badges que já estão no grupo Credly
    badges = []
    seen = set()
    for b in outro_raw:
        bid = b.get("id", "")
        if bid in credly_ids or bid in seen:
            continue
        seen.add(bid)
        name = b.get("badge_template", {}).get("name", "Badge")
        image = b.get("badge_template", {}).get("image", {})
        img_url = image.get("url", "") if isinstance(image, dict) else str(image)
        img_url = img_url.replace(
            "https://images.credly.com/images/",
            "https://images.credly.com/size/80x80/images/",
        )
        badge_url = (
            f"https://www.credly.com/badges/{bid}"
            if bid
            else f"https://www.credly.com/users/{USER}/badges"
        )
        badges.append((bid, name, img_url, badge_url))

    return badges


def update_readme(outro_badges, credly_badges):
    all_badges = outro_badges + credly_badges
    lines = [f"[![{n}]({i})]({u})" for _, n, i, u in all_badges]
    section = "\n".join(lines)

    with open(README) as f:
        content = f.read()

    new_content = re.sub(
        r"(<!--START_SECTION:badges-->).*?(<!--END_SECTION:badges-->)",
        f"\\1\n{section}\n\\2",
        content,
        flags=re.DOTALL,
    )

    if new_content == content:
        return False

    with open(README, "w") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    print("── Grupo Credly (API) ────────────────────────")
    credly = fetch_credly_badges()
    credly_ids = {bid for bid, *_ in credly}
    print(f"  Total: {len(credly)} badges\n")

    print("── Grupo Outro (Playwright) ──────────────────")
    outro = fetch_outro_badges(credly_ids)
    print(f"  Total: {len(outro)} badges\n")

    print("── Atualizando README.md ─────────────────────")
    changed = update_readme(outro, credly)

    if changed:
        total = len(outro) + len(credly)
        print(f"  README atualizado: {len(outro)} Outro + {len(credly)} Credly = {total} badges\n")
        print("Próximos passos:")
        print("  git add README.md")
        print('  git commit -m "chore: atualiza badges"')
        print("  git push")
    else:
        print("  Nenhuma alteração detectada.")
