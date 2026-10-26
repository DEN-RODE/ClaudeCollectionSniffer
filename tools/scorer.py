"""
Gem Scorer : note chaque annonce /100 en croisant les 3 axes d'une pépite.
  1. DÉCOTE : prix annonce vs comp de marché (sous-coté = bon)
  2. TENDANCE : la pièce monte / stagne / baisse (monte = bon)
  3. QUALITÉ : grader majeur, signaux de valeur, absence de pièges

Les frais sont intégrés (eBay/Catawiki + port + douane potentielle) pour
raisonner en COÛT RÉEL, pas en prix affiché — exactement la logique
mise max = (valeur - frais) qu'on a appliquée à la main.
"""
from dataclasses import dataclass
from tools.identify import Identity


@dataclass
class GemScore:
    score: int
    verdict: str
    max_bid_eur: float | None
    reasons: list[str]


def _real_cost(price_eur: float, source: str, seller_country: str = "EU") -> float:
    """Coût réel = prix + frais plateforme + port + douane estimée."""
    fees = 0.0
    if source == "catawiki":
        fees += price_eur * 0.09          # frais acheteur Catawiki ~9%
    shipping = 8.0                        # port moyen
    customs = price_eur * 0.20 if seller_country not in ("EU", "FR") else 0.0
    return price_eur + fees + shipping + customs


def score_listing(
    price_eur: float,
    source: str,
    ident: Identity,
    comp_median: float | None,
    trend_direction: str,
    seller_country: str = "EU",
    safety_margin: float = 0.85,   # on veut acheter à <=85% de la valeur
) -> GemScore:
    reasons = []
    score = 50  # base neutre

    real_cost = _real_cost(price_eur, source, seller_country)

    # --- Axe 1 : décote vs marché ---
    max_bid = None
    if comp_median:
        # mise max pour rester sous la marge de sécurité, frais déduits
        max_bid = round(comp_median * safety_margin - (real_cost - price_eur), 2)
        ratio = real_cost / comp_median
        if ratio <= 0.70:
            score += 25; reasons.append(f"Très sous-coté ({ratio:.0%} du marché)")
        elif ratio <= 0.85:
            score += 15; reasons.append(f"Sous-coté ({ratio:.0%} du marché)")
        elif ratio <= 1.0:
            score += 5; reasons.append(f"Au prix du marché ({ratio:.0%})")
        else:
            score -= 20; reasons.append(f"SURCOTÉ ({ratio:.0%} du marché)")
    else:
        reasons.append("Pas de comp fiable (tendance maison à construire)")

    # --- Axe 2 : tendance ---
    if trend_direction == "up":
        score += 15; reasons.append("Tendance haussière")
    elif trend_direction == "down":
        score -= 10; reasons.append("Tendance baissière")
    elif trend_direction == "stable":
        reasons.append("Tendance stable")

    # --- Axe 3 : qualité / signaux ---
    if "dt_saber" in ident.signals:
        score += 30; reasons.append("🚨 DT saber = potentiel rarissime")
    if "12_back" in ident.signals:
        score += 10; reasons.append("12-back (première vague 1978)")
    if "moc" in ident.signals:
        score += 8; reasons.append("MOC (sur carte)")
    if ident.is_graded and not ident.grader_is_major:
        score -= 25; reasons.append(f"Grader mineur ({ident.grader}) = décote forte")
    if ident.traps:
        score -= 30; reasons.append(f"⚠️ piège: {', '.join(ident.traps)}")

    score = max(0, min(100, score))
    verdict = (
        "PÉPITE" if score >= 75 else
        "À surveiller" if score >= 55 else
        "Passer"
    )
    return GemScore(score=score, verdict=verdict, max_bid_eur=max_bid, reasons=reasons)


def assess_listing_risk(*, title: str = "", condition: str = "",
                        price_eur: float | None = None, cote_eur: float | None = None,
                        seller_pct: float | None = None, seller_feedback: int | None = None,
                        quantity_available: int | None = None,
                        seller_reviews_text: str = "") -> dict:
    """
    Détecteur d'ARNAQUE / risque vendeur. Renvoie {risk_score:0-100, flags:[...], verdict}.
    Pensé pour les cas vus en vrai : faux Charizard "PSA 9" non gradé à 110€, vendeur 50%.
    """
    flags = []; risk = 0
    t = title.lower(); c = condition.lower()
    # 1) Titre prétend "gradé/PSA/CGC/slab" mais état = non gradé
    claims_graded = any(k in t for k in ["psa", "cgc", "bgs", "graded", "gradé", "slab"])
    if claims_graded and ("non gradé" in c or "ungraded" in c or "sans" in c):
        risk += 45; flags.append("Titre 'gradé' mais état = NON gradé (incohérence)")
    # 2) Prix dérisoire vs cote (trop beau)
    if price_eur and cote_eur and cote_eur > 0 and price_eur < cote_eur * 0.25:
        risk += 35; flags.append(f"Prix {price_eur:.0f}€ << cote ~{cote_eur:.0f}€ (trop beau = suspect)")
    # 3) Quantité multiple pour un objet censé être unique (gradé/vintage)
    if quantity_available and quantity_available > 1 and claims_graded:
        risk += 30; flags.append(f"{quantity_available} exemplaires d'un objet 'unique' (= copies)")
    # 4) Réputation vendeur faible
    if seller_pct is not None and seller_pct < 90:
        risk += 25; flags.append(f"Vendeur {seller_pct:.0f}% positif (faible)")
    if seller_feedback is not None and seller_feedback < 20:
        risk += 10; flags.append(f"Vendeur peu d'historique ({seller_feedback})")
    # 5) Mots d'alerte dans les avis
    if any(w in seller_reviews_text.lower() for w in ["escroc", "arnaque", "copie", "jamais envoyé", "pas rembours", "scam", "fake", "counterfeit"]):
        risk += 40; flags.append("Avis acheteurs signalent arnaque/contrefaçon/non-envoi")
    risk = min(100, risk)
    verdict = ("🚫 ARNAQUE PROBABLE" if risk >= 70 else
               "⚠️ Risque élevé" if risk >= 40 else
               "Risque faible")
    return {"risk_score": risk, "verdict": verdict, "flags": flags}
