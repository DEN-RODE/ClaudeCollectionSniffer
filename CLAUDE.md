# CLAUDE.md — GemHunter

> Bot multi-agent (CrewAI) de détection de **pépites collectibles** sur eBay /
> Leboncoin / Catawiki. Objectif : trouver, dans les univers que j'aime
> (Star Wars Kenner vintage, Pokémon gradé, comics key issues, non-sport/stickers
> 80-90s), les **pièces de valeur au meilleur prix** — sous-cotées ET dont la
> tendance monte. Le plaisir guide ce qu'on regarde ; 3 filtres décident ce qu'on achète.

Ce fichier est la source de vérité pour toute session Claude Code sur ce repo.
Le lire en entier avant d'écrire ou modifier du code.

---

## 0. Principes directeurs (NE JAMAIS LES PERDRE DE VUE)

> **RÈGLE N°1 — READ-ONLY ABSOLU (non négociable).**
> Le bot NE PASSE JAMAIS D'ORDRE et N'ACHÈTE JAMAIS à la place de l'utilisateur.
> Interdits stricts : placer/relancer une enchère, ajouter au panier, valider un
> achat ou un paiement, contacter un vendeur pour acheter, accepter une
> contre-offre. Le bot DÉTECTE, IDENTIFIE, NOTE et ALERTE — point.
> Toute transaction est 100% manuelle, décidée et exécutée par l'humain.
> Cela vaut pour TOUS les canaux, y compris la navigation pilotée (Claude in
> Chrome) : lecture seule, jamais de clic 'Acheter'/'Enchérir'/'Commander'.
> Aucun connecteur ne doit exposer de méthode d'achat/enchère. Une source = `search()` en lecture seule.


1. **Honnêteté financière.** Ce bot optimise un LOISIR avec option de plus-value,
   PAS un placement. Ne jamais présenter les collectibles comme un investissement
   sûr. Le vrai patrimoine se construit ailleurs (PEA/MSCI World). Le bot fait
   gagner sur le *timing* et le *prix d'achat*, pas sur des rendements garantis.
2. **3 filtres de valeur** appliqués à tout objet avant un "achat" :
   (a) licence/perso à demande DURABLE, (b) rareté réelle + état top
   (MOC unpunched / scellé / haute note), (c) grader MAJEUR si gradé.
   Si un seul manque → plaisir éventuel à petit prix, jamais "pépite".
3. **Graders majeurs uniquement** : CGC, PSA, BGS, CBCS, AFA, UKG, NGC, PCGS.
   Pénaliser fortement WCG / GCG / GCC / graders maison (décote marché réelle).
4. **Coût réel, pas prix affiché.** Toujours raisonner
   `coût = prix + frais plateforme + port + douane` et comparer à la cote de
   VENTES RÉELLES (pas aux prix demandés gonflés). Catawiki = +~9 % acheteur.
5. **Mise max = (cote × marge_sécurité) − frais.** Marge ~0.85 pour acheter au
   juste prix, plus basse si revente visée. Ne jamais surenchérir au-delà.
6. **Pas de mystery box.** Espérance négative par construction. Filtrer/rejeter.
7. **Vérifier la variante.** Une "Dark Vador ROTJ" peut être : Tri-logo Palitoy
   (~150-280€), US standard (~120-150€), ou réédition moderne (~30€). Lisible
   surtout au DOS de la carte → l'identification a besoin de la VISION recto+verso.

---

## 1. Architecture

Pipeline séquentiel CrewAI, piloté par une **watchlist de cibles** (le "quoi chasser"),
avec mémoire de tendance partagée (Chroma).

```
Curator ──(maintient)──> WATCHLIST
                             │
   ┌─────────────────────────┘
   ▼
Scout → Identifier → Market → Trend → GemScorer → Alert
                                  ▲
                            TrendMemory (Chroma)
```

### Les agents
- **Curator** (`agents/curator.py`) : décide QUOI chasser. Découvre les top objets
  de chaque univers (web search + LLM) et recalibre cotes/prix-cibles depuis Chroma.
  C'est l'agent "stratège" — il industrialise le travail de sélection des key issues.
- **Scout** : interroge les sources (eBay phase 1) pour chaque cible/thème.
- **Identifier** (`tools/identify.py`) : grader, note, variante, signaux de valeur
  (DT saber, 12-back, MOC, Tri-logo), pièges (rééditions). Règles + fallback LLM.
- **Market** (`tools/market.py`) : comp de marché (médiane annonces actives en
  gratuit ; GoCollect/PriceCharting plus tard).
- **Trend** (`tools/market.py::TrendMemory`) : dynamique 30/90j calculée sur
  l'historique accumulé dans Chroma (tendance maison gratuite).
- **GemScorer** (`tools/scorer.py`) : score /100 = décote + tendance + qualité,
  frais réels intégrés, mise max calculée.
- **Alert** : notifie seulement score ≥ 75 (Telegram/Discord) avec lien, comp,
  tendance, mise max.

### Connecteurs (interface commune `connectors/base.py`)
- `connectors/ebay.py` — **eBay Browse API** (gratuit, légal). FONDATION phase 1.
- `connectors/scraped_sources.py` — stubs **Leboncoin** & **Catawiki** (phase 2,
  scraping managé). Même interface `SourceConnector.search()` → le reste du bot
  ne change pas quand on les active.

---

## 2. Les STEPS du bot (cycle de run)

Un cycle complet = ces étapes, dans l'ordre :

**STEP 0 — Curation (périodique, pas à chaque run)**
Le Curator rafraîchit la WATCHLIST : pour chaque univers, (re)trouve les pièces
qui valent le coup + met à jour `ref_eur` / `target_buy_eur`. Source : web search
sur price guides publics + recalibrage depuis Chroma. → `config/watchlist.py` enrichi.

**STEP 1 — Scan (Scout)**
Pour chaque cible de la WATCHLIST (et/ou thème de `config/themes.py`), lancer
`connector.search(query)` sur les sources actives. Dédupliquer par `listing_id`.
Respecter rate limits + throttling. Cacher les résultats bruts.

**STEP 2 — Identification (Identifier)**
Pour chaque `Listing` : `identify(title, description)` → `Identity`
(grader, grade, signals, traps). Si parsing ambigu → fallback LLM (vision sur
recto+verso d'images quand dispo). Rejeter d'emblée les `traps` (rééditions).

**STEP 3 — Marché (Market)**
Récupérer la cote de référence : médiane des annonces actives comparables
(gratuit) ou cote watchlist `ref_eur`. Enregistrer le prix observé dans Chroma
(`TrendMemory.record`) → nourrit la tendance.

**STEP 4 — Tendance (Trend)**
`TrendMemory.trend(item_key, days=90)` → direction up/stable/down + %.
Si données insuffisantes : "insufficient_data" (le bot le dit, ne bluffe pas).

**STEP 5 — Scoring (GemScorer)**
`score_listing(price, source, ident, comp, trend, seller_country)` →
`GemScore(score, verdict, max_bid_eur, reasons)`. Frais réels intégrés.
Bonus si l'objet matche un univers de la watchlist ; malus léger si hors-scope
(j'aime les 80-90s mais je n'achète QUE de la valeur dans mes univers).

**STEP 6 — Alerte (Alert)**
Score ≥ 75 → "PÉPITE" → notification immédiate (lien + comp + tendance + mise max).
55-74 → "à surveiller" → digest quotidien. < 55 → ignorer.

**STEP 7 — Boucle & apprentissage**
Logger chaque décision. Quand je valide/rejette une alerte, le feedback ré-pondère
les critères (ML Learning Agent, façon TRUKAIAK) et affine les `target_buy_eur`.

---

## 3. MCP — intégration & serveurs recommandés

CrewAI a une intégration MCP native via `crewai-tools` (`MCPServerAdapter`).
Deux usages :

### 3a. Brancher des MCP comme OUTILS des agents
`MCPServerAdapter` convertit les tools d'un serveur MCP en tools CrewAI 1:1.
Supports : stdio, SSE, Streamable HTTP. **Note** : l'adapter ne récupère que le
premier output texte (`.content[0].text`) — prévoir un handling custom pour les
sorties multi-modales. **Sécurité** : valider les `Origin` sur SSE, binder sur
127.0.0.1 en local, jamais 0.0.0.0 (risque DNS-rebinding).

```python
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
import os

# Exemple stdio (process local)
params = StdioServerParameters(command="npx", args=["-y", "firecrawl-mcp"],
                               env={"FIRECRAWL_API_KEY": os.environ["FIRECRAWL_API_KEY"]})
try:
    adapter = MCPServerAdapter(params)
    tools = adapter.tools                 # -> tools CrewAI
    agent = Agent(role="Scout", tools=tools, ...)
finally:
    adapter.stop()                        # IMPÉRATIF (try/finally)

# Exemple SSE/HTTP (serveur distant)
# params = {"url": "http://127.0.0.1:8000/sse"}
```

### 3b. Serveurs MCP à connecter (je les lâcherai au fur et à mesure)
Priorité pour ce projet :
- **Apify MCP** — LE choix pour scraping structuré multi-sites (30k+ Actors :
  eBay, marketplaces, etc.). Contrôle proxy (résidentiel, pays, sessions) = utile
  pour les cibles anti-bot. Restreindre les Actors autorisés via `--actors` en prod.
  → candidat pour **Leboncoin/Catawiki** (phase 2) + comps eBay.
- **Firecrawl MCP** — URL→Markdown rapide, simple, gère la plupart des anti-bot
  courants. Idéal pour scraper une page produit ad-hoc / price guides publics.
  Tier gratuit ~500 crédits. → candidat **PriceCharting/GoCollect pages, fiches**.
- **Bright Data MCP** — quand Apify/Firecrawl bloquent (Cloudflare entreprise,
  anti-bot lourd). Filet de sécurité pour cibles difficiles.
- (Optionnel) **Filesystem MCP / GitHub MCP** — confort dev, pas cœur métier.

Recommandation : **Firecrawl pour l'ad-hoc/RAG**, **Apify pour l'ingestion
récurrente structurée**. Séparer scheduled (Apify) vs interactif (Firecrawl)
garde les coûts et le contexte sous contrôle.

### 3c. Légal / risque
- eBay API officielle = OK.
- Scraper Leboncoin/Catawiki via MCP = zone grise CGU + risque IP. Décision
  business à assumer. Le MVP tourne SANS. Activer en connaissance de cause.
- Toujours : clés en variables d'env, jamais commit ; rate limits côté provider ;
  validation des URLs (bloquer file://, IP internes) ; logging des appels.

---

## 4. Hooks CrewAI

Utiliser les hooks pour la robustesse et l'apprentissage, pas pour la logique métier :
- **before_kickoff / after_kickoff** : préparer le contexte (charger watchlist,
  ouvrir la connexion Chroma) / persister les résultats + métriques de run.
- **task callbacks** (`callback=` sur Task) : logger chaque sortie d'agent,
  capturer les `GemScore` pour le feedback d'apprentissage.
- **step_callback** (sur Agent/Crew) : tracer les appels d'outils (debug,
  comptage tokens, coût LiteLLM).
- Garder les hooks idempotents et sans effet de bord caché. La logique de
  scoring/décision reste dans `tools/`, pas dans les hooks.

---

## 5. Plugins / stack optimale (ma stack habituelle, à réutiliser)

- **LiteLLM** — routage modèle par coût/complexité. Identifier/Curator = modèle
  capable ; tâches simples = modèle cheap. Brancher comme LLM des agents CrewAI.
- **LLMLingua** — compression de prompt (identification en masse = beaucoup de
  texte d'annonces). Compresser avant l'appel LLM.
- **mem0** — mémoire persistante par agent (préférences d'achat, historique de
  décisions) en complément de Chroma (qui sert la tendance prix).
- **Chroma** — déjà au cœur : `TrendMemory` (historique prix) + cache annonces +
  embeddings pour dédup sémantique des annonces quasi-identiques.
- **LlamaIndex** (optionnel) — si on indexe de gros price guides / catalogues
  pour du RAG (ex. base Kenner complète avec variantes).

---

## 6. Conventions de code

- Python 3.12. Type hints partout. Dataclasses pour les structures
  (`Listing`, `Identity`, `GemScore`).
- Une responsabilité par module. La logique métier vit dans `tools/` (testable
  sans réseau ni LLM). Les agents/`crew.py` orchestrent seulement.
- Le savoir métier (cibles, graders, signaux, pièges) vit dans `config/`
  (`watchlist.py`, `themes.py`) — éditable sans toucher au code.
- Toute nouvelle source = une classe implémentant `SourceConnector`. Ne jamais
  coder en dur une source ailleurs.
- Tests : `tools/scorer.py` et `tools/identify.py` doivent rester testables en
  pur offline (cf. les cas de validation : Vader ROTJ, ToS#65 surcoté,
  DT saber = pépite, repro = piège).
- Secrets en env (`EBAY_CLIENT_ID/SECRET`, `FIRECRAWL_API_KEY`, `APIFY_TOKEN`,
  `ANTHROPIC_API_KEY`). Jamais commit. `.env` dans `.gitignore`.

---

## 7. Roadmap / phases

- **Phase 1 (fait — squelette)** : eBay Browse + identify + market(actif) +
  scorer + watchlist + curator(stub). Tourne offline pour la logique.
- **Phase 1.5 (next)** : brancher (a) LLM Claude via LiteLLM pour
  `identify_with_llm` + `Curator.discover_targets`, (b) Alert Telegram,
  (c) remplir Chroma sur quelques semaines pour activer la tendance.
- **Phase 2** : connecteurs Leboncoin/Catawiki via Apify/Firecrawl MCP
  (décision risque). Comps via ventes complétées (eBay Marketplace Insights si
  accès accordé, sinon scraping price guides).
- **Phase 3** : feedback d'apprentissage (ML Learning Agent) qui ré-pondère le
  scorer et affine les prix-cibles selon mes achats validés/rejetés.

---

## 8. Définition d'une "pépite" (le but du bot)

Une pépite = les 3 axes alignés :
1. **Sous-cotée** : coût réel ≤ ~85 % de la cote de ventes réelles.
2. **Tendance** : stable→haussière (pas en chute).
3. **Qualité** : licence durable + état top + grader majeur + dans mes univers,
   sans piège (repro, grader bidon, mystery box).

Le GemScorer formalise ça en /100. Seul ≥ 75 mérite de me déranger.
Tout le reste est du bruit ou du plaisir à petit prix — à ne pas confondre
avec un actif.

---

## 9. État courant & leçons (mis à jour 2026-06-22)

**Décisions verrouillées (ne pas régresser) :**
- **NEUF SOUS BLISTER (MOC / scellé / MISB) ou GRADÉ (grader majeur) UNIQUEMENT**, pour TOUS les univers (decision user 2026-06-14). On ne surface JAMAIS de loose ni de CIB nu (l'utilisateur en possède deja beaucoup). Enforce dans `build_dashboard.py` : `scan_rows` skip `ty in (1,3)` ; `multi_rows` ne garde que titres sealed/MOC/scellé/neuf/card/gradé. Jeux retro = scellé ou WATA/VGA/CGC, pas CIB.
- **Plafond d'achat = 300 €** par pièce (env `GEMHUNTER_MAX_BUDGET`, défaut 300). Au-delà : on n'analyse pas. Tables Trouvailles + Geek filtrées ≤300 €.
- **JAMAIS de cote « (e) » bidon.** Une cote = **ventes eBay réellement conclues** (recherche `&LH_Sold=1&LH_Complete=1`, médiane). Fallback médiane des annonces ACTIVES uniquement si pas de ventes, et libellé explicitement comme tel. Bannir le suffixe « (e) ».
- **Vision = vraie photo** (screenshot/planche-contact), pas « annoncé ». Si pas vérifié, dire « d'après titre », ne pas prétendre l'avoir vu.
- **Favoris = LIVE, jamais une vieille capture.** Relire à chaque fois : eBay `ebay.fr/mye/myebay/watchlist`, Leboncoin `leboncoin.fr/favorites`, Catawiki `catawiki.com/fr/interests/objects`.

**Dashboard (artefact Cowork `gemhunter-dashboard`, fichier outputs `dashboard_artifact.html`) = 3 tables :**
1. Trouvailles thématiques (univers de l'utilisateur, ≤300 €)
2. Chasse GEEK large — flip (Pokémon gradé, comics CGC, jeux CIB, MTG, Lego…, ≤300 €)
3. Tes favoris (LIVE, cotés aux ventes eBay réelles)
Colonnes : Univers · Objet(lien) · Type · Prix · Coût · Cote · Achat max · Marge · Verdict · Vision · Note. Coût = prix + frais plateforme. Achat max = cote×0.85 − frais.

**Limites de fiabilité du scraping navigateur (CAUSE des données foireuses) :**
- Watchlist eBay **mélange objets suivis + recommandations** → filtrer sur le statut « AFFAIRE SUIVIE ».
- **Prix de liste Leboncoin non fiables** (bug de binding) → lire via `__NEXT_DATA__` ou ouvrir l'annonce ; ne jamais coter un favori LBC sans ouvrir.
- **Catawiki bloque l'extraction** des lots favoris (filtre).
- Sorties JS du navigateur **tronquées ~1 Ko** → transférer par tranches.
- Onglets Chrome se réinitialisent entre les tours → faire extraction+transfert dans le même tour.
- **Vraie réparation = API eBay Browse + Marketplace Insights (sniff + cotes auto) + scraping managé Apify/Firecrawl pour LBC/Catawiki.** Tant que pas branché : données partielles, le dire.

**Cotes ventes eBay réelles relevées (2026-06-05, référence) :** SW#1 1977 CGC méd ~119 € (11→2056 selon note) ; SW#2 ~85 € ; SW#3 toutes notes ~49 € (9.2 = premium) ; Hell Arisen #3 CGC ~73 € ; GI Joe SGT Savage 94 ~17 € ; Vador ROTJ Kenner loose ~42 € ; Hot Wheels Crack-Ups 84 ~19 € ; Batman 89 Kenner ~30 € ; Crados carte seule ~5-15 €.

**Run 2026-06-22 (live Claude in Chrome) :** eBay sniff 10 univers via fetch same-origin -> `scan.tsv` 83 annonces <=300 EUR (MOC/scelle/grade only, ~5-9/univers ; titres nettoyes du bruit a11y 'La page s'ouvre'). Medianes ventes conclues `LH_Sold` rafraichies (cotes_sold.json, n=54..478/cat ; SW/GIJoe/NonSport/TF/Retro via requetes LARGES incl loose -> mediane diluee, le dire) : SW 25 . MOTU 36 . GIJoe 48 . Non-sport 41 . TF 31 . Pokemon 73 . Comics 101 . Retro 37 . MTG 79 . Lego 83. Catawiki rafraichi (24 lots/univers SW+Pokemon+Comics) -> apres filtre sealed/grade + anti-trap (funko/mystery/mandalorian/2025-26) il ne reste que 12 comics CGC, tous enchere (prix=-1). SW Catawiki=Funko/loose, Pokemon Catawiki=mystery box (rejetes). LBC search heavily client-rendered cette session (body ~722 chars, prix non extractibles fiablement) -> 10 lots LBC du run precedent CONSERVES (non re-cotes live, conforme regle 'ne pas inventer prix LBC'). Favoris 77 CONSERVES (re-read live de 77 annonces = prix null sans ouvrir chacune). multi_src.json = 22 lots (10 LBC + 12 Catawiki). Dashboard `Trouvailles 35 . Geek 64 . Favoris 77` -> artefact Cowork gemhunter-dashboard + dashboard_artifact.html + scan_global.html a jour.

**Run 2026-06-16 (auto, navigateur) :** eBay sniff 10 univers -> `scan.tsv` 70 annonces <=300 EUR (MOC/scelle/grade, ~7-9/univers). Medianes ventes conclues `LH_Sold` rafraichies (n=116..246/cat) -> `cotes_sold.json` : SW 49 . MOTU 64 . GIJoe 22 . Non-sport 30 . TF 50 . Pokemon 80 . Comics 91 . Retro 25 . MTG 57 . Lego 75. (vs 14/06 : TF + Lego en hausse ; SW/MOTU/GIJoe/Pokemon/Comics/Retro/MTG en baisse - requetes plus larges, mediane diluee). LBC + Catawiki (~16 objets, prix a confirmer en ouvrant l'annonce, bid live != prix achat) -> `multi_src.json` (22 lots). Favoris (77) CONSERVES (favoris.json du 14/06). Dashboard `Trouvailles 36 . Geek 57 . Favoris 77` -> 2 dashboards a jour (`dashboard_artifact.html` + `scan_global.html`).

**Run 2026-06-14 (2e passe, regle sealed/grade) :** Filtre durci -> scan.tsv = 46 grade + 44 scelle (0 loose/CIB). Retro re-sniffe en gradé WATA/VGA/CGC (9 lots, ex: Spikeout VGA 299, Dark Cloud2 WATA 299, NES Gauntlet CGC 296). multi_src filtre 31->9 (1 SW carde LBC + 8 gradés Catawiki Pokemon/Comics ; loose LBC/Catawiki retires). Favoris 77 inchanges (pas de tag loose fiable -> audit a faire en ouvrant chaque annonce, non invente). Dashboard `Trouvailles 46 . Geek 53 . Favoris 77` -> 2 dashboards a jour.

**Run 2026-06-14 (auto, navigateur) :** eBay sniff 10 univers via fetch same-origin -> 90 annonces <=300 EUR (9/univers, MOC/scelle/grade, reeditions/TVC/mystery exclues, filtre pertinence par univers). Medianes ventes conclues `LH_Sold` rafraichies (n=81..130/cat) -> `cotes_sold.json` : SW 56 . MOTU 79 . GIJoe 50 . Non-sport 29 . TF 40 . Pokemon 99 . Comics 109 . Retro CIB 62 . MTG 83 . Lego 50. (vs 13/06 : SW/MOTU/GIJoe/Comics en hausse ; Non-sport/TF/MTG/Lego en baisse). LBC via `__NEXT_DATA__` (18 lots : SW/MOTU/GIJoe/retro) + Catawiki `/l/` (13 lots SW/Pokemon/Comics, TOUS marques 'enchere' prix=-1 car bid live qui monte != prix achat) -> `multi_src.json` (31 lots). Favoris (77) CONSERVES (favoris.json du 12/06, deja cote/verdicte ; live re-read remonte prix null sans ouvrir chaque annonce). Dashboard `Trouvailles 64 . Geek 57 . Favoris 77` -> 2 dashboards a jour. A noter bons plans : MTG Chevalier Noir Revised PSA 8 59 EUR (cote ~83), Lego Paradisa 6411 scelle 245 EUR, comics CGC keys SW#1/FF#33/FF#46 ~280-296 EUR (cote ~109, surcotes vs mediane large).

**Alertes programmées :**
- `gemhunter-morning-scan` (9h08, quotidien) — sniff des 3 sites + favoris, cotes ventes eBay réelles, et MET À JOUR les **2 dashboards** : artefact Cowork `gemhunter-dashboard` + fichier `scan_global.html`.
- `crados-alerte-quotidienne` (9h04) — scan eBay+LBC des Crados manquants (Gaétan Poulecassé, Mathieu Le Dégueu #21) + nouveautés ; mémoire `reports/crados_seen.json`.
- `gemhunter-md-update` (00h07 et 12h07) — cette tâche de maintenance de CLAUDE.md.

**Profil :** collectionneur-INVESTISSEUR, petit kiffe Vador Kenner. Meilleur sous-jacent invest = comics keys CGC (SW 1977 Marvel) + Kenner vintage MOC/gradé. Crados = loisir, pas invest.
