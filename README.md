# GemHunter — bot multi-agent CrewAI de détection de pépites collectibles

## Objectif
Scanner les marketplaces (eBay phase 1 ; Leboncoin/Catawiki phase 2) sur tes
thèmes (Kenner vintage, comics SW/Marvel, Pokémon gradé, non-sport scellé),
identifier chaque pièce, comparer au marché, mesurer la tendance, et n'alerter
que sur les vraies pépites (sous-coté + tendance + qualité).

## Architecture (6 étapes)
Scout -> Identifier -> Market -> Trend -> GemScorer -> Alert
Mémoire de tendance maison sur Chroma (gratuit, se construit dans le temps).

## Démarrage rapide
```bash
cp .env.example .env            # puis remplir EBAY_CLIENT_ID / EBAY_CLIENT_SECRET
pip install -r requirements.txt # clés eBay gratuites sur developer.ebay.com
```

### Lancer un scan de la watchlist
```bash
python run.py scan                      # toutes les cibles
python run.py scan --universe comics    # un seul univers
```

### Évaluer une annonce eBay précise (par URL)
```bash
python run.py url "https://www.ebay.fr/itm/123456789012"
```
Le bot identifie la pièce, source un comp de marché, score /100 et calcule la
mise max conseillée (frais réels intégrés).

### Tests (logique métier, offline, sans réseau ni LLM)
```bash
pytest tests/
```

## Deux moteurs
- `run.py` : pipeline direct, **sans LLM** — la voie la plus courte vers un run réel.
- `crew.py` : variante multi-agents CrewAI orchestrée par LLM (phase 1.5+).

## Alerte
Sortie console toujours active. Push Telegram si `TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID`, Discord si `DISCORD_WEBHOOK_URL`. Push uniquement pour
les pépites (score >= 75).

## Phases
- Phase 1 (fait) : eBay Browse API + identify + comp actif + scorer + alerte + tests.
- Phase 1.5 : fallback LLM (Claude) sur annonces ambiguës ; Curator autonome.
- Phase 2 : connecteurs Leboncoin/Catawiki via scraping managé (Firecrawl/Apify).
            ⚠️ Zone grise CGU — décision risque à prendre.

## Le savoir métier est dans config/
`themes.py` (graders majeurs/mineurs, signaux Kenner, pièges) et `watchlist.py`
(cibles précises avec cote et prix d'achat). Éditable sans toucher au code.
