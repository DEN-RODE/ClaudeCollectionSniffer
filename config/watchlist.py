"""
WATCHLIST DE CIBLES — le "quoi chasser", pas juste "quels mots-clés".

Chaque entrée = une pièce qui vaut le coup, avec :
  - la requête précise pour la trouver,
  - la variante/détail qui fait la valeur (sinon on confond commun et rare),
  - une cote de référence (ref_eur) tenue à jour par le Trend Agent,
  - un prix-cible d'achat (target_buy_eur) = au-dessous = signal d'achat.

Le Curator Agent enrichit/met à jour cette liste (web search + Chroma).
Les cotes ci-dessous sont des ORDRES DE GRANDEUR de départ, à raffiner par le bot.
Niveaux de prix volontairement larges : le marché bouge, le bot recalibre.
"""

WATCHLIST = [

    # ============ STAR WARS — KENNER VINTAGE (80s) ============
    {
        "universe": "kenner_vintage",
        "name": "Darth Vader 12-back Double Telescoping (DT)",
        "query": "kenner star wars darth vader 12 back double telescoping",
        "must_have": ["dt_saber", "12_back"],     # sinon ce n'est PAS la pièce
        "grail": True,
        "ref_eur": 50000, "target_buy_eur": 5000,  # tout sous ce prix = à investiguer
    },
    {
        "universe": "kenner_vintage",
        "name": "Darth Vader MOC 12-back (saber simple)",
        "query": "kenner darth vader 12 back moc afa",
        "must_have": ["12_back", "moc"],
        "ref_eur": 1500, "target_buy_eur": 800,
    },
    {
        "universe": "kenner_vintage",
        "name": "Darth Vader MOC ROTJ/ESB (carte propre)",
        "query": "kenner darth vader return of the jedi moc unpunched",
        "must_have": ["moc"],
        "ref_eur": 150, "target_buy_eur": 90,
    },
    {
        "universe": "kenner_vintage",
        "name": "Boba Fett loose complet (vintage)",
        "query": "kenner boba fett vintage loose complete",
        "must_have": [],
        "ref_eur": 120, "target_buy_eur": 70,
    },

    # ============ COMICS — STAR WARS / MARVEL KEYS ============
    {
        "universe": "comics",
        "name": "Star Wars #1 (1977) 30c CGC 8.5",
        "query": "star wars 1 1977 cgc 8.5 30 cent",
        "must_have": [],          # vérifier 30c (pas reprint 35c losange)
        "avoid": ["35 cent reprint", "diamond", "whitman"],
        "ref_eur": 310, "target_buy_eur": 250,
    },
    {
        "universe": "comics",
        "name": "Star Wars #42 (1ère app Boba Fett comics)",
        "query": "star wars 42 1980 cgc boba fett",
        "must_have": [],
        "ref_eur": 200, "target_buy_eur": 110,
    },
    {
        "universe": "comics",
        "name": "Tales of Suspense #66 (origine Red Skull)",
        "query": "tales of suspense 66 cgc red skull",
        "must_have": [],
        "ref_eur": 110, "target_buy_eur": 50,   # brut OK, garder brut
    },
    {
        "universe": "comics",
        "name": "Marvel Spotlight #5 (1ère app Ghost Rider)",
        "query": "marvel spotlight 5 cgc ghost rider",
        "must_have": [],
        "ref_eur": 250, "target_buy_eur": 100,
    },

    # ============ POKÉMON — VINTAGE GRADÉ ============
    {
        "universe": "pokemon",
        "name": "Charizard Base Set PSA (holo)",
        "query": "pokemon base set charizard psa holo",
        "must_have": [],          # grader majeur exigé (scorer pénalise WCG/GCG)
        "ref_eur": 350, "target_buy_eur": 220,
    },
    {
        "universe": "pokemon",
        "name": "Dark Electrode EX Team Rocket Returns PSA 10",
        "query": "dark electrode team rocket returns psa 10",
        "must_have": [],
        "ref_eur": 190, "target_buy_eur": 120,
    },
    {
        "universe": "pokemon",
        "name": "Évoli/Eeveelutions vintage PSA",
        "query": "pokemon eevee jungle psa 9 vintage",
        "must_have": [],
        "ref_eur": 80, "target_buy_eur": 45,
    },

    # ============ STICKERS / NON-SPORT VINTAGE 80-90s ============
    {
        "universe": "stickers_nonsport",
        "name": "Panini Star Wars album/stickers vintage (80s)",
        "query": "panini star wars sticker album vintage 1977 1983",
        "must_have": [],
        "ref_eur": 120, "target_buy_eur": 60,
    },
    {
        "universe": "stickers_nonsport",
        "name": "Pack scellé Batman 1989 (Topps)",
        "query": "batman 1989 topps sealed pack",
        "must_have": [],
        "ref_eur": 40, "target_buy_eur": 20,
    },
    {
        "universe": "stickers_nonsport",
        "name": "Merlin Pokémon stickers 90s scellé",
        "query": "merlin pokemon sticker sealed packet 1999",
        "must_have": [],
        "ref_eur": 30, "target_buy_eur": 12,
    },
]


def targets_for(universe: str | None = None) -> list[dict]:
    if universe is None:
        return WATCHLIST
    return [t for t in WATCHLIST if t["universe"] == universe]


# ============ SEUILS D'ALERTE (déclencheurs prix) ============
# Le scan ping si une annonce AUTHENTIQUE (pas réédition) matche grade ET prix <= max.
ALERT_TARGETS = [
    {
        "name": "Star Wars #1 (1977) CGC ≥9.2 sous cote",
        "universe": "comics",
        "query": "star wars 1 1977 cgc",
        "graders_ok": ["CGC", "CBCS", "PSA"],   # graders majeurs only
        "min_grade": 9.2,
        "max_price_eur": 330,                     # cote réelle ~250-330€ en 9.2/9.4
        "min_price_eur": 180,                     # plancher : sous ça = réédition/variante (pas le vrai 1er tirage)
        "ref_eur": 300,
        "must_be_first_print": True,
        "avoid": ["reprint", "facsimile", "whitman", "diamond", "35 cent",
                  "35c", "special edition", "treasury", "multi-pack",
                  "dynamic forces", "turkish", "anniversary", "foreign", "2023", "2024", "rep edition", "df edition"],
        "note": "30¢ 1st print uniquement. Slab CGC = pas de risque réédition.",
    },
]


def alert_targets() -> list[dict]:
    return ALERT_TARGETS


# ============ CHASSE GLOBALE "VINTAGE GEEK" (hors thématique perso) ============
# Tout ce qui est neuf/scellé/MOC/gradé et qui se revend bien. Large.
GEEK_QUERIES = [
    # Jeux vidéo rétro scellés / CIB
    "nintendo nes sealed", "super nintendo snes sealed boxed", "n64 sealed",
    "game boy game sealed", "sega megadrive sealed", "playstation 1 sealed",
    "pokemon game boy sealed", "zelda sealed",
    # Cartes gradées (Pokémon, MTG, Yu-Gi-Oh, sport)
    "pokemon wotc psa 10", "pokemon base set psa", "pokemon 1st edition psa",
    "magic the gathering beta psa", "mtg revised dual land", "yugioh 1st edition psa",
    "panini prizm psa rookie", "topps chrome psa rookie",
    # Figurines MOC toutes licences
    "star wars kenner moc afa", "masters of the universe moc", "transformers g1 misb",
    "gi joe arah moc 1985", "tmnt 1988 moc", "power rangers moc 1993",
    "ghostbusters kenner moc", "thundercats moc", "mask kenner moc",
    # Comics gradés keys
    "comic cgc 9.8 key first appearance", "marvel comic cgc key bronze age",
    # Lego scellés retirés
    "lego star wars ucs sealed misb", "lego retired set sealed",
    # Pop culture
    "funko pop grail vaulted exclusive", "hot wheels redline sealed",
]


def geek_queries() -> list[str]:
    return GEEK_QUERIES
