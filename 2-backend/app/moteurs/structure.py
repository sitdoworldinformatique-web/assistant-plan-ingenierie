"""Structure et fondations — maçonnerie chaînée R+0, semelles filantes (CdC § 6.4)."""
from __future__ import annotations

import math

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.implantation import EPS, Mur, ResultatImplantation
from app.moteurs.programme import Programme

N = normes.STRUCTURE
T = normes.TOITURE
MODULE = "structure"
REF = N["reference"]


class Semelle(BaseModel):
    id: str
    mur_id: str
    longueur: float
    largeur_reprise: float
    q_mur: float
    q_chainage: float
    q_toiture: float
    q_els: float
    largeur: float  # B
    hauteur: float  # h
    ferraillage: str
    trace: tuple[float, float, float, float]  # x, y, l, p pour le plan


class Poteau(BaseModel):
    id: str
    x: float
    y: float
    section: str
    armatures: str
    cadres: str
    motif: str


class Chainage(BaseModel):
    id: str
    type: str  # "horizontal" | "linteau"
    reference: str
    longueur: float
    section: str


class ResultatStructure(BaseModel):
    semelles: list[Semelle]
    poteaux: list[Poteau]
    chainages: list[Chainage]
    dallage: dict
    hauteur_mur: float
    controles: list[Controle]
    hypotheses: list[Hypothese]


def charge_toiture(programme: Programme) -> float:
    """Charge surfacique de toiture (kN/m², en plan)."""
    if programme.toiture == "terrasse":
        return N["terrasse_permanente"] + N["terrasse_exploitation"]
    return N["charge_toiture"]["tuiles" if programme.couverture == "tuiles" else "legere"]


def _largeur_reprise(m: Mur, murs: list[Mur], programme: Programme, prof_axe: float) -> float:
    """Largeur de toiture reprise par un mur porteur (demi-portées de part et d'autre)."""
    terrasse = programme.toiture == "terrasse"
    debord = 0.0 if terrasse else T["debord"]
    if not m.horizontal:
        if programme.toiture == "4 pans" and m.type == "exterieur":
            return prof_axe / 4 + debord
        return T["entraxe_fermes"] / 2
    # Murs horizontaux : appuis = murs extérieurs horizontaux (+ refends porteurs sous terrasse)
    appuis = [a for a in murs if a.horizontal and a.porteur and (terrasse or a.type == "exterieur")]
    if m not in appuis:
        return 0.0
    xm = (m.x1 + m.x2) / 2
    ys = sorted({a.y1 for a in appuis if min(a.x1, a.x2) - EPS <= xm <= max(a.x1, a.x2) + EPS})
    i = ys.index(next(y for y in ys if abs(y - m.y1) < EPS))
    largeur = 0.0
    largeur += (ys[i] - ys[i - 1]) / 2 if i > 0 else debord
    largeur += (ys[i + 1] - ys[i]) / 2 if i < len(ys) - 1 else debord
    return largeur


def _arrondi_sup(v: float, pas: float) -> float:
    return math.ceil(round(v / pas, 9)) * pas


def calculer(impl: ResultatImplantation, programme: Programme) -> ResultatStructure:
    p = programme
    hyp: list[Hypothese] = []
    ctl: list[Controle] = []

    def h(lib: str, val: str) -> None:
        hyp.append(Hypothese(module=MODULE, libelle=lib, valeur=val, source=REF))

    def c(id_, niveau, titre, detail):
        ctl.append(Controle(id=id_, module=MODULE, niveau=niveau, titre=titre, detail=detail, reference_norme=REF))

    hauteur_mur = p.hauteur_sous_plafond + N["surhauteur_mur"]
    g_mur = N["poids_mur"][p.maconnerie]
    cl, ch = N["section_chainage"]
    q_chainage = N["poids_beton_arme"] * cl * ch
    q_toit = charge_toiture(p)
    sigma = p.portance_sol * 1000  # MPa → kN/m²
    prof_axe = impl.parametres["profondeur_axe"]

    semelles: list[Semelle] = []
    for m in impl.murs:
        if not m.porteur:
            continue
        reprise = _largeur_reprise(m, impl.murs, p, prof_axe)
        q_mur = g_mur * hauteur_mur
        q_t = q_toit * reprise
        q = q_mur + q_chainage + q_t
        b = max(N["largeur_semelle_min"], _arrondi_sup(q / sigma, N["pas_arrondi_semelle"]))
        hs = max(N["hauteur_semelle_min"], (b - m.epaisseur) / 4 + N["enrobage_hauteur"])
        if m.horizontal:
            x0, x1 = sorted((m.x1, m.x2))
            trace = (x0 - b / 2, m.y1 - b / 2, x1 - x0 + b, b)
        else:
            y0, y1 = sorted((m.y1, m.y2))
            trace = (m.x1 - b / 2, y0 - b / 2, b, y1 - y0 + b)
        semelles.append(Semelle(id=f"S{len(semelles) + 1}", mur_id=m.id, longueur=m.longueur, largeur_reprise=reprise,
                                q_mur=q_mur, q_chainage=q_chainage, q_toiture=q_t, q_els=q, largeur=b, hauteur=hs,
                                ferraillage=f"{N['ferraillage_semelle']} — minimum constructif, à justifier par "
                                            "l'ingénieur", trace=trace))

    # Poteaux / chaînages verticaux : angles, jonctions de murs, ouvertures > 1,8 m
    pt = N["poteau"]
    positions: dict[tuple[float, float], str] = {}
    for m in impl.murs:
        for x, y in ((m.x1, m.y1), (m.x2, m.y2)):
            positions.setdefault((round(x, 3), round(y, 3)), "angle ou jonction de murs")
    for o in impl.ouvertures:
        if o.largeur > N["ouverture_poteaux_seuil"]:
            d = o.largeur / 2 + pt["section"][0] / 2
            for s in (-1, 1):
                xy = (o.x + s * d, o.y) if o.horizontal else (o.x, o.y + s * d)
                positions.setdefault((round(xy[0], 3), round(xy[1], 3)), f"ouverture de {fmt(o.largeur)} m")
    sec = f"{round(pt['section'][0] * 100)} × {round(pt['section'][1] * 100)}"
    poteaux = [Poteau(id=f"P{i + 1}", x=x, y=y, section=sec, armatures=pt["armatures"], cadres=pt["cadres"], motif=mo)
               for i, ((x, y), mo) in enumerate(sorted(positions.items()))]

    chainages = [Chainage(id=f"CH{i + 1}", type="horizontal", reference=m.id, longueur=m.longueur,
                          section=f"{round(cl * 100)} × {round(ch * 100)}") for i, m in enumerate(impl.murs)]
    for o in impl.ouvertures:
        chainages.append(Chainage(id=f"L{o.id}", type="linteau", reference=o.id,
                                  longueur=o.largeur + 2 * N["appui_linteau"],
                                  section=f"{round(o.epaisseur * 100)} × {round(ch * 100)}"))

    surface_dallage = sum(pc.surface_nette for pc in impl.pieces if not pc.exterieure)
    d = N["dallage"]
    dallage = {"surface": surface_dallage, "epaisseur": d["epaisseur"], "herisson": d["herisson"],
               "treillis": d["treillis"], "volume_beton": surface_dallage * d["epaisseur"]}

    # Contrôles
    if p.niveaux > 1:
        c("STRUCT-NIVEAUX", "bloquant", "Plusieurs niveaux : non pris en charge",
          "Le module structure ne traite que les maisons R+0 en maçonnerie chaînée.")
    if p.portance_sol < N["portance_min_superficielle"]:
        c("STRUCT-SOL", "bloquant", "Fondations superficielles inadaptées",
          f"σ sol = {fmt(p.portance_sol)} MPa < {fmt(N['portance_min_superficielle'])} MPa : étude spécifique requise.")
    if not p.portance_mesuree:
        c("STRUCT-PORTANCE", "avertissement", f"Portance supposée {fmt(p.portance_sol)} MPa",
          "Étude géotechnique recommandée avant exécution.")
    else:
        c("STRUCT-PORTANCE", "ok", "Portance du sol mesurée", f"σ sol = {fmt(p.portance_sol)} MPa.")
    if semelles:
        bmax = max(s.largeur for s in semelles)
        c("STRUCT-SEMELLES", "ok", "Semelles filantes",
          f"{len(semelles)} semelles, largeur maximale {fmt(bmax)} m ; ferraillage minimum constructif à justifier.")
    c("STRUCT-FERRAILLAGE", "avertissement", "Ferraillage forfaitaire",
      f"Semelles {N['ferraillage_semelle']} et poteaux {pt['armatures']} : minimum constructif à justifier "
      "par l'ingénieur.")

    h("Hauteur de mur (HSP + 0,30 m)", f"{fmt(hauteur_mur)} m")
    h("Poids surfacique du mur", f"{fmt(g_mur, 1)} kN/m² ({p.maconnerie})")
    h("Chaînage", f"{fmt(N['poids_beton_arme'], 0)} kN/m³ × {fmt(cl)} × {fmt(ch)} = {fmt(q_chainage)} kN/m")
    h("Charge de toiture (en plan)", f"{fmt(q_toit, 1)} kN/m²")
    h("Contrainte admissible du sol", f"{fmt(p.portance_sol)} MPa"
      + ("" if p.portance_mesuree else " (hypothèse prudente, non mesurée)"))
    h("Largeur de semelle", "B = q_ELS / σ_sol, minimum 0,40 m, arrondie aux 5 cm supérieurs")
    h("Hauteur de semelle", "h = max(0,25 ; (B − e_mur) / 4 + 0,05)")
    h("Cloisons", "posées sur le dallage, sans semelle")
    h("Dallage", f"béton {fmt(d['epaisseur'])} m sur hérisson {fmt(d['herisson'])} m, treillis {d['treillis']}")

    return ResultatStructure(semelles=semelles, poteaux=poteaux, chainages=chainages, dallage=dallage,
                             hauteur_mur=hauteur_mur, controles=ctl, hypotheses=hyp)
