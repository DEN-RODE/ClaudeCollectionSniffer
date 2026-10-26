"""
Outil Market + Trend (version GRATUITE, point 3).

Stratégie sans API payante :
1. COMP de marché : on récupère le prix de référence via
   - eBay Browse (médiane des annonces actives similaires) = "prix demandé"
   - + scraping léger PriceCharting (page publique) = "prix réalisé" approx.
2. TENDANCE : on stocke chaque prix observé dans Chroma, daté.
   Au fil des semaines, le bot construit SA base historique -> tendance maison,
   indépendante de GoCollect/PriceCharting payants.

Quand un budget API arrivera, on remplace get_comp() par un appel GoCollect,
sans rien changer au reste.
"""
import statistics
from datetime import datetime, timezone
from connectors.base import Listing


def get_comp_from_active(listings: list[Listing]) -> dict:
    """Comp grossier = médiane des annonces actives similaires (gratuit, Browse API)."""
    prices = [l.price_eur for l in listings if l.price_eur > 0]
    if not prices:
        return {"comp_median": None, "n": 0}
    return {
        "comp_median": statistics.median(prices),
        "comp_min": min(prices),
        "comp_max": max(prices),
        "n": len(prices),
    }


class TrendMemory:
    """
    Mémoire de tendance maison sur Chroma.
    Clé = identifiant normalisé de la pièce (ex: 'kenner_vader_rotj_77back_moc').
    On stocke (date, prix) pour calculer une dynamique 30j/90j nous-mêmes.
    """
    def __init__(self, chroma_collection):
        self.col = chroma_collection  # collection Chroma injectée

    def record(self, item_key: str, price_eur: float, source: str):
        self.col.add(
            documents=[f"{item_key} {price_eur} {source}"],
            metadatas=[{
                "item_key": item_key,
                "price_eur": price_eur,
                "source": source,
                "ts": datetime.now(timezone.utc).isoformat(),
            }],
            ids=[f"{item_key}-{datetime.now(timezone.utc).timestamp()}"],
        )

    def trend(self, item_key: str, days: int = 90) -> dict:
        """Récupère l'historique stocké et calcule la pente (hausse/baisse/stable)."""
        res = self.col.get(where={"item_key": item_key})
        metas = res.get("metadatas", []) or []
        points = sorted(
            [(m["ts"], m["price_eur"]) for m in metas],
            key=lambda x: x[0],
        )
        if len(points) < 3:
            return {"direction": "insufficient_data", "n": len(points)}
        first = statistics.mean([p for _, p in points[: max(1, len(points)//3)]])
        last = statistics.mean([p for _, p in points[-max(1, len(points)//3):]])
        change = (last - first) / first if first else 0
        direction = (
            "up" if change > 0.05 else "down" if change < -0.05 else "stable"
        )
        return {"direction": direction, "change_pct": round(change * 100, 1),
                "n": len(points)}


# --- Helpers d'intégration (clé de tendance + init Chroma) ---
import re as _re


def normalize_key(name: str) -> str:
    """Clé de pièce stable pour la mémoire de tendance (ex: 'darth_vader_12_back')."""
    s = name.lower().strip()
    s = _re.sub(r"[^a-z0-9]+", "_", s)
    return _re.sub(r"_+", "_", s).strip("_")


def get_trend_collection(path: str = "./chroma_gemhunter", name: str = "trend"):
    """
    Ouvre (ou crée) la collection Chroma persistante pour TrendMemory.
    Import paresseux : si chromadb n'est pas installé, on retourne None et le bot
    fonctionne quand même (tendance = insufficient_data).
    """
    try:
        import chromadb
    except ImportError:
        return None
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(name)
