#!/usr/bin/env python3
"""
Atualiza as badges do Credly no README.md.
Busca badges dos grupos "Outro" (via Playwright) e "Credly" (via API).

Uso:
    python3 update_badges.py

Instalação única do Playwright (só na primeira vez):
    pip install playwright --break-system-packages
    playwright install chromium

Depois de rodar:
    git add README.md
    git commit -m "chore: atualiza badges"
    git push
"""

import re
import json
import urllib.request

USER = "nilo-lima-jr"
README = "README.md"


# ── Grupo Outro ───────────────────────────────────────────────────────────────

def fetch_outro_badges():
    """
    Carrega o perfil do Credly com Playwright e intercepta a chamada à API
    de badges externos (/external_badges/open_badges/public).
    A página já faz essa chamada automaticamente na carga inicial.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Outro] Playwright não instalado — pulando grupo Outro.")
        print("  Para incluir: pip install playwright --break-system-packages")
        print("                playwright install chromium")
        return []

    captured = []
    user_uuid = None

    def on_response(r):
        nonlocal user_uuid
        if (
            "credly.com" in r.url
            and "external_badges/open_badges/public" in r.url
            and r.status == 200
        ):
            try:
                data = r.json()
                captured.append(data)
                m = re.search(r"/users/([0-9a-f-]{36})/", r.url)
                if m and not user_uuid:
                    user_uuid = m.group(1)
                meta = data.get("metadata", {})
                print(
                    f"  [Outro] API capturada — "
                    f"{meta.get('total_count', '?')} badges, "
                    f"{meta.get('total_pages', 1)} página(s)"
                )
            except Exception as e:
                print(f"  [Outro] Erro ao processar resposta: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page.on("response", on_response)
        page.goto(
            f"https://www.credly.com/users/{USER}",
            wait_until="domcontentloaded",
            timeout=45000,
        )
        page.wait_for_timeout(8000)
        browser.close()

    if not captured:
        print("  [Outro] Nenhuma resposta capturada.")
        return []

    # Coleta badges da primeira página
    badges_raw = list(captured[0].get("data", []))

    # Paginação adicional via chamada direta (raro, mas suportado)
    if user_uuid:
        meta = captured[0].get("metadata", {})
        total_pages = meta.get("total_pages", 1)
        for p_num in range(2, total_pages + 1):
            url = (
                f"https://www.credly.com/api/v1/users/{user_uuid}"
                f"/external_badges/open_badges/public?page={p_num}&page_size=48"
            )
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req) as resp:
                pdata = json.loads(resp.read())
            badges_raw.extend(pdata.get("data", []))

    # Formata para (id, nome, img_url, badge_url)
    result = []
    for b in badges_raw:
        bid = b.get("id", "")
        ext = b.get("external_badge", {})
        name = ext.get("badge_name", "Badge")
        img_url = ext.get("image_url", "")
        badge_url = ext.get("badge_url") or f"https://www.credly.com/users/{USER}/badges"
        result.append((bid, name, img_url, badge_url))

    return result


# ── Grupo Credly ──────────────────────────────────────────────────────────────

def fetch_credly_badges():
    """Busca todas as badges do grupo Credly via API JSON pública."""
    badges = []
    page = 1
    while True:
        url = (
            f"https://www.credly.com/users/{USER}/badges.json"
            f"?page={page}&page_size=48&sort=newest"
        )
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
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
        print(
            f"  [Credly] Página {page}/{meta.get('total_pages', 1)} — "
            f"{meta.get('total_count', '?')} badges no total"
        )
        if page >= meta.get("total_pages", 1):
            break
        page += 1

    return badges


# ── README ────────────────────────────────────────────────────────────────────

def update_readme(outro, credly):
    credly_ids = {bid for bid, *_ in credly}

    # Remove do Outro qualquer badge que também esteja no Credly
    outro_filtered = [(bid, n, i, u) for bid, n, i, u in outro if bid not in credly_ids]

    all_badges = outro_filtered + credly
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
        return 0

    with open(README, "w") as f:
        f.write(new_content)

    return len(all_badges)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── Grupo Outro (Playwright) ──────────────────")
    outro = fetch_outro_badges()
    print(f"  Total: {len(outro)} badges\n")

    print("── Grupo Credly (API) ────────────────────────")
    credly = fetch_credly_badges()
    print(f"  Total: {len(credly)} badges\n")

    print("── Atualizando README.md ─────────────────────")
    total = update_readme(outro, credly)

    if total:
        print(f"  README atualizado: {len(outro)} Outro + {len(credly)} Credly = {total} badges\n")
        print("Próximos passos:")
        print("  git add README.md")
        print('  git commit -m "chore: atualiza badges"')
        print("  git push")
    else:
        print("  Nenhuma alteração detectada.")
