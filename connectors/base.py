"""
Interface commune à toutes les sources d'annonces.
eBay (phase 1) + Leboncoin / Catawiki (phase 2) implémentent cette classe.
Le reste du bot (identification, scoring, alerte) ne dépend QUE de cette interface,
donc ajouter une source = écrire une nouvelle classe, sans rien casser ailleurs.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Listing:
    """Annonce normalisée, identique quelle que soit la source."""
    source: str                      # "ebay" | "leboncoin" | "catawiki"
    listing_id: str
    title: str
    price_eur: float
    currency_raw: str
    url: str
    condition: Optional[str] = None  # neuf / occasion / gradé...
    seller: Optional[str] = None
    seller_rating: Optional[float] = None
    image_urls: list = field(default_factory=list)
    is_auction: bool = False
    ends_at: Optional[datetime] = None
    raw: dict = field(default_factory=dict)  # données brutes pour debug


class SourceConnector(ABC):
    """Toute source d'annonces implémente search()."""

    name: str = "abstract"

    @abstractmethod
    def search(self, query: str, max_results: int = 50,
               condition: Optional[str] = None) -> list[Listing]:
        """Retourne une liste de Listing normalisés pour la requête donnée."""
        raise NotImplementedError
