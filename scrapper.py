from playwright.sync_api import sync_playwright
import csv
import time
import requests
import traceback

SEARCH_QUERY = "Coffret cartes Pokémon Dresseur d'Elite"
SEARCH_URL = "https://www.carrefour.fr/s?q=Coffret+cartes+Pokémon+Dresseur+d'Elite"
CSV_FILE = "carrefour_pokemon_filtered.csv"
MAX_PRICE = 60
INTERVAL_MINUTES = 30

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1460333627526221846/t8pcnnbrE-JyiZHxyzImLlzINTRe92bmwRdUIKHfADsla2dZBFmO_nb4nr9QbVn_S-_3"

def send_discord_report(products):
    if not products:
        message = (
            "🛒 **Carrefour Pokémon – Scan terminé**\n"
            "❌ Aucun produit trouvé sous 60 €.\n\n"
            f"🔎 Recherche : {SEARCH_QUERY}"
        )
    else:
        message = (
            "🛒 **Carrefour Pokémon – Produits trouvés !** 🎉\n\n"
            f"✅ **{len(products)} produit(s)** sous 60 €\n"
            f"🔗 Voir la page : {SEARCH_URL}\n\n"
        )
        for p in products[:5]:  # limiter l'affichage
            message += f"- **{p['nom']}** → {p['prix']}\n"

    requests.post(DISCORD_WEBHOOK, json={"content": message})

def scrape_carrefour_fast(search_query):
    results = []
    seen_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--disable-extensions"
                ]
            )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="fr-FR"
            )

            page = context.new_page()
            page.goto(f"https://www.carrefour.fr/s?q={search_query}", timeout=60000)

            try:
                page.click("button:has-text('Accepter')", timeout=3000)
            except:
                pass

            # ⚡ Scroll automatique ultra rapide
            page.evaluate("""
                () => new Promise(resolve => {
                    let totalHeight = 0;
                    const distance = 1500;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 200);
                })
            """)

            page.wait_for_timeout(1000)

            products = page.evaluate("""
                () => Array.from(document.querySelectorAll('li.product-list-grid__item')).map(item => {
                    const nom = item.querySelector('h3.product-card-title__text')?.innerText.trim() || null;
                    const url = item.querySelector('a.c-link[href*="/p/"]')?.getAttribute('href')?.split("?")[0] || null;
                    const priceParts = item.querySelectorAll(
                        "div[data-testid='product-price__amount--main'] p.product-price__content"
                    );
                    const prix = priceParts.length
                        ? Array.from(priceParts).map(p => p.innerText.trim()).join('')
                        : null;
                    return { nom, url, prix };
                })
            """)

            for p in products:
                if not p["url"] or p["url"] in seen_urls:
                    continue
                seen_urls.add(p["url"])

                try:
                    prix_float = float(p["prix"].replace("€", "").replace(",", "."))
                    if prix_float > MAX_PRICE:
                        continue
                except:
                    continue

                results.append({
                    "nom": p["nom"],
                    "prix": p["prix"],
                    "url": p["url"]
                })

            browser.close()

    except Exception as e:
        print("Erreur scraping :", e)
        traceback.print_exc()

    return results

def export_csv(data):
    if not data:
        return
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["nom", "prix", "url"])
        writer.writeheader()
        writer.writerows(data)

if __name__ == "__main__":
    produits = scrape_carrefour_fast(SEARCH_QUERY)
    export_csv(produits)
    send_discord_report(produits)
