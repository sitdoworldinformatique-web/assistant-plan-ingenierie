"""Secours solaire — pré-dimensionnement repris du prototype (CdC § 6.6)."""
from __future__ import annotations

import math

from pydantic import BaseModel

from app.moteurs import normes
from app.moteurs.commun import Controle, Hypothese, fmt
from app.moteurs.electricite import ResultatElectricite
from app.moteurs.programme import Programme

S = normes.SOLAIRE
MODULE = "solaire"
REF = S["reference"]


class ResultatSolaire(BaseModel):
    demande: bool
    charges_essentielles_w: float
    onduleur_kva: float
    batteries_kwh: float
    energie_jour_kwh: float
    panneaux_kwc: float
    controles: list[Controle]
    hypotheses: list[Hypothese]


def calculer(elec: ResultatElectricite, programme: Programme) -> ResultatSolaire:
    p = programme
    p_ecl = sum(c.p for c in elec.circuits if c.cat == "ecl")
    pompe = normes.ELECTRICITE["specialises"]["pompe"]["p"] if "pompe" in p.equipements else 0.0
    p_ess = p_ecl + S["charges_fixes_w"] + pompe
    pas = S["pas_onduleur_kva"]
    onduleur = math.ceil(round(p_ess * S["marge_onduleur"] / 1000 / pas, 9)) * pas
    batteries = p_ess * S["facteur_utilisation"] * p.autonomie_h / 1000 / (S["profondeur_decharge"]
                                                                          * S["rendement_onduleur"])
    e_jour = p_ess * S["facteur_journalier"] * S["heures_jour"] / 1000
    kwc = e_jour / (p.ensoleillement_h * S["ratio_performance"])

    def h(lib, val):
        return Hypothese(module=MODULE, libelle=lib, valeur=val, source=REF)

    hyp = [
        h("Charges essentielles", f"éclairage {fmt(p_ecl, 0)} W + {fmt(S['charges_fixes_w'], 0)} W (réfrigérateur, TV, "
          f"recharges){' + pompe ' + fmt(pompe, 0) + ' W' if pompe else ''}"),
        h("Onduleur", f"P × {fmt(S['marge_onduleur'])}, arrondi au {fmt(pas, 1)} kVA supérieur"),
        h("Batteries", f"P × {fmt(S['facteur_utilisation'], 1)} × {fmt(p.autonomie_h, 1)} h / "
          f"({fmt(S['profondeur_decharge'], 1)} × {fmt(S['rendement_onduleur'], 1)})"),
        h("Énergie journalière", f"P × {fmt(S['facteur_journalier'], 1)} × {fmt(S['heures_jour'], 0)} h"),
        h("Panneaux", f"E / ({fmt(p.ensoleillement_h, 1)} h × {fmt(S['ratio_performance'])})"),
    ]
    ctl = [Controle(id="SOL-PREDIM", module=MODULE, niveau="avertissement" if p.solaire else "ok",
                    titre="Pré-dimensionnement solaire" if p.solaire else "Secours solaire non demandé",
                    detail="Valeurs indicatives à confirmer par un bilan de consommation détaillé." if p.solaire else
                    "Le programme ne prévoit pas de secours solaire.", reference_norme=REF)]
    if not p.solaire:
        return ResultatSolaire(demande=False, charges_essentielles_w=p_ess, onduleur_kva=0, batteries_kwh=0,
                               energie_jour_kwh=0, panneaux_kwc=0, controles=ctl, hypotheses=hyp)
    return ResultatSolaire(demande=True, charges_essentielles_w=p_ess, onduleur_kva=onduleur, batteries_kwh=batteries,
                           energie_jour_kwh=e_jour, panneaux_kwc=kwc, controles=ctl, hypotheses=hyp)
