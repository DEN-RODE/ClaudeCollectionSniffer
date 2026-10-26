"""Tests offline de l'identification (règles, pas de réseau ni LLM)."""
from tools.identify import identify


def test_grader_majeur_detecte():
    ident = identify("Pokemon Charizard Base Set PSA 9 holo")
    assert ident.is_graded
    assert ident.grader == "PSA"
    assert ident.grade == 9.0
    assert ident.grader_is_major is True


def test_grader_mineur_penalise():
    ident = identify("Star Wars #1 WCG 9.8")
    assert ident.grader == "WCG"
    assert ident.grader_is_major is False
    assert "grader mineur" in ident.notes


def test_dt_saber_signal():
    ident = identify("Kenner Darth Vader 12-back double telescoping MOC")
    assert "dt_saber" in ident.signals
    assert "12_back" in ident.signals
    assert "moc" in ident.signals


def test_repro_piege():
    ident = identify("Star Wars Black Series Darth Vader reproduction")
    assert ident.traps  # au moins un piège
    assert any(t in ("black series", "reproduction") for t in ident.traps)


def test_vader_rotj_commun_pas_de_signal_rare():
    ident = identify("Kenner Darth Vader Return of the Jedi loose")
    assert "dt_saber" not in ident.signals
    assert "12_back" not in ident.signals
