"""
GemHunter — scanner autonome (mode API eBay).

Usage:
    python run.py scan                 # scanne la watchlist sur eBay FR+US
    python run.py scan --universe comics
    python run.py url "https://www.ebay.fr/itm/123..."   # évalue 1 annonce

Pipeline par cible : search (FR+US) -> filtre qualité (MOC/scellé/gradé) ->
identify_listing -> comp (médiane annonces actives) -> anti-arnaque -> score.
Sortie : reports/scan_live.html + résumé console. 100% read-only.
"""
import argparse, os, statistics, datetime, html
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

from connectors.ebay import EbayConnector
from config.watchlist import targets_for, alert_targets
from tools.identify import identify_listing, passes_quality_filter, triage_traps
from tools.scorer import score_listing, _real_cost, assess_listing_risk
from tools.vision import analyze_listing_images, merge_into_identity

# Client Claude (vision) si clé présente — remplit la colonne Vision automatiquement
_VISION = None
if os.environ.get("ANTHROPIC_API_KEY"):
    try:
        import anthropic; _VISION = anthropic.Anthropic()
    except Exception as e:
        print("[vision] client KO:", repr(e)[:120])

def _vision_note(listing, ident):
    if not _VISION:
        return "📷 vision off (ajoute ANTHROPIC_API_KEY)"
    urls = [u for u in (listing.image_urls or []) if u][:4]
    if not urls:
        return "📷 pas d'image"
    try:
        v = analyze_listing_images(urls, listing.title, _VISION)
        merge_into_identity(ident, v)
        form = v.get("form","?"); cond = v.get("condition_notes","") or ""
        traps = v.get("traps") or []
        tag = {"moc":"✅ MOC","sealed":"✅ scellé","graded_slab":"✅ slab gradé","loose":"⚠️ loose"}.get(form,"")
        if traps: tag = "🚫 "+",".join(traps)
        cb = v.get("cardback"); var = v.get("variant")
        extra = " ".join(x for x in [cb, var, cond] if x)
        return f"{tag} {extra}".strip()[:90] or "vu"
    except Exception as e:
        return f"📷 vision KO ({repr(e)[:40]})" 

MAX_BUDGET = float(os.environ.get('GEMHUNTER_MAX_BUDGET', '300'))  # n'analyse pas au-dessus
EU = {"FR","DE","ES","IT","BE","NL","LU","PT","IE","AT","FI","GR","PL","CZ","SK","SI","HU","RO","BG","HR","DK","SE","EE","LV","LT","MT","CY"}

def connectors():
    cid = os.environ.get("EBAY_CLIENT_ID",""); cs = os.environ.get("EBAY_CLIENT_SECRET","")
    mkts = os.environ.get("EBAY_MARKETPLACES", "EBAY_FR,EBAY_US").split(",")
    conns = [EbayConnector(cid, cs, marketplace=m.strip()) for m in mkts if m.strip()]
    # Leboncoin + Catawiki via Apify (si token configuré)
    if os.environ.get("APIFY_TOKEN"):
        try:
            from connectors.scraped_sources import LeboncoinConnector, CatawikiConnector
            if os.environ.get("APIFY_LEBONCOIN_ACTOR"): conns.append(LeboncoinConnector())
            if os.environ.get("APIFY_CATAWIKI_ACTOR"): conns.append(CatawikiConnector())
        except Exception as e:
            print("[apify] init KO:", repr(e)[:120])
    return conns

def country_of(listing):
    c = (listing.raw or {}).get("itemLocation",{}).get("country") or (listing.raw or {}).get("country","")
    return "EU" if (c or "").upper() in EU else ((c or "").upper() or "EU")

def search_all(conns, query, max_results=50):
    seen, out = set(), []
    for c in conns:
        try:
            for l in c.search(query, max_results=max_results):
                if l.listing_id in seen: continue
                seen.add(l.listing_id); out.append(l)
        except Exception as e:
            print(f"[scan] {c.marketplace} '{query[:30]}' KO: {repr(e)[:120]}")
    return out

def comp_median(listings):
    p = [l.price_eur for l in listings if l.price_eur and l.price_eur > 1]
    return round(statistics.median(p),2) if p else None

def evaluate(listing, comp, target=None):
    ident = identify_listing(listing.title, (listing.raw or {}).get("description",""))
    verdict, reason = triage_traps(ident)
    risk = assess_listing_risk(title=listing.title, condition=listing.condition or "",
                               price_eur=listing.price_eur, cote_eur=comp,
                               seller_pct=listing.seller_rating)
    gem = score_listing(listing.price_eur, listing.source, ident, comp,
                        trend_direction="insufficient_data", seller_country=country_of(listing))
    vnote = _vision_note(listing, ident)
    return ident, verdict, reason, risk, gem, vnote

def scan(universe=None, max_results=50):
    conns = connectors()
    if not conns: print("Pas de clés eBay."); return [], []
    rows, alerts = [], []
    # 1) Alertes prix
    for at in alert_targets():
        ls = search_all(conns, at["query"], max_results)
        comp = comp_median(ls)
        for l in ls:
            ok,_ = passes_quality_filter(l.title, l.condition or "")
            if not ok: continue
            ident, verdict, reason, risk, gem, vnote = evaluate(l, at.get("ref_eur") or comp, at)
            if verdict=="reject" or risk["risk_score"]>=70: continue
            floor = at.get("min_price_eur", 0)
            if l.price_eur and floor <= l.price_eur <= at["max_price_eur"] and not any(a in l.title.lower() for a in at.get("avoid",[])):
                alerts.append((at["name"], l, gem))
    # 2) Scan watchlist (dédup globale + rejet pièges/arnaques)
    seen = set(); rejected = 0
    for t in targets_for(universe):
        ls = search_all(conns, t["query"], max_results)
        comp = comp_median(ls) or t.get("ref_eur")
        for l in ls:
            if l.listing_id in seen: continue
            seen.add(l.listing_id)
            if l.price_eur and l.price_eur > MAX_BUDGET: continue
            ok, why_q = passes_quality_filter(l.title, l.condition or "")
            if not ok: continue
            ident, verdict, reason, risk, gem, vnote = evaluate(l, comp, t)
            if verdict == "reject" or risk["risk_score"] >= 70:
                rejected += 1; continue   # piège (repro/facsimile) ou arnaque écartés
            rows.append(dict(univ=t["universe"], title=l.title, price=l.price_eur, url=l.url,
                             source=l.source, comp=comp, score=gem.score, verdict=gem.verdict,
                             maxbid=gem.max_bid_eur, traps=ident.traps,
                             risk=risk["risk_score"], reason=reason, vision=vnote, why=" / ".join(gem.reasons[:2])))
    rows.sort(key=lambda r:(-(r['score'] or 0)))
    print(f"[scan] {len(rows)} retenus, {rejected} écartés (pièges/arnaques)")
    return rows, alerts

def render(rows, alerts):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    def esc(x): return html.escape(str(x))
    def color(r): return "#aff5c4" if r['score']>=75 else "#ffe08a" if r['score']>=55 else "#9aa4af"
    arows = "".join(
        f"<tr><td>{esc(r['univ'])}</td><td><a href='{esc(r['url'])}' target=_blank>{esc(r['title'][:70])}</a></td>"
        f"<td style='text-align:right'>{r['price']:.0f}€</td><td style='text-align:right'>{(r['comp'] or 0):.0f}€</td>"
        f"<td style='text-align:right'>{(r['maxbid'] or 0):.0f}€</td>"
        f"<td style='text-align:right;color:{color(r)}'>{r['score']}</td><td>{esc(r['verdict'])}</td>"
        f"<td>{'🚫 '+str(r['risk']) if r['risk']>=40 else ''} {esc(r['why'])}</td></tr>"
        for r in rows)
    al = "".join(f"<li>🔔 <b>{esc(n)}</b> — {esc(l.title[:60])} à <b>{l.price_eur:.0f}€</b> "
                 f"(score {g.score}) <a href='{esc(l.url)}' target=_blank>voir</a></li>" for n,l,g in alerts) or "<li>Aucune alerte déclenchée.</li>"
    out = f"""<!DOCTYPE html><html lang=fr><head><meta charset=utf-8><title>GemHunter scan live</title>
<style>body{{font-family:sans-serif;background:#0e1116;color:#e6edf3;padding:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:6px;border-bottom:1px solid #222;text-align:left}}
a{{color:#58a6ff}}h1{{font-size:20px}}.al{{background:#161b22;border:1px solid #333;padding:10px;border-radius:8px}}</style></head><body>
<h1>🪙 GemHunter — Scan LIVE eBay</h1><p>{now} · {len(rows)} objets (MOC/scellé/gradé) · comps = médiane annonces actives</p>
<div class=al><b>🔔 Alertes</b><ul>{al}</ul></div>
<table><thead><tr><th>Univers</th><th>Objet</th><th>Prix</th><th>Comp</th><th>Achat max</th><th>Score</th><th>Verdict</th><th>👁 Vision</th><th>Note</th></tr></thead>
<tbody>{arows}</tbody></table></body></html>"""
    os.makedirs("reports", exist_ok=True)
    open("reports/scan_live.html","w",encoding="utf-8").write(out)
    return "reports/scan_live.html"



import json as _json
SEEN_PATH = "reports/seen_ids.json"
def _load_seen():
    try: return set(_json.load(open(SEEN_PATH)))
    except Exception: return set()
def _save_seen(seen):
    os.makedirs("reports", exist_ok=True); _json.dump(sorted(seen), open(SEEN_PATH,"w"))

def hunt(max_results=50):
    """Chasse GLOBALE 'vintage geek' (hors thématique perso) : tout ce qui est
    neuf/scellé/MOC/gradé et flippable. INCRÉMENTAL : ignore les ids déjà vus."""
    from config.watchlist import geek_queries
    conns = connectors()
    if not conns: print("Pas de clés eBay."); return []
    seen = _load_seen(); rows = []; nouveaux = 0
    for q in geek_queries():
        ls = search_all(conns, q, max_results)
        comp = comp_median(ls)
        for l in ls:
            if l.listing_id in seen: continue          # déjà analysé -> on saute
            if l.price_eur and l.price_eur > MAX_BUDGET: continue
            ok, _ = passes_quality_filter(l.title, l.condition or "")
            if not ok: continue                         # seulement neuf/scellé/MOC/gradé
            ident, verdict, reason, risk, gem, vnote = evaluate(l, comp, None)
            seen.add(l.listing_id); nouveaux += 1
            if verdict == "reject" or risk["risk_score"] >= 70: continue
            # flip = sous la cote (marge positive sur ventes actives)
            cr = _real_cost(l.price_eur, l.source, country_of(l))
            flip = comp and cr < comp * 0.85
            rows.append(dict(query=q, title=l.title, price=l.price_eur, url=l.url,
                             source=l.source, comp=comp, score=gem.score, verdict=gem.verdict,
                             maxbid=gem.max_bid_eur, flip=bool(flip), vision=vnote,
                             why=" / ".join(gem.reasons[:2])))
    _save_seen(seen)
    rows.sort(key=lambda r:(-(1 if r["flip"] else 0), -(r["score"] or 0)))
    print(f"[hunt] {len(rows)} candidats retenus, {nouveaux} nouveaux analysés (incrémental). Total connus: {len(seen)}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    ps = sub.add_parser("scan"); ps.add_argument("--universe", default=None); ps.add_argument("--max", type=int, default=50)
    pu = sub.add_parser("url"); pu.add_argument("url")
    a = ap.parse_args(argv)
    if a.mode=="scan":
        rows, alerts = scan(a.universe, a.max)
        path = render(rows, alerts)
        print(f"\n{len(rows)} objets retenus, {len(alerts)} alerte(s). Rapport : {path}")
        for r in rows[:10]:
            print(f"  {r['score']:>3} {r['verdict']:<12} {r['price']:>6.0f}€ (comp {r['comp'] or '?'}) | {r['title'][:55]}")
    elif a.mode=="hunt":
        rows=hunt(a.max)
        for r in rows[:15]:
            tag="FLIP" if r["flip"] else "    "
            print(f"  {tag} {r['score']:>3} {r['price']:>6.0f}€ (comp {r['comp'] or '?'}) | {r['title'][:50]}")
    elif a.mode=="url":
        c = connectors()[0]; l = c.get_item_by_url(a.url)
        comp = comp_median(search_all(connectors(), l.title, 30))
        ident, verdict, reason, risk, gem, vnote = evaluate(l, comp)
        print(f"{l.title}\n prix {l.price_eur}€ | comp {comp} | score {gem.score} {gem.verdict} | risk {risk['risk_score']}")
        print(" mise max:", gem.max_bid_eur, "| raisons:", gem.reasons, "| pièges:", ident.traps)
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
