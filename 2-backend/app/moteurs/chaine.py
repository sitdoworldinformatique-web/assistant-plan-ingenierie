"""Chaîne de calcul complète : Programme → tous les moteurs → contrôles agrégés (fonction pure)."""
from __future__ import annotations

from pydantic import BaseModel

from app.moteurs import electricite, implantation, metre, regles, solaire, structure, toiture
from app.moteurs.commun import Controle, Hypothese
from app.moteurs.normes import VERSION_MOTEURS
from app.moteurs.programme import Programme


class Resultats(BaseModel):
    implantation: implantation.ResultatImplantation
    electricite: electricite.ResultatElectricite
    structure: structure.ResultatStructure
    toiture: toiture.ResultatToiture
    solaire: solaire.ResultatSolaire
    metre: metre.ResultatMetre
    controles: list[Controle]
    hypotheses: list[Hypothese]
    statut: str
    statuts_modules: dict[str, str]
    version_moteurs: str


def calculer(programme: Programme, prix: dict[str, dict] | None = None) -> Resultats:
    impl = implantation.calculer(programme)
    elec = electricite.calculer(impl, programme)
    struc = structure.calculer(impl, programme)
    toit = toiture.calculer(impl, programme)
    sol = solaire.calculer(elec, programme)
    met = metre.calculer(programme, impl, struc, toit, elec, sol, prix)
    modules = (impl, elec, struc, toit, sol, met)
    controles, statut, par_module = regles.agreger(*(m.controles for m in modules))
    hypotheses = [h for m in modules for h in m.hypotheses]
    return Resultats(implantation=impl, electricite=elec, structure=struc, toiture=toit, solaire=sol, metre=met,
                     controles=controles, hypotheses=hypotheses, statut=statut, statuts_modules=par_module,
                     version_moteurs=VERSION_MOTEURS)
