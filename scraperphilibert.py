from playwright.sync_api import sync_playwright
import requests
import traceback
import os
import unicodedata

SEARCH_URL = "https://www.philibertnet.com/fr/recherche?search_query=coffret+dresseur+d%27%C3%A9lite"
MAX_PRICE = 70

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
KEYWORDS = ["coffret", "dresseur", "elite"]  # sans accents

def send_discord_report(products):
    if not products:
        print("ℹ️ Aucun produit trouvé sous le prix maximum.")
        return

    message = "🟣 **Philibert – Coffret Dresseur d'Élite détecté !** 🎉\n\n"
    for p in products:
        message += (
            f"🃏 **{p['nom']}**\n"
            f"💰 {p['prix']}\n"
            f"🔗 {p['url']}\n\n"
        )

    requests.post(DISCORD_WEBHOOK, json={"content": message})


def scrape_philibert():
    results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="fr-FR")
            page = context.new_page()

            page.goto(SEARCH_URL, timeout=60000)
            page.wait_for_load_state("networkidle")

            products = page.evaluate("""
                () => Array.from(document.querySelectorAll('li.ajax_block_product')).map(item => {
                    const nameEl = item.querySelector('p.s_title_block a');
                    const priceEl = item.querySelector('span.price');
                    const url = nameEl ? nameEl.href : null;

                    return nameEl && priceEl
                        ? {
                            nom: nameEl.innerText.trim(),
                            prix: priceEl.innerText.trim(),
                            url: url
                        }
                        : null;
                }).filter(Boolean)
            """)

            for p in products:
                # normaliser le nom (minuscules + sans accents)
                nom_clean = unicodedata.normalize("NFD", p["nom"])
                nom_clean = "".join(
                    c for c in nom_clean if unicodedata.category(c) != "Mn"
                ).lower()

                # mots-clés obligatoires
                if not all(k in nom_clean for k in KEYWORDS):
                    continue

                # convertir le prix
                try:
                    prix_float = float(
                        p["prix"]
                        .replace("€", "")
                        .replace(",", ".")
                        .replace("\xa0", "")
                        .strip()
                    )
                except:
                    continue

                if prix_float <= MAX_PRICE:
                    results.append({
                        "nom": p["nom"],
                        "prix": p["prix"],
                        "url": p["url"]
                    })

            browser.close()

    except Exception as e:
        print("❌ Erreur scraping Philibert :", e)
        traceback.print_exc()

    return results


if __name__ == "__main__":
    produits = scrape_philibert()
    send_discord_report(produits)
