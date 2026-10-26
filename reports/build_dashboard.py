#!/usr/bin/env python3
# GemHunter — builder UNIQUE du dashboard. Source: scan.tsv + cotes_sold.json + favoris.json
# Produit dashboard_artifact.html (== scan_global.html). Lancé par la tache planifiee.
import json,os,datetime,re
HERE=os.path.dirname(os.path.abspath(__file__))
def L(n): return os.path.join(HERE,n)
MED=json.load(open(L('cotes_sold.json')))['MED']
try:
    ITEM=json.load(open(L('cotes_item.json')))
except Exception:
    ITEM={}
FAV=json.load(open(L('favoris.json')))
ULAB=['Kenner SW','MOTU','GI Joe','Non-sport','Transformers','Pokémon','Comics','Jeu vidéo','Magic','Lego']
TYPL=['Gradé','CIB','Sous blister','Autre']
NOTE=['Vintage Kenner','MOTU vintage MOC','GI Joe vintage','Non-sport scellé 80s','Transformers G1','Pokémon gradé','Comic clé / gradé','Jeu rétro CIB','MTG scellé','Lego scellé']
MODERN=['fan art','vip','polybag','add on','accessoires','foundations','eldraine','tarkir','karlov','aether','modern masters','dragonstorm','wii sports','far cry','fifa']
PILL={'Enchère':'background:#e7e0fb;color:#5b3fb0','Bon plan':'background:#d6f5e0;color:#0f6e36','À surveiller':'background:#fef3cd;color:#7a5b00','Surcoté':'background:#ffe0cc;color:#8a4b10','Au marché':'background:#fef3cd;color:#7a5b00','Garder':'background:#fef3cd;color:#7a5b00','Loisir':'background:#eceff1;color:#546e7a','Virer':'background:#fcdada;color:#a32020'}
def visL(ty): return {0:'Gradé (d’après titre)',1:'CIB (d’après titre)',2:'Blister/MOC (d’après titre)',3:'À vérifier'}[ty]
def itm(i): return 'https://www.ebay.fr/itm/%s'%i
def scan_rows():
    rows=[]
    DROP_MODERN=['2019','2020','2021','2022','2023','2024','2025','we hate','hate the 90','chrome 20','blaster','reboot','flashback','funko','retro collection','vintage collection','collection vintage','origins','masterverse','classics','reissue','réédition']
    for ln in open(L('scan.tsv'),encoding='utf-8'):
        ln=ln.rstrip('\n')
        if not ln: continue
        p=ln.split('§')
        if len(p)<5: continue
        ui=int(p[0]);ty=int(p[1]);title=p[2].strip();prix=int(p[3]);iid=p[4].strip()
        lt0=title.lower()
        if ui<5 and any(x in lt0 for x in DROP_MODERN): continue
        if ty in (1,3): continue  # REGLE: neuf sous blister (MOC/scelle) ou grade UNIQUEMENT - pas de loose ni CIB nu
        cote=ITEM.get(iid) or MED[ui];cout=prix+12;amax=round(cote*0.85-12);marge=cote-cout
        lt=title.lower();flag=any(m in lt for m in MODERN) or (ui in (7,8,9) and prix<25)
        if flag:v='À surveiller';note='Moderne scellé — flip à confirmer'
        else:
            if marge>=cote*0.15:v='Bon plan'
            elif marge>=-cote*0.06:v='À surveiller'
            else:v='Surcoté'
            note=NOTE[ui]
        rows.append(dict(sup='T' if ui<5 else 'G',ui=ui,ty=ty,title=title,prix=prix,id=iid,cote=cote,cout=cout,amax=amax,marge=marge,v=v,note=note))
    seen=set();rows=[r for r in rows if not(r['id'] in seen or seen.add(r['id']))]
    return rows
def tr(r):
    _url=r.get('url') or itm(r['id']); _lab=ULAB[r['ui']]+((' · '+r['src']) if r.get('src') else '')
    if r.get('marge') is None:
        return ('<tr><td class=u>%s</td><td><a href="%s" target=_blank>%s</a></td><td>%s</td><td class=num>enchère</td><td class=num>—</td><td class=num>%d€</td><td class=num>%d€</td><td class=num>—</td><td><span class=pill style="%s">%s</span></td><td class=vis>%s</td><td class=note>%s</td></tr>')%(_lab,_url,r['title'],TYPL[r['ty']],r['cote'],r['amax'],PILL[r['v']],r['v'],visL(r['ty']),r['note'])
    mc='#0f6e36' if r['marge']>=0 else '#a32020';ms=('+%d'%r['marge']) if r['marge']>=0 else ('%d'%r['marge'])
    return ('<tr><td class=u>%s</td><td><a href="%s" target=_blank>%s</a></td><td>%s</td>'
    '<td class=num>%d€</td><td class=num>%d€</td><td class=num>%d€</td><td class=num>%d€</td>'
    '<td class="num" style="color:%s">%s€</td><td><span class=pill style="%s">%s</span></td>'
    '<td class=vis>%s</td><td class=note>%s</td></tr>')%(_lab,_url,r['title'],TYPL[r['ty']],r['prix'],r['cout'],r['cote'],r['amax'],mc,ms,PILL[r['v']],r['v'],visL(r['ty']),r['note'])
def favrow(f):
    favurl=f[9] if len(f)>9 else ''
    u,ty,t,iid,prix,cote,vis,note,v=f[:9]
    cout=prix+12 if prix else 0;amax=round(cote*0.85-12) if cote else 0
    marge=(cote-cout) if (prix and cote) else None
    prixd=(str(prix)+'€') if prix else '—';coutd=(str(cout)+'€') if prix else '—'
    coted=('~'+str(cote)+'€') if cote else '—';amaxd=(str(amax)+'€') if cote else '—'
    if marge is None:marged='—';mc='#555'
    else:mc='#0f6e36' if marge>=0 else '#a32020';marged=('+' if marge>=0 else '')+str(marge)+'€'
    return ('<tr><td class=u>%s</td><td><a href="%s" target=_blank>%s</a></td><td>%s</td>'
    '<td class=num>%s</td><td class=num>%s</td><td class=num>%s</td><td class=num>%s</td>'
    '<td class="num" style="color:%s">%s</td><td><span class=pill style="%s">%s</span></td>'
    '<td class=vis>%s</td><td class=note>%s</td></tr>')%(u,(favurl or itm(iid)),t,ty,prixd,coutd,coted,amaxd,mc,marged,PILL[v],v,vis,note)

def multi_rows():
    import json,os
    try: M=json.load(open(L('multi_src.json')))
    except Exception: return []
    SRC={'L':('LBC','https://www.leboncoin.fr'),'C':('CATA','https://www.catawiki.com/fr')}
    rs=[]
    SEAL=('scell','sealed','moc','misb','neuf','blister','mosc','unpunched','scelle','card')
    GRAD=('graded','grade','cgc','psa','bgs','cbcs','afa','ukg','wata','vga','ngc','pcgs')
    for s,u,prix,path,title in M:
        _tl=title.lower()
        if not (any(k in _tl for k in SEAL) or any(k in _tl for k in GRAD)): continue  # REGLE sealed/grade only
        lab,base=SRC.get(s,('?',''))
        url=path if path.startswith('http') else base+path
        cote=MED[u]; amax=round(cote*0.85-6)
        if s=='C' and (not prix or prix<=1):
            rs.append(dict(sup='T' if u<5 else 'G',ui=u,ty=3,title=title,url=url,cote=cote,cout=0,amax=amax,marge=None,prix=-1,v='Enchère',note=lab+' · enchère',src=lab)); continue
        cout=prix+6; marge=cote-cout
        if marge>=cote*0.15: v='Bon plan'
        elif marge>=-cote*0.06: v='À surveiller'
        else: v='Surcoté'
        rs.append(dict(sup='T' if u<5 else 'G',ui=u,ty=3,title=title,url=url,cote=cote,cout=cout,amax=amax,marge=marge,prix=prix,v=v,note=lab,src=lab))
    return rs

RANK={'Bon plan':0,'À surveiller':1,'Enchère':2,'Surcoté':3}
rows=scan_rows()
MR=multi_rows()
rows=rows+MR
T=[r for r in rows if r['sup']=='T'];T.sort(key=lambda r:(RANK[r['v']],-(r['marge'] if r['marge'] is not None else -999)))
G=[r for r in rows if r['sup']=='G'];G.sort(key=lambda r:(RANK[r['v']],-(r['marge'] if r['marge'] is not None else -999)))
now=datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
HEAD='<!DOCTYPE html><html lang=fr><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>GemHunter</title><style>\n:root{color-scheme:light}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#1a1a1a;padding:16px}\nh1{font-size:20px;margin:0 0 2px}h2{font-size:16px;margin:22px 0 6px;border-left:3px solid #1f6feb;padding-left:8px}.sub{color:#666;font-size:12px;margin-bottom:8px}\ntable{width:100%;border-collapse:collapse;font-size:12.5px;margin-bottom:6px}th,td{padding:6px 8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}th{color:#666;font-size:10px;text-transform:uppercase}\n.num{text-align:right;white-space:nowrap}.u{color:#1f6feb;font-size:11px;white-space:nowrap}a{color:#1f6feb;text-decoration:none}\n.pill{padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;white-space:nowrap}.note{color:#777;font-size:11px;max-width:200px}.vis{font-size:11px;color:#137a3a;max-width:155px}\n#q{width:60%;padding:7px 10px;font-size:13px;border:1px solid #ccc;border-radius:6px}#qb{padding:7px 12px;font-size:13px;border:0;background:#1f6feb;color:#fff;border-radius:6px;cursor:pointer}\n</style></head><body><h1>🪙 GemHunter — Dashboard</h1>\n<div class=sub>MAJ '+now+' · 3 tableaux · cote = ventes eBay conclues (LH_Sold) · frais inclus · plafond 300€ · NEUF SOUS BLISTER ou GRADE only · 100% read-only</div>\n<div style="margin:8px 0"><input id=q placeholder="Filtrer le dashboard (ex: vador, cgc, snes, moc)..."><button id=qb onclick="filt()">Filtrer</button></div>'
TH='<table><thead><tr><th>Univers</th><th>Objet (lien)</th><th>Type</th><th class=num>Prix</th><th class=num>Coût</th><th class=num>Cote</th><th class=num>Achat max</th><th class=num>Marge</th><th>Verdict</th><th>👁 Vision</th><th>Note</th></tr></thead><tbody>'
SCRIPT='<script>function filt(){var v=document.getElementById("q").value.toLowerCase();document.querySelectorAll("tbody tr").forEach(function(r){r.style.display=r.innerText.toLowerCase().indexOf(v)>=0?"":"none";});}</script>'
html=(HEAD
+'<h2>① Trouvailles thématiques (%d)</h2>'%len(T)+'<div class=sub>Tes univers vintage ≤300€ · cote = médiane ventes eBay conclues par catégorie.</div>'+TH+''.join(tr(r) for r in T)+'</tbody></table>'
+'<h2>② Chasse GEEK large — flip (%d)</h2>'%len(G)+'<div class=sub>Pokémon gradé · comics CGC · jeux CIB · MTG · Lego ≤300€ · cote = ventes eBay conclues.</div>'+TH+''.join(tr(r) for r in G)+'</tbody></table>'
+'<h2>③ Tes favoris (live) — cotés aux ventes eBay réelles (%d eBay)</h2>'%len(FAV)+'<div class=sub>Favoris eBay relus en live. Leboncoin (~6 collec.) & Catawiki (16 objets) : prix à confirmer en ouvrant l\'annonce.</div>'+TH+''.join(favrow(f) for f in FAV)+'</tbody></table>'
+SCRIPT+'</body></html>')
open(L('dashboard_artifact.html'),'w',encoding='utf-8').write(html)
open(L('scan_global.html'),'w',encoding='utf-8').write(html)
print('OK build: Trouvailles=%d Geek=%d Favoris=%d -> dashboard_artifact.html + scan_global.html (identiques)'%(len(T),len(G),len(FAV)))
