"""Tests offline du GemScorer (frais réels, 3 axes, verdicts)."""
from tools.identify import Identity
from tools.scorer import score_listing


def _ident(**kw):
    return Identity(**kw)


def test_dt_saber_est_pepite():
    gem = score_listing(
        price_eur=3000, source="ebay",
        ident=_ident(signals=["dt_saber", "12_back", "moc"], grader_is_major=True),
        comp_median=50000, trend_direction="up",
    )
    assert gem.score >= 75
    assert gem.verdict == "PÉPITE"


def test_surcote_rejete():
    gem = score_listing(
        price_eur=200, source="ebay",
        ident=_ident(signals=[]),
        comp_median=110, trend_direction="stable",
    )
    assert gem.score < 55
    assert gem.verdict == "Passer"


def test_grader_mineur_decote():
    bon = score_listing(120, "ebay", _ident(is_graded=True, grader="CGC",
                        grader_is_major=True), comp_median=200, trend_direction="stable")
    mauvais = score_listing(120, "ebay", _ident(is_graded=True, grader="WCG",
                        grader_is_major=False), comp_median=200, trend_direction="stable")
    assert mauvais.score < bon.score


def test_repro_est_penalise():
    gem = score_listing(
        price_eur=30, source="ebay",
        ident=_ident(traps=["reproduction"]),
        comp_median=150, trend_direction="up",
    )
    assert any("piège" in r for r in gem.reasons)


def test_mise_max_integre_les_frais_catawiki():
    gem = score_listing(
        price_eur=100, source="catawiki",
        ident=_ident(), comp_median=200, trend_direction="stable",
    )
    # mise max = comp*0.85 - frais (catawiki 9% + port) => < 170
    assert gem.max_bid_eur is not None
    assert gem.max_bid_eur < 170


def test_douane_hors_ue_alourdit_le_cout():
    eu = score_listing(100, "ebay", _ident(), comp_median=120,
                       trend_direction="stable", seller_country="EU")
    us = score_listing(100, "ebay", _ident(), comp_median=120,
                       trend_direction="stable", seller_country="US")
    # hors UE : douane => ratio coût/marché plus haut => score <= EU
    assert us.score <= eu.score
