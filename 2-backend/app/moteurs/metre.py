"""Métré et devis (CdC § 6.7). Quantités calculées ; prix lus dans la table des prix."""
from __future__ import annotations

import math
from collections import Counter

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.electricite import ResultatElectricite
from app.moteurs.implantation import ResultatImplantation
from app.moteurs.prix_defaut import MENTION, PRIX_DEFAUT
from app.moteurs.programme import Programme
from app.moteurs.solaire import ResultatSolaire
from app.moteurs.structure import ResultatStructure
from app.moteurs.toiture import ResultatToiture

M = normes.METRE
ST = normes.STRUCTURE
MODULE = "metre"
REF = M["reference"]


class Ligne(BaseModel):
    lot: str
    code: str
    poste: str
    quantite: float
    unite: str
    prix_unitaire: float
    total: float


class ResultatMetre(BaseModel):
    lignes: list[Ligne]
    total: float
    devise: str
    mention_prix: str
    quantites: dict[str, float]
    controles: list[Controle]
    hypotheses: list[Hypothese]


def prix_par_defaut() -> dict[str, dict]:
    return {code: {"libelle": lib, "unite": u, "prix": px} for code, (lib, u, px) in PRIX_DEFAUT.items()}


def calculer(
    programme: Programme,
    impl: ResultatImplantation,
    structure: ResultatStructure,
    toiture: ResultatToiture,
    elec: ResultatElectricite,
    solaire: ResultatSolaire,
    prix: dict[str, dict] | None = None,
) -> ResultatMetre:
    p = programme
    prix = prix or prix_par_defaut()
    lignes: list[Ligne] = []
    manquants: list[str] = []
    q: dict[str, float] = {}

    def ligne(lot: str, code: str, quantite: float, poste: str | None = None) -> None:
        if quantite <= 0:
            return
        info = prix.get(code)
        if info is None:
            manquants.append(code)
            info = {"libelle": code, "unite": "", "prix": 0.0}
        pu = float(info["prix"])
        lignes.append(Ligne(lot=lot, code=code, poste=poste or info["libelle"], quantite=quantite,
                            unite=info["unite"], prix_unitaire=pu, total=quantite * pu))

    # --- Gros œuvre ------------------------------------------------------------
    sup = ST["profondeur_fouille_sup"]
    v_fouilles = sum(s.longueur * s.largeur * (s.hauteur + sup) for s in structure.semelles)
    v_semelles = sum(s.longueur * s.largeur * s.hauteur for s in structure.semelles)
    cl, ch = ST["section_chainage"]
    ml_ch_h = sum(c.longueur for c in structure.chainages if c.type == "horizontal")
    ml_linteaux = sum(c.longueur for c in structure.chainages if c.type == "linteau")
    v_poteaux = len(structure.poteaux) * ST["poteau"]["section"][0] * ST["poteau"]["section"][1] \
        * structure.hauteur_mur
    v_chainages = ml_ch_h * cl * ch + ml_linteaux * cl * ch + v_poteaux
    v_dallage = structure.dallage["volume_beton"]
    v_dalle_toit = toiture.dalle_volume
    v_beton_total = v_semelles + v_chainages + v_dallage + v_dalle_toit
    q.update(fouilles_m3=v_fouilles, beton_semelles_m3=v_semelles, beton_chainages_m3=v_chainages,
             beton_dallage_m3=v_dallage, beton_total_m3=v_beton_total)

    hauteur_maconnerie = p.hauteur_sous_plafond
    par_mur = {m.id: m for m in impl.murs}
    s_ouv: Counter = Counter()
    for o in impl.ouvertures:
        ext = par_mur[o.mur_id].type != "cloison"
        s_ouv["ext" if ext else "int"] += o.largeur * min(o.hauteur, hauteur_maconnerie)
    s_ext = sum(m.longueur for m in impl.murs if m.type != "cloison") * hauteur_maconnerie - s_ouv["ext"]
    s_int = sum(m.longueur for m in impl.murs if m.type == "cloison") * hauteur_maconnerie - s_ouv["int"]
    blocs_ext = math.ceil(s_ext * M["blocs_par_m2"] * (1 + M["pertes_blocs"]))
    blocs_int = math.ceil(s_int * M["blocs_par_m2"] * (1 + M["pertes_blocs"]))
    v_mortier = (s_ext + s_int) * M["mortier_par_m2_mur"]
    q.update(murs_ext_m2=s_ext, cloisons_m2=s_int, blocs_ext=blocs_ext, blocs_int=blocs_int)

    acier = v_semelles * M["ratio_acier_semelles"] + (v_chainages + v_dalle_toit) * M["ratio_acier_chainages"]
    v_ciment = v_beton_total + v_mortier
    sacs = math.ceil(v_ciment * M["dosage_ciment"] / M["sac_ciment"])
    sable = v_beton_total * M["sable_par_m3_beton"] + v_mortier
    gravier = v_beton_total * M["gravier_par_m3_beton"]

    go = "Gros œuvre"
    ligne(go, "terrassement", v_fouilles)
    ligne(go, "beton_fondation", v_semelles)
    ligne(go, "beton_arme", v_chainages + v_dalle_toit)
    ligne(go, "acier", acier)
    ligne(go, "ciment", sacs)
    ligne(go, "sable", sable)
    ligne(go, "gravier", gravier)
    ligne(go, "blocs_20", blocs_ext, f"Blocs de maçonnerie — murs extérieurs ({p.maconnerie})")
    ligne(go, "blocs_10", blocs_int)
    ligne(go, "mortier", v_mortier)
    ligne(go, "enduit", 2 * (s_ext + s_int))
    ligne(go, "dallage", structure.dallage["surface"])

    # --- Toiture ----------------------------------------------------------------
    to = "Toiture"
    if p.toiture == "terrasse":
        ligne(to, "etancheite", toiture.surface)
        ligne(to, "acrotere", toiture.acrotere_ml)
    else:
        ligne(to, "charpente", toiture.charpente_ml)
        ligne(to, f"couverture_{p.couverture.replace(' ', '_')}", toiture.surface)
    ligne(to, "gouttiere", toiture.gouttieres)
    ligne(to, "descente", toiture.descentes)

    # --- Menuiseries ------------------------------------------------------------
    me = "Menuiseries"
    ouv = Counter()
    for o in impl.ouvertures:
        if o.type == "porte":
            ouv["porte_entree" if o.style == "entree" else "porte_garage" if o.style == "basculante"
                else "porte_interieure"] += 1
        elif o.type in ("fenetre", "placard"):
            ouv[o.type] += 1
    for code in ("porte_entree", "porte_interieure", "porte_garage", "fenetre", "placard"):
        ligne(me, code, ouv[code])

    # --- Finitions --------------------------------------------------------------
    fi = "Finitions"
    s_sols = sum(pc.surface_nette for pc in impl.pieces if pc.type not in ("garage",))
    ligne(fi, "carrelage", s_sols * (1 + M["pertes_carrelage"]))
    s_plafonds = sum(pc.surface_nette for pc in impl.pieces if not pc.exterieure)
    ligne(fi, "peinture", 2 * (s_ext + s_int) + s_plafonds,
          f"Peinture {M['couches_peinture']} couches (murs et plafonds)")

    # --- Électricité ------------------------------------------------------------
    el = "Électricité"
    cond = normes.ELECTRICITE["conducteurs_par_cable"]
    par_section: Counter = Counter()
    for c in elec.circuits:
        par_section[c.s] += c.l * cond
    codes_cables = {1.5: "cable_1_5", 2.5: "cable_2_5", 4.0: "cable_4", 6.0: "cable_6", 10.0: "cable_10",
                    16.0: "cable_16"}
    for s in sorted(par_section):
        ligne(el, codes_cables[s], par_section[s])
    ligne(el, "disjoncteur", len(elec.circuits))
    ligne(el, "interrupteur_diff_a", sum(1 for d in elec.differentiels if d.type == "A"))
    ligne(el, "interrupteur_diff_ac", sum(1 for d in elec.differentiels if d.type == "AC"))
    ligne(el, "disjoncteur_branchement", 1)
    ligne(el, "tableau", 1)
    types = Counter(pt.type for pt in elec.points)
    ligne(el, "prise", types["prise"] + types["prise_specialisee"])
    ligne(el, "interrupteur", types["interrupteur"])
    ligne(el, "luminaire", types["lumiere"])

    # --- Solaire ----------------------------------------------------------------
    if solaire.demande:
        so = "Kit solaire"
        ligne(so, "onduleur", solaire.onduleur_kva)
        ligne(so, "batteries", solaire.batteries_kwh)
        ligne(so, "panneaux", solaire.panneaux_kwc)

    total = sum(lg.total for lg in lignes)
    devise = next(iter(prix.values()), {}).get("devise", "USD")
    ctl = [Controle(id="METRE-PRIX", module=MODULE, niveau="avertissement", titre="Prix indicatifs",
                    detail=f"Prix unitaires {MENTION} ; faire relever les prix locaux avant tout engagement.",
                    reference_norme=REF)]
    if p.devise != devise:
        ctl.append(Controle(id="METRE-DEVISE", module=MODULE, niveau="avertissement", titre="Devise",
                            detail=f"Le programme demande « {p.devise} » mais la table des prix est en {devise} ; "
                                   "aucune conversion n'est appliquée.", reference_norme=REF))
    if manquants:
        ctl.append(Controle(id="METRE-PRIX-MANQUANTS", module=MODULE, niveau="avertissement",
                            titre="Prix manquants", detail="Postes sans prix : " + ", ".join(sorted(set(manquants))),
                            reference_norme=REF))

    def h(lib, val):
        return Hypothese(module=MODULE, libelle=lib, valeur=val, source=REF)

    hyp = [
        h("Fouilles", f"longueur × B × (h + {fmt(sup)} m), longueurs à l'axe des murs"),
        h("Acier", f"{fmt(M['ratio_acier_semelles'], 0)} kg/m³ en semelles, {fmt(M['ratio_acier_chainages'], 0)} kg/m³ "
          "en chaînages, poteaux, linteaux et dalle"),
        h("Ciment", f"{fmt(M['dosage_ciment'], 0)} kg/m³ de béton et de mortier, sacs de {fmt(M['sac_ciment'], 0)} kg"),
        h("Granulats", f"sable {fmt(M['sable_par_m3_beton'], 1)} m³ et gravier {fmt(M['gravier_par_m3_beton'], 1)} m³ "
          "par m³ de béton"),
        h("Maçonnerie", f"hauteur {fmt(hauteur_maconnerie)} m (sous chaînage), ouvertures déduites, "
          f"{fmt(M['blocs_par_m2'], 1)} blocs/m² + {round(M['pertes_blocs'] * 100)} % de pertes"),
        h("Mortier", f"{fmt(M['mortier_par_m2_mur'])} m³ par m² de maçonnerie"),
        h("Carrelage", f"surfaces nettes hors garage + {round(M['pertes_carrelage'] * 100)} %"),
        h("Câbles", f"longueur de circuit × {cond} conducteurs"),
        h("Prix", f"{MENTION} (devise {devise})"),
    ]
    return ResultatMetre(lignes=lignes, total=total, devise=devise, mention_prix=MENTION, quantites=q,
                         controles=ctl, hypotheses=hyp)
