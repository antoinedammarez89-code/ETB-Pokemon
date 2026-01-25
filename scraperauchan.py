from playwright.sync_api import sync_playwright
import csv
import requests
import traceback

# ---------------- CONFIG ----------------
SEARCH_QUERY = "Coffret Dresseur d'Elite pokemon"
MAX_PRICE = 60
CSV_FILE = "auchan_pokemon_filtered.csv"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1460333627526221846/t8pcnnbrE-JyiZHxyzImLlzINTRe92bmwRdUIKHfADsla2dZBFmO_nb4nr9QbVn_S-_3"  # ← mets ton webhook Discord ici

keywords = [w.lower() for w in SEARCH_QUERY.split()]

# ---------------- FONCTIONS ----------------
def send_discord_report(products):
    if not products:
        print("⛔ Aucun produit pertinent trouvé, Discord non envoyé")
        return
    message = (
        f"🛒 **Auchan Pokémon – Produits trouvés !** 🎉\n\n"
        f"✅ **{len(products)} produit(s)** sous {MAX_PRICE} €\n"
        f"🔎 Recherche : {SEARCH_QUERY}\n\n"
    )
    for p in products[:10]:
        message += f"- **{p['nom']}** → {p['prix']} → https://www.auchan.fr{p['url']}\n"

    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": message})
        print("Discord envoyé, status code :", r.status_code)
    except Exception as e:
        print("Erreur envoi Discord :", e)


def scrape_auchan(search_query):
    results = []
    seen_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="fr-FR")
            page = context.new_page()
            
            # ⚡ Lien correct pour Auchan
            search_url = f"https://www.auchan.fr/recherche?text={search_query.replace(' ', '%20')}"
            print("Ouverture de la page :", search_url)
            page.goto(search_url, timeout=60000)

            # Scroll pour charger lazy-load
            page.evaluate("""
                () => new Promise(resolve => {
                    let totalHeight = 0;
                    const distance = 1500;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if(totalHeight >= scrollHeight){
                            clearInterval(timer);
                            resolve();
                        }
                    }, 200);
                })
            """)
            page.wait_for_timeout(1000)

            # Récupérer les produits
            products = page.evaluate("""
                () => Array.from(document.querySelectorAll('article.product-thumbnail')).map(item => {
                    const nom_el = item.querySelector('.product-thumbnail__description');
                    const prix_el = item.querySelector('.product-price');
                    const url_el = item.querySelector('a.product-thumbnail__details-wrapper');

                    const nom = nom_el ? nom_el.innerText.trim() : null;
                    const prix = prix_el ? prix_el.innerText.trim() : null;
                    const url = url_el ? url_el.getAttribute('href') : null;

                    return {nom, prix, url};
                })
            """)
            print(f"Produits trouvés sur la page : {len(products)}")

            for p in products:
                if not p["nom"] or not p["url"]:
                    continue
                nom_lower = p["nom"].lower()

                # ⚡ Filtrage par mots-clés
                if not all(word in nom_lower for word in keywords):
                    print("Produit ignoré (non pertinent) :", p["nom"])
                    continue

                # Vérification prix
                try:
                    prix_float = float(p["prix"].replace("€","").replace(",",".")) if p["prix"] else 9999
                    if prix_float > MAX_PRICE:
                        print("Produit ignoré (trop cher) :", p["nom"], p["prix"])
                        continue
                except:
                    print("Produit ignoré (prix non lisible) :", p["nom"], p["prix"])
                    continue

                if p["url"] in seen_urls:
                    continue
                seen_urls.add(p["url"])

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

# ---------------- MAIN ----------------
if __name__ == "__main__":
    produits = scrape_auchan(SEARCH_QUERY)
    print("Nombre de produits récupérés :", len(produits))
    for p in produits[:10]:
        print(p)
    send_discord_report(produits)
