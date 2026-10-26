"""
GemHunter — orchestration CrewAI.

6 agents séquentiels + mémoire de tendance partagée :
  Scout -> Identifier -> Market -> Trend -> GemScorer -> Alert

NB : CrewAI s'installe via `pip install crewai`. Ici on montre la STRUCTURE.
Les @tool exposent nos fonctions (identify, get_comp, score_listing) aux agents.
Le LLM des agents peut être routé via LiteLLM (cf. ta stack) pour le coût.
"""
import os
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

from connectors.ebay import EbayConnector
from config.themes import THEMES
from tools.identify import identify
from tools.market import get_comp_from_active
from tools.scorer import score_listing

# --- Connecteur source (eBay en phase 1) ---
ebay = EbayConnector(
    client_id=os.environ.get("EBAY_CLIENT_ID", ""),
    client_secret=os.environ.get("EBAY_CLIENT_SECRET", ""),
)


# --- Outils exposés aux agents CrewAI ---
@tool("search_listings")
def search_listings_tool(query: str) -> list:
    """Recherche les annonces actives pour une requête donnée (eBay)."""
    listings = ebay.search(query, max_results=50)
    return [l.__dict__ for l in listings]


@tool("identify_item")
def identify_item_tool(title: str, description: str = "") -> dict:
    """Identifie grader, état, signaux de valeur et pièges d'une annonce."""
    return identify(title, description).__dict__


@tool("score_gem")
def score_gem_tool(price_eur: float, source: str, comp_median: float,
                   trend_direction: str, ident: dict) -> dict:
    """Note l'annonce /100 (décote + tendance + qualité) et donne la mise max."""
    from tools.identify import Identity
    id_obj = Identity(**{k: ident.get(k) for k in
                         ["grader", "grade", "grader_is_major", "is_graded",
                          "signals", "traps", "notes"] if k in ident})
    return score_listing(price_eur, source, id_obj, comp_median,
                          trend_direction).__dict__


# --- Agents ---
scout = Agent(
    role="Scout d'annonces",
    goal="Trouver toutes les annonces actives dans les thèmes ciblés",
    backstory="Chasseur infatigable qui ratisse les marketplaces.",
    tools=[search_listings_tool], verbose=True,
)
identifier = Agent(
    role="Expert d'identification",
    goal="Reconnaître la pièce exacte : grader, variante, signaux rares, pièges",
    backstory="Spécialiste vintage qui repère un DT saber au premier coup d'œil.",
    tools=[identify_item_tool], verbose=True,
)
analyst = Agent(
    role="Analyste marché & tendance",
    goal="Établir le comp de marché et la dynamique de prix",
    backstory="Connaît les cotes réelles, pas les prix affichés gonflés.",
    verbose=True,
)
scorer = Agent(
    role="Juge des pépites",
    goal="Noter chaque annonce et ne retenir que les vraies opportunités",
    backstory="Impitoyable : sous-coté + tendance + qualité, sinon poubelle.",
    tools=[score_gem_tool], verbose=True,
)
alerter = Agent(
    role="Notificateur",
    goal="Envoyer les pépites (score>=75) avec lien, comp, tendance, mise max",
    backstory="Ne dérange l'utilisateur que pour les vraies affaires.",
    verbose=True,
)


def build_crew() -> Crew:
    tasks = [
        Task(description="Pour chaque thème de THEMES, lance search_listings.",
             agent=scout, expected_output="Liste d'annonces brutes normalisées."),
        Task(description="Identifie chaque annonce (grader/variante/signaux/pièges).",
             agent=identifier, expected_output="Annonces enrichies d'une Identity."),
        Task(description="Calcule le comp de marché et la tendance par pièce.",
             agent=analyst, expected_output="comp_median + trend par annonce."),
        Task(description="Score chaque annonce /100, calcule la mise max.",
             agent=scorer, expected_output="GemScore par annonce."),
        Task(description="Notifie uniquement les annonces score>=75.",
             agent=alerter, expected_output="Alertes envoyées."),
    ]
    return Crew(agents=[scout, identifier, analyst, scorer, alerter],
                tasks=tasks, process=Process.sequential, verbose=True)


if __name__ == "__main__":
    crew = build_crew()
    crew.kickoff()
