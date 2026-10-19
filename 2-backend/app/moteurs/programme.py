"""Modèle `Programme` (entrée de tous les moteurs) et analyseur par règles.

L'analyseur par règles est le secours quand l'IA texte n'est pas configurée ou échoue.
Il ne renseigne jamais une donnée de terrain que le texte ne donne pas explicitement.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Toiture = Literal["2 pans", "4 pans", "terrasse"]
Couverture = Literal["tole bac acier", "tole ondulee", "tuiles", "dalle beton"]
Maconnerie = Literal["parpaing 20", "parpaing 15", "brique"]
Equipement = Literal["plaque", "four", "lavelinge", "lavevaisselle", "chauffeeau", "pompe"]

EQUIPEMENTS_DEFAUT: list[str] = ["plaque", "four", "lavelinge", "chauffeeau", "pompe"]

# Champs que l'IA n'a jamais le droit de modifier (données de terrain)
CHAMPS_TERRAIN = frozenset({"resistance_terre", "portance_sol", "portance_mesuree"})


class Programme(BaseModel):
    """Programme de la maison. Unités : m, m², MPa, Ω, h."""

    model_config = ConfigDict(extra="forbid")

    nom: str = "Maison individuelle"
    niveaux: int = Field(1, ge=1, le=10, description="MVP : 1 seul niveau (R+0)")
    chambres: int = Field(3, ge=0, le=8)
    salles_de_bain: int = Field(1, ge=1, le=4)
    wc_separe: bool = True
    bureau: bool = False
    garage: bool = False
    veranda: bool = True
    cuisine_ouverte: bool = False
    surface_sejour: float = Field(0, ge=0, description="m², 0 = automatique")
    terrain_largeur: float = Field(15, gt=0)
    terrain_profondeur: float = Field(20, gt=0)
    recul: float = Field(2.0, ge=0, description="distance minimale aux limites (m)")
    hauteur_sous_plafond: float = Field(3.0, gt=2, le=6)
    toiture: Toiture = "2 pans"
    couverture: Couverture = "tole bac acier"
    pente_toiture: float = Field(25, ge=0, le=100, description="%")
    maconnerie: Maconnerie = "parpaing 20"
    portance_sol: float = Field(0.15, gt=0, description="MPa, hypothèse prudente si non mesurée")
    portance_mesuree: bool = False
    clim_chambres: bool = True
    clim_sejour: bool = True
    equipements: list[Equipement] = Field(default_factory=lambda: list(EQUIPEMENTS_DEFAUT))
    resistance_terre: float | None = Field(None, ge=0, description="Ω, mesurée sur site")
    solaire: bool = True
    autonomie_h: float = Field(6, ge=0)
    ensoleillement_h: float = Field(4.5, gt=0)
    devise: str = "USD"
    longueurs_circuits: dict[str, float] = Field(default_factory=dict)


def schema_json() -> dict:
    """JSON Schema de `Programme` (utilisé comme `input_schema` de l'outil Claude)."""
    return Programme.model_json_schema()


# ---------------------------------------------------------------------------
# Analyseur par règles
# ---------------------------------------------------------------------------

_NOMBRES = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}
_N = r"(\d+|zero|une?|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)"
_F = r"(\d+(?:[.,]\d+)?)"


def _normaliser(texte: str) -> str:
    t = unicodedata.normalize("NFD", texte.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("²", "2").replace("×", "x").replace("’", "'").replace("Ω", " ohm")
    t = t.replace("ω", " ohm")
    return re.sub(r"\s+", " ", t)


def _entier(mot: str) -> int:
    return int(mot) if mot.isdigit() else _NOMBRES[mot]


def _flottant(txt: str) -> float:
    return float(txt.replace(",", "."))


def _cherche(motif: str, t: str) -> re.Match | None:
    return re.search(motif, t)


def _extraire(texte: str, commande: bool = False) -> tuple[dict, list[str]]:
    """Champs du `Programme` que le texte donne explicitement + remarques. En mode commande, le texte ne
    complète qu'un programme existant : pas de remarque sur les données absentes."""
    t = _normaliser(texte)
    v: dict = {}
    remarques: list[str] = []

    # Nom
    if "villa" in t and not commande:
        v["nom"] = "Villa"

    # Niveaux
    m = _cherche(r"\br\s*\+\s*(\d)", t)
    if m:
        v["niveaux"] = 1 + int(m.group(1))
    elif re.search(r"\b(duplex|a etage|avec etage|un etage|1 etage)\b", t):
        v["niveaux"] = 2
    elif re.search(r"plain[- ]?pied|rez[- ]de[- ]chaussee|\bplain pied\b", t):
        v["niveaux"] = 1
    if v.get("niveaux", 1) > 1:
        remarques.append("Plusieurs niveaux demandés : non pris en charge par le MVP (R+0 uniquement).")

    # Chambres
    m = _cherche(_N + r" chambres?\b", t)
    if m:
        n = _entier(m.group(1))
        if n > 8:
            remarques.append(f"{n} chambres demandées : limité à 8.")
            n = 8
        v["chambres"] = n
    else:
        m = _cherche(r"\b[ft]\s?(\d)\b", t)
        if m and int(m.group(1)) >= 1:
            v["chambres"] = min(8, int(m.group(1)) - 1)
        elif re.search(r"\bstudio\b|sans chambre", t):
            v["chambres"] = 0

    # Salles de bain
    m = _cherche(_N + r" (?:salles? (?:de bains?|d'eau)|sdb)\b", t)
    if m:
        n = _entier(m.group(1))
        if n < 1 or n > 4:
            remarques.append(f"{n} salle(s) de bain demandée(s) : ramené entre 1 et 4.")
            n = min(4, max(1, n))
        v["salles_de_bain"] = n

    # WC
    if re.search(r"sans wc separe|wc (?:dans|integre a) la (?:salle de bains?|sdb)|wc non separe", t):
        v["wc_separe"] = False
    elif re.search(r"wc separes?|toilettes? separees?", t):
        v["wc_separe"] = True

    # Bureau, garage, véranda
    for cle, motif in (("bureau", r"bureau"), ("garage", r"garage"), ("veranda", r"veranda|terrasse couverte")):
        if re.search(r"(?:sans|pas de) (?:\w+ )?(?:" + motif + r")", t):
            v[cle] = False
        elif re.search(motif, t):
            v[cle] = True

    # Cuisine
    if re.search(r"cuisine (?:ouverte|americaine)", t):
        v["cuisine_ouverte"] = True
    elif re.search(r"cuisine (?:fermee|separee|independante)", t):
        v["cuisine_ouverte"] = False

    # Surface du séjour
    m = _cherche(r"(?:sejour|salon)(?: \w+){0,2}? (?:de )?" + _F + r" ?m2", t)
    if m:
        v["surface_sejour"] = _flottant(m.group(1))

    # Terrain
    m = _cherche(r"(?:terrain|parcelle|lot)(?: \w+){0,2}? (?:de )?" + _F + r" ?m? ?(?:x|par|sur) ?" + _F, t)
    if m:
        v["terrain_largeur"] = _flottant(m.group(1))
        v["terrain_profondeur"] = _flottant(m.group(2))
    elif not commande:
        remarques.append("Dimensions du terrain non précisées : 15 × 20 m retenu par défaut.")

    m = _cherche(r"recul(?: \w+){0,2}? (?:de )?" + _F + r" ?m\b", t)
    if m:
        v["recul"] = _flottant(m.group(1))

    m = _cherche(r"(?:hauteur sous plafond|hsp)(?: de)? " + _F, t)
    if m:
        v["hauteur_sous_plafond"] = _flottant(m.group(1))

    # Toiture
    if re.search(r"\b(?:4|quatre) pans\b|toit a quatre", t):
        v["toiture"] = "4 pans"
    elif re.search(r"\b(?:2|deux) pans\b|double pente", t):
        v["toiture"] = "2 pans"
    elif re.search(r"toit(?:ure)? (?:en )?terrasse|toit plat|toiture plate|dalle de toiture", t):
        v["toiture"] = "terrasse"
    elif re.search(r"\b(?:1|un|mono) ?pan\b|monopente", t):
        remarques.append("Toiture à un pan non prise en charge : 2 pans retenu.")

    # Couverture
    if v.get("toiture") == "terrasse":
        v["couverture"] = "dalle beton"
    elif re.search(r"tuiles?", t):
        v["couverture"] = "tuiles"
    elif re.search(r"tole ondulee|ondulee", t):
        v["couverture"] = "tole ondulee"
    elif re.search(r"bac acier|bac alu", t):
        v["couverture"] = "tole bac acier"
    elif re.search(r"\btoles?\b", t):
        v["couverture"] = "tole bac acier"
        remarques.append("Type de tôle non précisé : bac acier retenu.")

    m = _cherche(r"pente(?: \w+){0,2}? (?:de )?" + _F + r" ?(?:%|pour ?cent)", t)
    if m:
        v["pente_toiture"] = _flottant(m.group(1))
    elif v.get("toiture") == "terrasse":
        v["pente_toiture"] = 2
    elif v.get("couverture") == "tuiles":
        v["pente_toiture"] = 45
        remarques.append("Pente non précisée pour des tuiles : 45 % retenu.")

    # Maçonnerie
    if re.search(r"brique", t):
        v["maconnerie"] = "brique"
    elif re.search(r"(?:parpaings?|agglos?|blocs?)(?: de)? 15\b", t):
        v["maconnerie"] = "parpaing 15"
    elif re.search(r"(?:parpaings?|agglos?|blocs?)(?: de)? 20\b", t):
        v["maconnerie"] = "parpaing 20"

    # Sol (donnée de terrain : seulement si explicitement donnée)
    m = _cherche(r"(?:portance|contrainte (?:admissible )?du sol|sol)(?: \w+){0,3}? " + _F + r" ?(mpa|bars?|kpa)", t)
    if m:
        val = _flottant(m.group(1))
        unite = m.group(2)
        v["portance_sol"] = val / 10 if unite.startswith("bar") else val / 1000 if unite == "kpa" else val
        if re.search(r"mesuree|etude (?:de sol|geotechnique)|essai", t):
            v["portance_mesuree"] = True
        else:
            remarques.append("Portance donnée sans mention d'une mesure : considérée comme non mesurée.")

    # Climatisation
    if re.search(r"sans (?:clim|climatisation|climatiseur)", t):
        v["clim_chambres"] = False
        v["clim_sejour"] = False
    else:
        m = _cherche(r"(?:clim|climatisation|climatiseurs?)\b([^.;]*)", t)
        if m:
            suite = m.group(1)[:60]
            if "partout" in suite or "toutes les pieces" in suite:
                v["clim_chambres"] = v["clim_sejour"] = True
            else:
                ch = "chambre" in suite
                se = "sejour" in suite or "salon" in suite
                if ch or se:
                    v["clim_chambres"] = ch
                    v["clim_sejour"] = se

    # Équipements
    motifs_eq = {
        "plaque": r"plaques?(?: de cuisson| electrique)?|cuisiniere|table de cuisson",
        "four": r"\bfour\b",
        "lavelinge": r"lave[- ]?linge|machine a laver",
        "lavevaisselle": r"lave[- ]?vaisselle",
        "chauffeeau": r"chauffe[- ]?eau|ballon d'eau chaude|cumulus",
        "pompe": r"\bpompe\b|surpresseur|forage",
    }
    presents, absents = [], []
    for code, motif in motifs_eq.items():
        if re.search(r"sans (?:" + motif + r")", t):
            absents.append(code)
        elif re.search(motif, t):
            presents.append(code)
    if presents:
        v["equipements"] = presents
    elif absents:
        v["equipements"] = [e for e in EQUIPEMENTS_DEFAUT if e not in absents]

    # Terre (donnée de terrain)
    m = _cherche(r"(?:resistance de (?:la )?terre|prise de terre|terre)(?: \w+){0,2}? (?:de )?" + _F + r" ?ohms?", t)
    if m:
        v["resistance_terre"] = _flottant(m.group(1))
    elif not commande:
        remarques.append("Résistance de la prise de terre non fournie : mesure sur site requise.")

    # Solaire
    if re.search(r"sans (?:solaire|panneaux|secours solaire|kit solaire)", t):
        v["solaire"] = False
    elif re.search(r"solaire|panneaux", t):
        v["solaire"] = True
    m = _cherche(r"autonomie(?: \w+){0,2}? (?:de )?" + _F + r" ?h", t)
    if m:
        v["autonomie_h"] = _flottant(m.group(1))
    m = _cherche(r"ensoleillement(?: \w+){0,2}? (?:de )?" + _F + r" ?h", t)
    if m:
        v["ensoleillement_h"] = _flottant(m.group(1))

    # Devise
    if re.search(r"\bcdf\b|francs? congolais", t):
        v["devise"] = "CDF"
    elif re.search(r"\beur\b|euros?", t):
        v["devise"] = "EUR"

    return v, remarques


def analyser(texte: str) -> tuple[Programme, list[str]]:
    """Transforme un texte libre en `Programme` + liste de remarques (ambiguïtés)."""
    v, remarques = _extraire(texte)
    return Programme(**v), remarques
