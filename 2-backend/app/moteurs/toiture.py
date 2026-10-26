"""Toiture : surfaces, charpente, eaux pluviales (CdC § 6.5)."""
from __future__ import annotations

import math

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.implantation import ResultatImplantation
from app.moteurs.programme import Programme

T = normes.TOITURE
MODULE = "toiture"
REF = T["reference"]


class ResultatToiture(BaseModel):
    type: str
    couverture: str
    pente: float  # %
    surface_plan: float  # projetée, débords compris
    surface: float  # rampante
    debord: float
    fermes: int
    longueur_fermes_ml: float
    pannes_ml: float
    liteaux_ml: float
    aretiers_ml: float
    faitage_ml: float
    charpente_ml: float
    gouttieres: float  # ml
    descentes: int
    dalle_volume: float
    acrotere_ml: float
    controles: list[Controle]
    hypotheses: list[Hypothese]


def _rectangles(impl: ResultatImplantation, debord: float) -> list[tuple[float, float]]:
    """Rectangles de toiture (longueur selon x, portée selon y), débords compris."""
    em = impl.emprise
    e = em.epaisseur_ext
    w = impl.parametres["largeur_axe"]
    d = impl.parametres["profondeur_axe"]
    rects = [(w + e + 2 * debord, d + e + 2 * debord)]
    if impl.parametres["largeur_garage"]:
        dj = impl.parametres["profondeur_jour"]
        rects.append((impl.parametres["largeur_garage"], dj + e + 2 * debord))
    return rects


def calculer(impl: ResultatImplantation, programme: Programme) -> ResultatToiture:
    p = programme
    ctl: list[Controle] = []
    hyp: list[Hypothese] = []

    def c(id_, niveau, titre, detail, corrigeable=False):
        ctl.append(Controle(id=id_, module=MODULE, niveau=niveau, titre=titre, detail=detail, reference_norme=REF,
                            corrigeable=corrigeable))

    def h(lib, val):
        hyp.append(Hypothese(module=MODULE, libelle=lib, valeur=val, source=REF))

    terrasse = p.toiture == "terrasse"
    debord = 0.0 if terrasse else T["debord"]
    rects = _rectangles(impl, debord)
    surface_plan = sum(a * b for a, b in rects)
    pente = p.pente_toiture / 100
    cos = math.cos(math.atan(pente))
    surface = surface_plan if terrasse else surface_plan / cos

    fermes = 0
    ferme_ml = pannes = liteaux = aretiers = faitage = 0.0
    dalle_volume = acrotere = 0.0
    gouttieres = 0.0
    if terrasse:
        dalle_volume = surface_plan * T["dalle_terrasse"]
        acrotere = 2 * sum(a + b for a, b in rects) - (2 * rects[1][1] if len(rects) > 1 else 0.0)
    else:
        for longueur, portee in rects:
            demi = portee / 2
            rampant = demi / cos
            hauteur = demi * pente
            n_f = math.ceil(longueur / T["entraxe_fermes"]) + 1
            fermes += n_f
            # ferme : 2 arbalétriers + entrait + poinçon + contrefiches (≈ un rampant)
            ferme_ml += n_f * (2 * rampant + portee + hauteur + rampant)
            lignes = math.ceil(rampant / T["entraxe_pannes"].get(p.couverture, 1.0)) + 1
            pannes += 2 * lignes * longueur
            if p.couverture == "tuiles":
                liteaux += 2 * (math.ceil(rampant / T["entraxe_liteaux"]) + 1) * longueur
            if p.toiture == "4 pans":
                aretiers += 4 * math.sqrt(2 * demi ** 2 + hauteur ** 2)
                faitage += max(0.0, longueur - portee)
                gouttieres += 2 * (longueur + portee)
            else:
                faitage += longueur
                gouttieres += 2 * longueur
    charpente_ml = ferme_ml + pannes + liteaux + aretiers + faitage
    descentes = max(T["descentes_min"], math.ceil(surface_plan / T["surface_par_descente"]))

    # Contrôles
    mini = T["pente_min"][p.couverture]
    if terrasse and p.couverture != "dalle beton":
        c("TOIT-COUVERTURE", "bloquant", "Couverture incompatible avec une toiture terrasse",
          f"« {p.couverture} » sur une terrasse : retenir « dalle beton ».", corrigeable=True)
    elif not terrasse and p.couverture == "dalle beton":
        c("TOIT-COUVERTURE", "bloquant", "Couverture incompatible avec une toiture en pente",
          "Une dalle béton suppose une toiture terrasse.", corrigeable=True)
    if p.pente_toiture + 1e-9 < mini:
        c("TOIT-PENTE", "bloquant", "Pente trop faible pour la couverture",
          f"{fmt(p.pente_toiture, 0)} % < {fmt(mini, 0)} % minimum pour « {p.couverture} ».", corrigeable=True)
    elif terrasse and p.pente_toiture > T["pente_max_terrasse"]:
        c("TOIT-PENTE", "avertissement", "Pente de terrasse élevée",
          f"{fmt(p.pente_toiture, 1)} % > {fmt(T['pente_max_terrasse'], 0)} % usuels (forme de pente).")
    else:
        c("TOIT-PENTE", "ok", "Pente de toiture", f"{fmt(p.pente_toiture, 0)} % ≥ {fmt(mini, 0)} % pour « {p.couverture} ».")
    c("TOIT-VENT", "avertissement", "Zone cyclonique / vents forts",
      "Ancrer chaque ferme dans le chaînage haut (feuillards ou tiges scellées)." if not terrasse else
      "Vérifier l'étanchéité et les relevés d'acrotère face aux pluies battantes.")
    c("TOIT-EP", "ok", "Eaux pluviales",
      f"{descentes} descentes pour {fmt(surface_plan, 1)} m² projetés (1 pour {fmt(T['surface_par_descente'], 0)} m², "
      f"minimum {T['descentes_min']}).")

    h("Débord de toiture", f"{fmt(debord)} m")
    h("Surface rampante", "surface en plan avec débords / cos(arctan(pente))")
    if not terrasse:
        h("Entraxe des fermes", f"{fmt(T['entraxe_fermes'])} m")
        h("Entraxe des pannes", f"{fmt(T['entraxe_pannes'].get(p.couverture, 1.0))} m")
        h("Bois d'une ferme", "2 arbalétriers + entrait + poinçon + contrefiches (≈ 1 rampant)")
    else:
        h("Dalle de toiture", f"{fmt(T['dalle_terrasse'])} m, acrotère {fmt(T['acrotere'])} m")
    h("Descentes d'eaux pluviales", f"1 pour {fmt(T['surface_par_descente'], 0)} m² projetés, minimum {T['descentes_min']}")

    return ResultatToiture(type=p.toiture, couverture=p.couverture, pente=p.pente_toiture, surface_plan=surface_plan,
                           surface=surface, debord=debord, fermes=fermes, longueur_fermes_ml=ferme_ml, pannes_ml=pannes,
                           liteaux_ml=liteaux, aretiers_ml=aretiers, faitage_ml=faitage, charpente_ml=charpente_ml,
                           gouttieres=gouttieres, descentes=descentes, dalle_volume=dalle_volume, acrotere_ml=acrotere,
                           controles=ctl, hypotheses=hyp)
