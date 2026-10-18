"""Types partagés par les moteurs : contrôles et hypothèses."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Niveau = Literal["ok", "avertissement", "bloquant"]


class Controle(BaseModel):
    id: str
    module: str
    niveau: Niveau
    titre: str
    detail: str = ""
    reference_norme: str = ""
    corrigeable: bool = False


class Hypothese(BaseModel):
    module: str
    libelle: str
    valeur: str
    source: str = ""


def fmt(valeur: float, decimales: int = 2) -> str:
    """Nombre au format français (virgule décimale), pour les libellés d'hypothèses et de contrôles."""
    return f"{valeur:.{decimales}f}".replace(".", ",")
