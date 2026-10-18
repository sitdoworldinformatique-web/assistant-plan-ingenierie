"""Pipeline IA → moteurs → contrôles (CdC § 7).

1. INTERPRÉTER   texte → Programme (Claude, sortie structurée ; secours : analyseur par règles)
2. CALCULER      Programme → tous les moteurs
3. CONTRÔLER     regles.py
4. AUTO-CORRIGER bloquants corrigeables → Claude propose un Programme corrigé (2 itérations max),
                 jamais de modification des données de terrain
5. DESSINER      (à la demande, par l'API)
6. JOURNALISER   chaque étape IA dans journal_ia
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from app.moteurs import chaine, regles
from app.moteurs.normes import VERSION_MOTEURS
from app.moteurs.programme import CHAMPS_TERRAIN, Programme, analyser

log = logging.getLogger("orchestrateur")

MAX_ITERATIONS_CORRECTION = 2
# Champs que l'auto-correction a le droit de modifier (emprise, pente, surfaces)
CHAMPS_CORRIGEABLES = frozenset({
    "recul", "veranda", "garage", "bureau", "chambres", "salles_de_bain", "surface_sejour", "pente_toiture",
    "couverture", "toiture", "cuisine_ouverte", "wc_separe",
})


class ClientIA(Protocol):
    modele: str

    def interpreter(self, texte: str, schema: dict) -> dict: ...

    def corriger(self, programme: dict, controles: list[dict], schema: dict) -> dict: ...

    def expliquer(self, contexte: dict) -> str: ...


def empreinte(programme: Programme) -> str:
    donnees = json.dumps(programme.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((donnees + "|" + VERSION_MOTEURS).encode("utf-8")).hexdigest()


def _resume(obj: Any, n: int = 200) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


class Journal:
    def __init__(self) -> None:
        self.entrees: list[dict] = []

    def ajouter(self, etape: str, entree: Any, sortie: Any, modele: str, debut: float, **extra) -> None:
        self.entrees.append({
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "etape": etape,
            "entree_resume": _resume(entree),
            "sortie_resume": _resume(sortie),
            "modele": modele,
            "duree_ms": round((time.perf_counter() - debut) * 1000),
            **extra,
        })


def interpreter(texte: str, ia: ClientIA | None, journal: Journal) -> tuple[Programme, list[str]]:
    """Texte → Programme. Claude (2 tentatives) puis secours par règles."""
    if ia is not None:
        for tentative in (1, 2):
            debut = time.perf_counter()
            try:
                brut = ia.interpreter(texte, Programme.model_json_schema())
                remarques = brut.pop("remarques", []) if isinstance(brut, dict) else []
                prog_ia = Programme(**brut)
                # Jamais de donnée de terrain inventée : seules celles que le texte donne explicitement
                prog_regles, _ = analyser(texte)
                prog = prog_ia.model_copy(update={c: getattr(prog_regles, c) for c in CHAMPS_TERRAIN})
                if any(getattr(prog, c) != getattr(prog_ia, c) for c in CHAMPS_TERRAIN):
                    remarques = list(remarques) + [
                        "Données de terrain (terre, portance) reprises uniquement du texte saisi."]
                journal.ajouter("interpreter", texte, prog.model_dump(), ia.modele, debut, tentative=tentative)
                return prog, [str(r) for r in remarques]
            except (ValidationError, TypeError, ValueError) as e:
                journal.ajouter("interpreter", texte, f"sortie invalide : {e.__class__.__name__}", ia.modele, debut,
                                tentative=tentative, erreur=True)
            except Exception as e:  # IA indisponible : on passe au secours
                journal.ajouter("interpreter", texte, f"erreur : {e.__class__.__name__}", ia.modele, debut,
                                tentative=tentative, erreur=True)
                break
    debut = time.perf_counter()
    prog, remarques = analyser(texte)
    journal.ajouter("interpreter", texte, prog.model_dump(), "analyseur-par-regles", debut)
    return prog, remarques


def corriger(programme: Programme, resultats: chaine.Resultats, ia: ClientIA | None, journal: Journal,
             prix: dict | None) -> tuple[Programme, chaine.Resultats, list[dict]]:
    """Auto-correction des bloquants corrigeables (2 itérations au plus)."""
    corrections: list[dict] = []
    if ia is None:
        return programme, resultats, corrections
    for iteration in range(1, MAX_ITERATIONS_CORRECTION + 1):
        bloquants = regles.bloquants_corrigeables(resultats.controles)
        if not bloquants:
            break
        debut = time.perf_counter()
        entree = {"programme": programme.model_dump(mode="json"),
                  "controles": [c.model_dump() for c in bloquants]}
        try:
            brut = ia.corriger(entree["programme"], entree["controles"], Programme.model_json_schema())
            nouveau = Programme(**brut["programme"])
        except Exception as e:
            journal.ajouter("corriger", entree, f"échec : {e.__class__.__name__}", ia.modele, debut,
                            iteration=iteration, erreur=True)
            break
        avant, apres = programme.model_dump(), nouveau.model_dump()
        modifies = sorted(k for k in apres if apres[k] != avant[k])
        interdits = [k for k in modifies if k not in CHAMPS_CORRIGEABLES]
        if interdits:
            journal.ajouter("corriger", entree, f"refusé : champs non autorisés {interdits}", ia.modele, debut,
                            iteration=iteration, erreur=True)
            break
        if not modifies:
            journal.ajouter("corriger", entree, "aucune modification proposée", ia.modele, debut, iteration=iteration)
            break
        programme = nouveau
        resultats = chaine.calculer(programme, prix)
        correction = {"iteration": iteration, "explication": str(brut.get("explication", "")),
                      "champs_modifies": modifies, "avant": {k: avant[k] for k in modifies},
                      "apres": {k: apres[k] for k in modifies}}
        corrections.append(correction)
        journal.ajouter("corriger", entree, correction, ia.modele, debut, iteration=iteration)
    return programme, resultats, corrections


def generer(texte: str | None, programme: Programme | None, ia: ClientIA | None, prix: dict | None = None) -> dict:
    """Pipeline complet. Renvoie programme, remarques, résultats, corrections, journal, empreinte."""
    journal = Journal()
    remarques: list[str] = []
    if programme is None:
        programme, remarques = interpreter(texte or "", ia, journal)
    resultats = chaine.calculer(programme, prix)
    programme, resultats, corrections = corriger(programme, resultats, ia, journal, prix)
    return {"programme": programme, "remarques": remarques, "resultats": resultats, "corrections": corrections,
            "journal_ia": journal.entrees, "empreinte": empreinte(programme)}


def expliquer(contexte: dict, ia: ClientIA | None, journal: Journal) -> str:
    debut = time.perf_counter()
    texte = ia.expliquer(contexte) if ia is not None else ""
    journal.ajouter("expliquer", contexte, texte, ia.modele if ia else "", debut)
    return texte
