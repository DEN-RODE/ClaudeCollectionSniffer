"""
Connecteur eBay — API Browse officielle (gratuite, légale).
Doc: https://developer.ebay.com/api-docs/buy/browse/overview.html

IMPORTANT sur le "gratuit" :
- Browse API = annonces ACTIVES uniquement (ce qui est en vente maintenant).
- Les ventes COMPLÉTÉES (sold) nécessitent l'API Marketplace Insights,
  soumise à validation eBay. Tant qu'on ne l'a pas, la "tendance réalisée"
  vient de PriceCharting (web) + du cache maison (Chroma). Voir tools/market.py.

Auth : OAuth2 client-credentials (App ID / Cert ID depuis developer.ebay.com).
"""
import os
import base64
import re
import time
import requests
from typing import Optional
from connectors.base import SourceConnector, Listing

EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_ITEM_LEGACY_URL = "https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id"
# eBay encode l'item id dans l'URL de l'annonce : .../itm/123456789012
EBAY_ITM_RE = re.compile(r"/itm/(?:[^/]+/)?(\d{9,15})")
# Marketplace FR pour des prix en EUR et des annonces pertinentes
MARKETPLACE = "EBAY_FR"


class EbayConnector(SourceConnector):
    name = "ebay"

    def __init__(self, client_id: str, client_secret: str, marketplace: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.marketplace = marketplace or os.environ.get("EBAY_MARKETPLACE", MARKETPLACE)
        self._token = None
        self._token_expiry = 0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET manquants. "
                "Crée une app gratuite sur developer.ebay.com et remplis le .env."
            )
        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        resp = requests.post(
            EBAY_OAUTH_URL,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 7200))
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            "Content-Type": "application/json",
        }

    def search(self, query: str, max_results: int = 50,
               condition: Optional[str] = None) -> list[Listing]:
        params = {
            "q": query,
            "limit": min(max_results, 200),
            "sort": "newlyListed",
        }
        # eBay condition IDs : 1000=neuf, 3000=occasion. Optionnel.
        filters = []
        if condition == "used":
            filters.append("conditionIds:{3000}")
        if filters:
            params["filter"] = ",".join(filters)

        resp = requests.get(
            EBAY_BROWSE_URL, headers=self._headers(), params=params, timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("itemSummaries", []) or []
        return [self._summary_to_listing(it) for it in items]

    # ---- Évaluation d'une annonce PRÉCISE par URL / id ----
    @staticmethod
    def extract_item_id(url: str) -> Optional[str]:
        """Extrait l'item id (legacy) d'une URL eBay (.../itm/123...)."""
        if not url:
            return None
        m = EBAY_ITM_RE.search(url)
        if m:
            return m.group(1)
        # cas où on passe directement l'id numérique
        if url.strip().isdigit():
            return url.strip()
        return None

    def get_item_by_url(self, url: str) -> Listing:
        """Récupère le détail complet d'une annonce eBay à partir de son URL."""
        item_id = self.extract_item_id(url)
        if not item_id:
            raise ValueError(f"URL eBay non reconnue (pas d'item id) : {url}")
        return self.get_item_by_legacy_id(item_id)

    def get_item_by_legacy_id(self, legacy_id: str) -> Listing:
        """Détail complet d'une annonce via Browse API getItemByLegacyId (gratuit)."""
        resp = requests.get(
            EBAY_ITEM_LEGACY_URL,
            headers=self._headers(),
            params={"legacy_item_id": legacy_id},
            timeout=30,
        )
        resp.raise_for_status()
        return self._item_to_listing(resp.json())

    # ---- Mapping réponse eBay -> Listing normalisé ----
    def _summary_to_listing(self, it: dict) -> Listing:
        price = it.get("price", {})
        return Listing(
            source=self.name,
            listing_id=it.get("itemId", ""),
            title=it.get("title", ""),
            price_eur=float(price.get("value", 0) or 0),
            currency_raw=price.get("currency", "EUR"),
            url=it.get("itemWebUrl", ""),
            condition=it.get("condition"),
            seller=(it.get("seller") or {}).get("username"),
            seller_rating=(it.get("seller") or {}).get("feedbackPercentage"),
            image_urls=[(it.get("image") or {}).get("imageUrl", "")],
            is_auction="AUCTION" in (it.get("buyingOptions") or []),
            raw=it,
        )

    def _item_to_listing(self, it: dict) -> Listing:
        """Mapping de la réponse détaillée getItem (champs plus riches)."""
        price = it.get("price", {})
        loc = (it.get("itemLocation") or {})
        images = []
        if it.get("image"):
            images.append(it["image"].get("imageUrl", ""))
        images += [im.get("imageUrl", "") for im in (it.get("additionalImages") or [])]
        return Listing(
            source=self.name,
            listing_id=it.get("legacyItemId") or it.get("itemId", ""),
            title=it.get("title", ""),
            price_eur=float(price.get("value", 0) or 0),
            currency_raw=price.get("currency", "EUR"),
            url=it.get("itemWebUrl", ""),
            condition=it.get("condition"),
            seller=(it.get("seller") or {}).get("username"),
            seller_rating=(it.get("seller") or {}).get("feedbackPercentage"),
            image_urls=[u for u in images if u],
            is_auction="AUCTION" in (it.get("buyingOptions") or []),
            raw={"description": it.get("description", ""),
                 "country": loc.get("country", ""), **it},
        )
