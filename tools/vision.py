"""
Analyse d'IMAGES d'annonce (règle 7 du CLAUDE.md : l'identification a besoin de
la vision recto/verso). Un titre eBay ne dit pas si c'est MOC, ni la variante.

`analyze_listing_images()` envoie les photos (recto + verso de préférence) à
Claude (vision) et renvoie un dict structuré : MOC/loose/scellé, cardback,
variante, défauts du blister, pièges (repro/facsimilé), confiance.

Le résultat est ensuite fusionné dans l'Identity (merge_into_identity) pour que
le GemScorer en tienne compte. Économie : on n'appelle la vision QUE sur les
candidats sérieux (présélection par règles + prix), pas sur toute la liste.
"""
import json
from tools.identify import Identity

VISION_PROMPT = """Tu es expert en collectibles vintage (Star Wars Kenner, comics
Marvel/SW, Pokémon, non-sport 80-90s). Analyse ces photos d'une annonce dont le
titre est : "{title}".

Réponds UNIQUEMENT en JSON strict avec ces champs :
{{
 "form": "moc" | "loose" | "sealed" | "graded_slab" | "unknown",
 "carded": true/false,           // sous blister/carte
 "cardback": "12-back"|"21-back"|"65-back"|"77-back"|"trilogo"|"potf-92"|null,
 "variant": "...",               // ex: "DT saber", "Tri-logo Palitoy", "facsimile"
 "unpunched": true/false/null,   // carte non-perforée (MOC)
 "condition_notes": "...",       // bulle écrasée, jaunissement, plis, etc.
 "grader": null | "CGC"|"PSA"|"BGS"|...,
 "grade": null | number,
 "traps": [],                    // ex: ["reproduction","facsimile","reissue"]
 "confidence": 0.0-1.0
}}
Base-toi sur ce que tu VOIS (blister, dos de carte, étiquettes, logo Kenner/Palitoy,
slab gradé), pas sur des suppositions."""


def analyze_listing_images(image_urls: list[str], title: str, anthropic_client,
                           model: str = "claude-sonnet-4-6", max_images: int = 4) -> dict:
    """Appelle Claude vision sur les images de l'annonce. Retourne un dict structuré."""
    if not image_urls:
        return {"form": "unknown", "confidence": 0.0, "error": "no_images"}
    content = [{"type": "text", "text": VISION_PROMPT.format(title=title)}]
    for url in image_urls[:max_images]:
        if not url:
            continue
        content.append({"type": "image",
                        "source": {"type": "url", "url": url}})
    resp = anthropic_client.messages.create(
        model=model, max_tokens=600,
        messages=[{"role": "user", "content": content}],
    )
    text = resp.content[0].text.strip()
    # tolérer un éventuel bloc ```json
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"form": "unknown", "confidence": 0.0, "raw": text}


def merge_into_identity(ident: Identity, vision: dict) -> Identity:
    """Fusionne le verdict visuel dans l'Identity (prioritaire sur le parsing texte)."""
    form = vision.get("form")
    if vision.get("carded") or form == "moc":
        if "moc" not in ident.signals:
            ident.signals.append("moc")
    if vision.get("unpunched") and "unpunched" not in ident.signals:
        ident.signals.append("unpunched")
    cb = vision.get("cardback")
    if cb == "12-back" and "12_back" not in ident.signals:
        ident.signals.append("12_back")
    if cb == "trilogo":
        ident.signals.append("trilogo")
    var = (vision.get("variant") or "").lower()
    if "dt" in var or "double telescop" in var:
        if "dt_saber" not in ident.signals:
            ident.signals.append("dt_saber")
    if vision.get("grader"):
        ident.is_graded = True
        ident.grader = vision["grader"]
        ident.grade = vision.get("grade")
    for t in vision.get("traps", []):
        if t not in ident.traps:
            ident.traps.append(t)
    if form == "loose":
        ident.notes += " [VISION] loose (pas sous blister). "
    cn = vision.get("condition_notes")
    if cn:
        ident.notes += f" [VISION] {cn}. "
    return ident
