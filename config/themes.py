"""
Config métier : thèmes de recherche + règles d'identification.
C'est ici qu'on encode tout ce qu'on a appris dans la conversation
(grader majeur only, détails Kenner qui font la valeur, etc.).
"""

# --- Thèmes prioritaires (point 2 : toutes les propositions) ---
THEMES = {
    "kenner_vintage": {
        "queries": [
            "star wars kenner darth vader vintage",
            "star wars kenner 12 back",
            "star wars kenner moc afa",
            "vintage star wars action figure kenner 1977 1978",
        ],
        "condition": None,  # on veut voir MOC (neuf) ET loose
    },
    "comics_starwars_marvel": {
        "queries": [
            "star wars 1 1977 cgc",
            "star wars 42 boba fett cgc",
            "marvel key issue cgc first appearance",
        ],
        "condition": None,
    },
    "pokemon_vintage_graded": {
        "queries": [
            "pokemon base set psa charizard",
            "pokemon wotc psa 9 holo",
            "pokemon team rocket psa",
        ],
        "condition": None,
    },
    "nonsport_sealed_8090s": {
        "queries": [
            "non sport sealed pack batman 1989",
            "marvel universe series 1 1990 sealed",
            "topps star wars 1977 sealed pack",
        ],
        "condition": None,
    },
}

# --- Graders reconnus (le reste = décote, cf. WCG/GCG vus dans la conv) ---
MAJOR_GRADERS = {"CGC", "PSA", "BGS", "CBCS", "AFA", "UKG", "NGC", "PCGS"}
MINOR_GRADERS = {"WCG", "GCG", "GCC", "MADNESS"}  # à pénaliser

# --- Signaux de valeur Kenner (ce qui transforme 25€ en pépite) ---
KENNER_VALUE_SIGNALS = {
    "dt_saber": ["double telescoping", "dt saber", "double telescopic"],  # 🚨 jackpot
    "12_back": ["12 back", "12-back", "douze dos"],                        # première vague 1978
    "moc": ["moc", "sur carte", "blister", "carded", "sealed", "unpunched"],
    "afa_graded": ["afa", "ukg", "graded"],
}

# --- Pièges à flagger ---
KENNER_TRAPS = [
    "black series", "vintage collection 2019", "réédition", "reproduction",
    "repro", "reissue", "the child", "mandalorian",  # = repros modernes
    "collection rétro",
    "collection retro",
    "rétro collection",
    "retro collection",
    "les temps sombres",
    "action masters",
]


# --- Pièges UNIVERSELS (tous univers) : mystery box / repack = espérance négative ---
GENERIC_TRAPS = [
    "mystery", "mystery box", "mystery repack", "repack", "grade'n", "grade n",
    "grade'n box", "random box", "boite mystere", "boîte mystère",
    "pochette surprise", "lot mystere", "lot mystère", "surprise box",
]


# --- Pièges COMICS : rééditions / facsimilés (pas l'original = pas de valeur) ---
COMIC_TRAPS = [
    "facsimile", "facsimilé", "reprint", "1rep", "multi-pack edition",
    "multi pack edition", "true believers", "30th anniversary edition",
    "marvel legends reprint", "facsimile edition", "newsstand reprint",
    "whitman",
    "diamond 35",
    "diamond price variant",
    "diamond variant",
    "35 cent reprint",
    "35c reprint",
    "treasury",
    "treasury edition",
    "marvel special edition",
    "collector's edition reprint",
]
