#!/usr/bin/env python3
"""
Atualiza as badges do Credly no README.md.

Uso:
    python3 update_badges.py

Depois:
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
            badges.append((name, img_url, f"https://www.credly.com/badges/{bid}"))

        meta = data.get("metadata", {})
        print(f"  Página {page}/{meta.get('total_pages', 1)} — {meta.get('total_count', '?')} badges no total")
        if page >= meta.get("total_pages", 1):
            break
        page += 1

    return badges


def update_readme(badges):
    lines = [f"[![{n}]({i})]({u})" for n, i, u in badges]
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
        print("Nenhuma alteração detectada no README.")
        return False

    with open(README, "w") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    print("Buscando badges do Credly...")
    badges = fetch_credly_badges()
    print(f"Total encontrado: {len(badges)} badges\n")

    print("Atualizando README.md...")
    changed = update_readme(badges)

    if changed:
        print(f"README.md atualizado com {len(badges)} badges.")
        print("\nPróximos passos:")
        print("  git add README.md")
        print('  git commit -m "chore: atualiza badges"')
        print("  git push")
    else:
        print("Nada a fazer.")
