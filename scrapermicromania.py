from playwright.sync_api import sync_playwright
import requests
import traceback
import unicodedata
import re
import os

# ---------------- CONFIG ----------------
SEARCH_QUERY = "Coffret Dresseur d'Elite pokemon"
MAX_PRICE = 60
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Normalisation pour filtrage
def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

keywords = normalize(SEARCH_QUERY).split()

# ---------------- FONCTIONS ----------------
def send_discord_report(products):
    if not products:
        print("⛔ Aucun produit pertinent trouvé, Discord non envoyé")
        return
    message = (
        f"🛒 **Micromania Pokémon – Produits trouvés !** 🎉\n\n"
        f"✅ **{len(products)} produit(s)** sous {MAX_PRICE} €\n"
        f"🔎 Recherche : {SEARCH_QUERY}\n\n"
    )
    for p in products[:10]:
        message += f"- **{p['nom']}** → {p['prix']} € → {p['url']}\n"

    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": message})
        print("Discord envoyé, status code :", r.status_code)
    except Exception as e:
        print("Erreur envoi Discord :", e)

def scrape_micromania(search_query):
    results = []
    seen_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="fr-FR")
            page = context.new_page()

            search_url = f"https://www.micromania.fr/on/demandware.store/Sites-Micromania-Site/fr_FR/Search-Show?q={search_query.replace(' ', '+')}"
            print("Ouverture de la page :", search_url)
            page.goto(search_url, timeout=60000)
            page.wait_for_timeout(2000)  # attendre que la page charge

            # Récupérer les produits
            # Dans la partie evaluate() où on récupère les produits
            products = page.evaluate("""
                () => Array.from(document.querySelectorAll('div.product-tile')).map(item => {
                const nom_el = item.querySelector('a.product-name-link h3');
                const prix_el = item.querySelector('span.value[itemprop="price"]');
                const url_el = item.querySelector('a.product-name-link');

                // Vérification back-in-stock (rupture)
                const stock_btn = item.querySelector('button.back-in-stock');
                const stock = stock_btn ? 'Rupture' : 'En stock';

                const nom = nom_el ? nom_el.innerText.trim() : null;
                const prix = prix_el ? prix_el.innerText.trim().replace(',', '.') : None;
                const url = url_el ? url_el.getAttribute('href') : null;

                return {nom, prix, url, stock};
                })
            """)
            print(f"Produits trouvés sur la page : {len(products)}")

            for p in products:
                if not p["nom"] or not p["url"]:
                    continue

                nom_norm = normalize(p["nom"])

                # ⚡ Filtrage par mots-clés
                if not all(word in nom_norm for word in keywords):
                    print("⏭️ Ignoré (hors recherche) :", p["nom"])
                    continue
                
                # Ignorer les produits en rupture
                if p.get("stock") == "Rupture":
                    print("⏭️ Ignoré (rupture) :", p["nom"])
                    continue
    
                # Vérification prix
                try:
                    prix_float = float(p["prix"]) if p["prix"] else 9999
                    if prix_float > MAX_PRICE:
                        print("⏭️ Ignoré (trop cher) :", p["nom"], p["prix"])
                        continue
                except:
                    print("⏭️ Ignoré (prix non lisible) :", p["nom"], p["prix"])
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
    produits = scrape_micromania(SEARCH_QUERY)
    print("Nombre de produits récupérés :", len(produits))
    for p in produits[:10]:
        print(p)
    send_discord_report(produits)
