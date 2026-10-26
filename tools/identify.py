"""
Outil d'identification. Combine :
1. un parsing par règles (rapide, gratuit) sur le titre/description,
2. un fallback LLM optionnel pour les cas ambigus (via l'API Claude).

C'est ce qui distingue une Vader à 25€ d'une à 130 000€ :
les détails "12-back + DT saber" qu'une recherche mot-clé rate.
"""
import re
from dataclasses import dataclass, field
from config.themes import (
    MAJOR_GRADERS, MINOR_GRADERS, KENNER_VALUE_SIGNALS, KENNER_TRAPS,
    GENERIC_TRAPS, COMIC_TRAPS,
)


@dataclass
class Identity:
    grader: str | None = None
    grade: float | None = None
    grader_is_major: bool = True
    is_graded: bool = False
    signals: list[str] = field(default_factory=list)   # ex: ["dt_saber","12_back"]
    traps: list[str] = field(default_factory=list)      # ex: ["réédition"]
    notes: str = ""


GRADE_RE = re.compile(
    r"\b(CGC|PSA|BGS|CBCS|AFA|UKG|WCG|GCG|GCC)\s*([0-9]{1,2}(?:\.[05])?)\b",
    re.IGNORECASE,
)


def identify(title: str, description: str = "") -> Identity:
    text = f"{title} {description}".lower()
    ident = Identity()

    # --- Grader + note ---
    m = GRADE_RE.search(f"{title} {description}")
    if m:
        ident.is_graded = True
        ident.grader = m.group(1).upper()
        try:
            ident.grade = float(m.group(2))
        except ValueError:
            pass
        ident.grader_is_major = ident.grader in MAJOR_GRADERS
        if ident.grader in MINOR_GRADERS:
            ident.notes += f"⚠️ grader mineur ({ident.grader}) = décote. "

    # --- Signaux de valeur Kenner ---
    for signal, keywords in KENNER_VALUE_SIGNALS.items():
        if any(kw in text for kw in keywords):
            ident.signals.append(signal)
    if "dt_saber" in ident.signals:
        ident.notes += "🚨 DT saber détecté = pièce potentiellement rarissime. "

    # --- Pièges (rééditions modernes) ---
    for trap in KENNER_TRAPS + GENERIC_TRAPS + COMIC_TRAPS:
        if trap in text and trap not in ident.traps:
            ident.traps.append(trap)
    if ident.traps:
        ident.notes += f"⚠️ piège possible (repro/moderne) : {', '.join(ident.traps)}. "

    return ident


# Fallback LLM pour cas ambigus (optionnel, appelé seulement si règles incertaines).
def identify_with_llm(title: str, description: str, anthropic_client) -> dict:
    """
    À brancher en phase 1.5 : on n'appelle le LLM que sur les annonces
    où le parsing par règles est ambigu (économie de tokens, cf. LiteLLM/LLMLingua).
    Retourne un dict structuré {grader, grade, signals, traps, confidence}.
    """
    prompt = (
        "Tu es expert en collectibles vintage. Analyse cette annonce et renvoie "
        "UNIQUEMENT du JSON : {grader, grade, is_moc, back_type, saber_type, "
        "traps:[], confidence:0-1}.\n\n"
        f"Titre: {title}\nDescription: {description}"
    )
    # resp = anthropic_client.messages.create(model="claude-...", ...)
    # return json.loads(resp...)
    raise NotImplementedError("Fallback LLM = phase 1.5")


def identify_listing(title: str, description: str = "", specs: dict | None = None) -> Identity:
    """
    Identification COMPLÈTE d'une annonce : titre + description + CARACTÉRISTIQUES (specs).
    Les pièges 'reprint/whitman/diamond/treasury' sont souvent dans les specs eBay
    (Variant Type, Features, Original/Reprint), PAS dans le titre. On concatène tout
    avant le parsing pour ne pas les rater.
    """
    spec_text = ""
    if specs:
        # ex: {"Variant Type":"Whitman Variant","Features":"Reprint","Original/Reprint":"Reprint"}
        spec_text = " ".join(f"{k} {v}" for k, v in specs.items())
    full_desc = f"{description} {spec_text}".strip()
    ident = identify(title, full_desc)
    # signal explicite si les specs marquent une réédition
    if specs:
        joined = " ".join(str(v).lower() for v in specs.values())
        if "reprint" in joined or "whitman" in joined or "facsimile" in joined:
            if "reprint" not in ident.traps:
                ident.traps.append("reprint")
            ident.notes += " [SPECS] réédition/variante détectée dans les caractéristiques. "
    return ident


# --- Pièges DURS (preuve explicite) vs DOUX (champ vendeur souvent faux) ---
HARD_TRAPS = {"facsimile", "facsimile edition", "facsimilé", "whitman", "diamond 35",
              "diamond variant", "treasury", "treasury edition", "marvel special edition",
              "mystery", "mystery box", "mystery repack", "repack", "grade'n",
              "collection rétro", "les temps sombres", "vintage collection", "action masters"}
SOFT_TRAPS = {"reprint", "1rep", "newsstand reprint", "reissue", "réédition", "multi-pack edition"}


def triage_traps(ident: Identity, vision_is_original: bool | None = None) -> tuple[str, str]:
    """
    Décide quoi faire des pièges détectés, avec PRIORITÉ À L'IMAGE.
      - vision_is_original=True  -> on efface les pièges 'doux' (le champ 'reprint' était faux) -> 'ok'
      - vision_is_original=False -> contrefaçon/réédition confirmée -> 'reject'
      - piège DUR présent         -> 'reject'
      - seulement piège DOUX      -> 'verify' (à confirmer en photo, NE PAS rejeter sec)
    """
    traps = set(t.lower() for t in ident.traps)
    hard = traps & HARD_TRAPS
    soft = traps & SOFT_TRAPS
    if vision_is_original is True and not hard:
        # l'image prime : on retire les pièges doux
        ident.traps = [t for t in ident.traps if t.lower() not in SOFT_TRAPS]
        ident.notes += " [VISION>TEXTE] original confirmé en photo, label 'reprint' ignoré. "
        return ("ok", "Original confirmé visuellement (label texte erroné)")
    if vision_is_original is False:
        return ("reject", "Réédition/contrefaçon confirmée en photo")
    if hard:
        return ("reject", "Piège explicite : " + ", ".join(sorted(hard)))
    if soft:
        return ("verify", "Champ 'reprint' à confirmer en photo (pavé prix/UPC : code-barres=original, diamant=réimpression)")
    return ("ok", "")


import re as _reqf
_MAJOR_GRADERS_RE = _reqf.compile(r"\b(CGC|PSA|BGS|CBCS|AFA|UKG|NGC|PCGS|SGC)\s*\d", _reqf.I)
_MINOR_GRADERS_RE = _reqf.compile(r"\b(WCG|GCG|GCC|MADNESS)\b", _reqf.I)
_SEALED_RE = _reqf.compile(r"\b(moc|mosc|misb|mib|nib|sealed|scell[ée]+|scellee|unpunch\w*|blister|carded|cello|factory sealed|neuf sous blister|sous blister|mint on card|sous carte|jamais ouvert)\b", _reqf.I)
_LOOSE_RE = _reqf.compile(r"\bloose\b|en vrac|d[ée]tach[ée]|incomplet|sans blister|sans carte|out of package|oop\b", _reqf.I)


def passes_quality_filter(title: str, condition: str = "") -> tuple[bool, str]:
    """
    Filtre QUALITÉ : ne garder QUE les objets MINT sous blister/scellé/MOC
    OU gradés par un grader MAJEUR. Écarte loose / occasion / brut non gradé.
    Retourne (garde?, raison).
    """
    t = f"{title} {condition}".strip()
    graded_major = bool(_MAJOR_GRADERS_RE.search(t))
    minor = bool(_MINOR_GRADERS_RE.search(t))
    sealed = bool(_SEALED_RE.search(t))
    loose = bool(_LOOSE_RE.search(t))
    if graded_major and not minor:
        return True, "gradé (grader majeur)"
    if minor:
        return False, "grader mineur (décote) — écarté"
    if sealed and not loose:
        return True, "sous blister / scellé (MOC)"
    return False, "ni gradé majeur ni sous blister → écarté"
