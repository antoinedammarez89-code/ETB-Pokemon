from playwright.sync_api import sync_playwright
import requests
import traceback

# ---------------- CONFIG ----------------
SEARCH_URL = "https://www.e.leclerc/recherche?q=Coffret%20Dresseur%20d%27Elite%20pokemon#seller_list=group::E.Leclerc"
SEARCH_QUERY = "Coffret Dresseur d'Elite pokemon"
MAX_PRICE = 60
import os
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

keywords = [w.lower().replace("'", "") for w in SEARCH_QUERY.split()]

# ---------------- SCRAPER ----------------
def scrape_leclerc():
    results = []
    seen_urls = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="fr-FR")
        print("🔎 Ouverture :", SEARCH_URL)
        page.goto(SEARCH_URL, timeout=60000)

        # Scroll lazy-load
        page.evaluate("""
            () => new Promise(resolve => {
                let h = 0;
                const i = setInterval(() => {
                    window.scrollBy(0, 1500);
                    h += 1500;
                    if (h >= document.body.scrollHeight) {
                        clearInterval(i);
                        resolve();
                    }
                }, 300);
            })
        """)

        page.wait_for_timeout(1000)

        products = page.query_selector_all("li.product-container")
        print("📦 Produits détectés :", len(products))

        for item in products:
            nom_el = item.query_selector(".product-label")
            url_el = item.query_selector("a.product-card-link")
            price_unit = item.query_selector(".price-unit")
            price_cents = item.query_selector(".price-cents")

            nom = nom_el.inner_text().strip() if nom_el else None
            url = url_el.get_attribute("href") if url_el else None
            if url and url.startswith("/"):
                url = "https://www.e.leclerc" + url

            if price_unit and price_cents:
                prix = price_unit.inner_text().strip() + price_cents.inner_text().strip()
            else:
                prix = None

            print(f"\n🔹 Brut : {nom} | {prix} | {url}")

            if not nom or not url or not prix:
                print("  ❌ Incomplet")
                continue

            nom_clean = nom.lower().replace("'", "")
            if not all(k in nom_clean for k in keywords):
                print("  ⚠ Hors recherche")
                continue

            try:
                prix_float = float(prix.replace("€", "").replace(",", "."))
                if prix_float > MAX_PRICE:
                    print("  💸 Trop cher")
                    continue
            except:
                print("  ⚠ Prix illisible")
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            print("  ✅ Ajouté")
            results.append({"nom": nom, "prix": prix, "url": url})

        browser.close()
    return results

# ---------------- DISCORD ----------------
def send_discord(products):
    if not products:
        print("⛔ Aucun produit pertinent")
        return

    msg = "🛒 **Leclerc – Pokémon ETB détectés** 🎉\n\n"
    for p in products:
        msg += f"- **{p['nom']}** → {p['prix']} → {p['url']}\n"

    requests.post(DISCORD_WEBHOOK, json={"content": msg})

# ---------------- MAIN ----------------
if __name__ == "__main__":
    produits = scrape_leclerc()
    print("\n📊 Résultat final :", len(produits))
    send_discord(produits)
