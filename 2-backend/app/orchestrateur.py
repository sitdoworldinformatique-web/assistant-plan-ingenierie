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

from app.moteurs import chaine, commandes, regles
from app.moteurs.commun import fmt
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


def commander(texte: str, courant: Programme, surface_sejour: float | None, ia: ClientIA | None,
              journal: Journal) -> tuple[Programme, list[commandes.Changement], list[str], str]:
    """Commande en langage naturel → programme modifié. Claude si configuré, sinon (ou en cas d'échec) les règles.

    Renvoie (programme, changements, remarques, source). Les données de terrain ne viennent jamais de l'IA."""
    prog_regles, ch_regles, rem_regles = commandes.appliquer(courant, texte, surface_sejour)
    if ia is not None:
        debut = time.perf_counter()
        demande = ("Programme actuel (JSON) :\n" + json.dumps(courant.model_dump(mode="json"), ensure_ascii=False)
                   + "\n\nCommande du constructeur : " + texte
                   + "\n\nRenvoie le programme complet après application de cette seule commande ;"
                   " ne change aucun autre champ.")
        try:
            brut = ia.interpreter(demande, Programme.model_json_schema())
            remarques = brut.pop("remarques", []) if isinstance(brut, dict) else []
            prog_ia = Programme(**brut)
            prog = prog_ia.model_copy(update={c: getattr(prog_regles, c) for c in CHAMPS_TERRAIN})
            changements = commandes.differences(courant, prog)
            journal.ajouter("commander", texte, [c.en_dict() for c in changements], ia.modele, debut)
            return prog, changements, [str(r) for r in remarques], "ia"
        except Exception as e:
            journal.ajouter("commander", texte, f"erreur : {e.__class__.__name__}", ia.modele, debut, erreur=True)
    return prog_regles, ch_regles, rem_regles, "regles"


def message_commande(changements: list[commandes.Changement], avant: dict, apres: chaine.Resultats) -> str:
    """Réponse en français à une commande : ce qui a changé, puis ce que les moteurs en disent."""
    if not changements:
        return "Rien n'a changé."
    texte = "C'est fait. " + " ; ".join(commandes.decrire(c) for c in changements) + "."
    avant_bloquants = {c["id"] for c in avant.get("controles", []) if c["niveau"] == "bloquant"}
    bloquants = [c for c in apres.controles if c.niveau == "bloquant"]
    nouveaux = [c for c in bloquants if c.id not in avant_bloquants]
    resolus = len(avant_bloquants - {c.id for c in bloquants})
    if nouveaux:
        texte += " Attention, les moteurs signalent : " + " ; ".join(f"{c.titre} ({c.detail})" for c in nouveaux[:2]) + "."
    elif bloquants:
        texte += f" {len(bloquants)} point(s) bloquant(s) restent à lever (voir l'onglet Validation)."
    elif resolus:
        texte += f" {resolus} point(s) bloquant(s) levé(s) : plus aucun blocage."
    else:
        texte += " Aucun point bloquant."
    return texte


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


def contexte_element(resultats: dict, element_id: str) -> dict | None:
    """Contrôle (ex. ELEC-DU-C4) ou circuit (ex. C4, ecl-1) → données et hypothèses à expliquer."""
    elec = resultats.get("electricite") or {}
    circuits = elec.get("circuits") or []

    def circuit(ident: str) -> dict | None:
        ident = ident.upper()
        return next((c for c in circuits if f"C{c.get('num')}" == ident or str(c.get("key", "")).upper() == ident),
                    None)

    controle = next((c for c in resultats.get("controles", []) if c["id"] == element_id), None)
    if controle is not None:
        module = controle["module"]
        ctx: dict = {"type": "controle", "controle": controle}
        suffixe = element_id.rsplit("-", 1)[-1]
        if module == "electricite" and (c := circuit(suffixe)) is not None:
            ctx["circuit"] = c
    elif (c := circuit(element_id)) is not None:
        module = "electricite"
        ctx = {"type": "circuit", "circuit": c,
               "controles": [k for k in resultats.get("controles", []) if k["id"].endswith(f"-C{c.get('num')}")]}
    else:
        return None
    ctx["hypotheses"] = [h for h in resultats.get("hypotheses", []) if h.get("module") == module]
    return ctx


def _explication_regles(ctx: dict) -> str:
    """Explication sans IA : reprend mot pour mot ce que le moteur a écrit."""
    if ctx["type"] == "controle":
        c = ctx["controle"]
        texte = f"{c['titre']}. {c['detail']}"
        if c.get("reference_norme"):
            texte += f" Référence : {c['reference_norme']}."
        return texte
    c = ctx["circuit"]
    return (f"Circuit C{c['num']} « {c['nom']} » ({c['det']}) : protection {c['in_']} A, section {fmt(c['s'])} mm², "
            f"longueur {fmt(c['l'], 1)} m, chute de tension {fmt(c['du'])} % pour une limite de {fmt(c['lim'])} %.")


def expliquer(ctx: dict, ia: ClientIA | None, journal: Journal) -> tuple[str, str]:
    """Renvoie (texte, source) : source = « ia » ou « regles » (sans clé, ou si l'IA échoue)."""
    if ia is not None:
        debut = time.perf_counter()
        try:
            texte = ia.expliquer(ctx)
            journal.ajouter("expliquer", ctx, texte, ia.modele, debut)
            return texte, "ia"
        except Exception as e:
            journal.ajouter("expliquer", ctx, f"erreur : {e.__class__.__name__}", ia.modele, debut, erreur=True)
    return _explication_regles(ctx), "regles"
