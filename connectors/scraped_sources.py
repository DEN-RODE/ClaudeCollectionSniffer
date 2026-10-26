"""
Leboncoin & Catawiki via APIFY (scraping managé). Même interface que eBay :
.search(query) -> list[Listing]. Le reste du bot ne change pas.

Config (.env) :
  APIFY_TOKEN=apify_api_xxx
  APIFY_LEBONCOIN_ACTOR=<owner>/<actor>   (depuis Apify Store)
  APIFY_CATAWIKI_ACTOR=<owner>/<actor>
L'ID d'actor s'écrit "owner~actor" dans l'URL API (on convertit le '/' automatiquement).
"""
import os
import requests
from typing import Optional
from connectors.base import SourceConnector, Listing

APIFY_RUN = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def _to_float(v) -> float:
    """Prix robuste : nombre, '55 €', '1 234,50', {'amount':55}, [55]..."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for k in ("amount", "value", "price", "eur"):
            if k in v:
                return _to_float(v[k])
        return 0.0
    if isinstance(v, (list, tuple)) and v:
        return _to_float(v[0])
    s = str(v).replace(" ", "").replace(" ", "").replace("€", "").replace("EUR", "")
    s = s.replace(",", ".")
    import re
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else 0.0


def _first(d: dict, keys, default=""):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


class ApifySource(SourceConnector):
    """Connecteur générique Apify (sous-classé par site)."""
    name = "apify"

    def __init__(self, token: Optional[str], actor: Optional[str], source_name: str):
        self.token = token or os.environ.get("APIFY_TOKEN", "")
        self.actor = (actor or "").replace("/", "~")
        self.name = source_name

    def _input(self, query: str, max_results: int) -> dict:
        # Beaucoup d'actors acceptent ces clés ; surchargé par sous-classe si besoin.
        return {"query": query, "search": query, "maxItems": max_results, "maxResults": max_results}

    def search(self, query: str, max_results: int = 50,
               condition: Optional[str] = None) -> list[Listing]:
        if not self.token or not self.actor:
            raise RuntimeError(f"{self.name}: APIFY_TOKEN ou actor manquant (.env).")
        r = requests.post(APIFY_RUN.format(actor=self.actor),
                          params={"token": self.token},
                          json=self._input(query, max_results), timeout=180)
        r.raise_for_status()
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        out = []
        for it in items[:max_results]:
            title = _first(it, ["title", "subject", "name", "lot_title"])
            if not title:
                continue
            price = _to_float(_first(it, ["price", "priceValue", "amount", "current_bid", "currentBid", "buyNowPrice"], 0))
            url = _first(it, ["url", "link", "adUrl", "itemUrl", "permalink"])
            img = _first(it, ["image", "imageUrl", "thumbnail", "mainImage"])
            imgs = it.get("images") if isinstance(it.get("images"), list) else ([img] if img else [])
            out.append(Listing(
                source=self.name, listing_id=str(_first(it, ["id", "list_id", "lotId", "itemId", "url"], title)),
                title=str(title), price_eur=price, currency_raw="EUR", url=str(url),
                condition=str(_first(it, ["condition", "state", "etat"], "") or ""),
                seller=str(_first(it, ["seller", "sellerName", "shopName"], "") or "") or None,
                image_urls=[str(u) for u in imgs if u],
                is_auction="bid" in " ".join(it.keys()).lower(),
                raw=it,
            ))
        return out


class LeboncoinConnector(ApifySource):
    def __init__(self, token: Optional[str] = None, actor: Optional[str] = None):
        super().__init__(token, actor or os.environ.get("APIFY_LEBONCOIN_ACTOR", ""), "leboncoin")


class CatawikiConnector(ApifySource):
    def __init__(self, token: Optional[str] = None, actor: Optional[str] = None):
        super().__init__(token, actor or os.environ.get("APIFY_CATAWIKI_ACTOR", ""), "catawiki")
