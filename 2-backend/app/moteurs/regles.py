"""Règles et statut global : agrège les contrôles de tous les modules (CdC § 6.8)."""
from __future__ import annotations

from typing import Literal

from app.moteurs.commun import Controle

Statut = Literal["bloque", "conforme_avec_reserves", "conforme"]
MODULES = ("implantation", "electricite", "structure", "toiture", "solaire", "metre")


def statut(controles: list[Controle]) -> Statut:
    if any(c.niveau == "bloquant" for c in controles):
        return "bloque"
    if any(c.niveau == "avertissement" for c in controles):
        return "conforme_avec_reserves"
    return "conforme"


def agreger(*listes: list[Controle]) -> tuple[list[Controle], Statut, dict[str, Statut]]:
    """Concatène les contrôles, vérifie l'unicité des identifiants, calcule les statuts."""
    tous = [c for liste in listes for c in liste]
    ids = [c.id for c in tous]
    doublons = {i for i in ids if ids.count(i) > 1}
    if doublons:
        raise ValueError(f"identifiants de contrôle en double : {sorted(doublons)}")
    par_module = {m: statut([c for c in tous if c.module == m]) for m in MODULES}
    return tous, statut(tous), par_module


def bloquants_corrigeables(controles: list[Controle]) -> list[Controle]:
    return [c for c in controles if c.niveau == "bloquant" and c.corrigeable]
