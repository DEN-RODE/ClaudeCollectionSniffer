"""Test connexion + recherche eBay Browse. Lancer : python test_ebay.py"""
import os, sys, requests
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
from connectors.ebay import EbayConnector, EBAY_BROWSE_URL, MARKETPLACE

cid = os.environ.get("EBAY_CLIENT_ID", ""); cs = os.environ.get("EBAY_CLIENT_SECRET", "")
print("Clés :", "ID ✅" if cid else "ID ❌", "|", "SECRET ✅" if cs else "SECRET ❌")
eb = EbayConnector(cid, cs)
try:
    tok = eb._get_token(); print("OAuth eBay : OK ✅")
except Exception as e:
    print("OAuth ÉCHEC ❌ ->", repr(e)[:300]); sys.exit(1)

def raw(q, mkt):
    r = requests.get(EBAY_BROWSE_URL,
        headers={"Authorization": f"Bearer {tok}", "X-EBAY-C-MARKETPLACE-ID": mkt},
        params={"q": q, "limit": 5}, timeout=30)
    j = r.json()
    return j.get("total"), (j.get("itemSummaries") or []), j.get("warnings")

print(f"\nMarketplace par défaut du connecteur : {MARKETPLACE}")
for mkt in ["EBAY_FR", "EBAY_US"]:
    print(f"\n=== {mkt} ===")
    for q in ["star wars kenner", "pokemon charizard psa", "masters of the universe moc"]:
        try:
            total, items, warn = raw(q, mkt)
            print(f"  '{q}' -> total={total} | reçus={len(items)}")
            for it in items[:2]:
                p = it.get("price", {})
                print(f"      {p.get('value','?')} {p.get('currency','')} | {it.get('title','')[:55]}")
            if warn: print("      ⚠ warnings:", str(warn)[:200])
        except Exception as e:
            print(f"  '{q}' -> ERREUR {repr(e)[:150]}")
print("\nSi des totaux > 0 apparaissent : l'API est pleinement opérationnelle ✅")
