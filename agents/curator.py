"""
Curator Agent — le "cerveau stratégique" qui décide QUOI chasser.

Deux missions :
1. DÉCOUVERTE : pour chaque univers, identifier les "top objets" (grails + keys
   accessibles) que l'utilisateur devrait viser — exactement comme sortir
   "Star Wars #1/#42/#66, Vader 12-back DT" à la main, mais en autonome.
2. CALIBRAGE : tenir à jour ref_eur (cote) et target_buy_eur (prix d'achat malin)
   à partir des données de tendance accumulées (Chroma) + web.

Il enrichit WATCHLIST. Le Scout chasse ensuite ces cibles précises au meilleur prix.

En gratuit : il s'appuie sur la recherche web (price guides publics : PriceCharting,
GoCollect, Heritage, actionfigure411) + la mémoire Chroma. Le LLM (Claude) structure
les trouvailles en cibles. À router via LiteLLM pour le coût.
"""
import json
from config.watchlist import WATCHLIST


CURATOR_PROMPT = """Tu es un expert en collectibles vintage (Star Wars Kenner, comics
Marvel/SW key issues, Pokémon gradé, stickers/non-sport 80-90s).

Pour l'univers "{universe}", liste les 5 à 10 pièces les plus pertinentes à viser
pour un collectionneur qui veut le TOP au meilleur prix. Pour chacune, donne :
- name : la pièce + la variante/détail EXACT qui fait la valeur
- query : la requête de recherche marketplace la plus efficace
- must_have : les détails obligatoires sans lesquels ce n'est pas la bonne pièce
- avoid : les pièges/variantes sans valeur à exclure (rééditions, reprints...)
- ref_eur : cote de référence actuelle (ordre de grandeur, marché EU)
- target_buy_eur : prix d'achat malin (décote ~25-40% sous la cote)
- rationale : 1 phrase sur pourquoi cette pièce (rareté/demande/tendance)

Base-toi sur les ventes réelles récentes, pas les prix affichés gonflés.
Privilégie les pièces à demande DURABLE (persos iconiques), pas le hype passager.
Renvoie UNIQUEMENT du JSON : une liste d'objets avec ces champs."""


def discover_targets(universe: str, anthropic_client, web_search_tool) -> list[dict]:
    """
    Découvre/rafraîchit les cibles d'un univers.
    Pipeline : web_search (price guides) -> contexte -> LLM structure en cibles JSON.
    """
    # 1. Récupérer du contexte marché frais via recherche web
    context = web_search_tool(f"top key issues grails {universe} value price guide 2026")

    # 2. Demander au LLM de structurer en cibles exploitables
    # resp = anthropic_client.messages.create(
    #     model="claude-...",  # routé via LiteLLM
    #     max_tokens=2000,
    #     messages=[{"role": "user",
    #                "content": CURATOR_PROMPT.format(universe=universe)
    #                           + "\n\nContexte marché:\n" + context}],
    # )
    # return json.loads(resp.content[0].text)
    raise NotImplementedError(
        "Brancher anthropic_client + web_search. Le résultat enrichit WATCHLIST."
    )


def recalibrate_prices(trend_memory) -> None:
    """
    Met à jour ref_eur/target_buy_eur de chaque cible WATCHLIST à partir des prix
    réellement observés (mémoire Chroma). Le bot apprend les vraies cotes au fil du temps.
    """
    for target in WATCHLIST:
        key = target["name"].lower().replace(" ", "_")
        t = trend_memory.trend(key)
        if t.get("direction") != "insufficient_data" and t.get("n", 0) >= 5:
            # ici : recalculer ref_eur = médiane récente observée, ajuster target_buy
            pass  # implémentation phase 1.5 quand la base Chroma est remplie
