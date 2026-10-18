"""Rapport texte de conformité (export rapport.txt)."""
from __future__ import annotations

from app.moteurs.commun import fmt

NIVEAUX = {"ok": "CONFORME", "avertissement": "AVERTISSEMENT", "bloquant": "BLOQUANT"}
STATUTS = {"bloque": "BLOQUÉ", "conforme_avec_reserves": "CONFORME AVEC RÉSERVES", "conforme": "CONFORME"}
MODULES = {"implantation": "Implantation", "electricite": "Électricité", "structure": "Structure",
           "toiture": "Toiture", "solaire": "Secours solaire", "metre": "Métré et devis"}
MENTION = "À valider par un ingénieur qualifié"


def rendre(projet: dict, validations: list[dict]) -> str:
    """`projet` : nom, programme, resultats (dict), empreinte, version_moteurs ; `validations` encore valides."""
    r = projet["resultats"]
    signes = {v["module"]: v for v in validations}
    lignes = [
        "ASSISTANT PLAN INGÉNIERIE — Rapport de conformité",
        f"Projet : {projet['nom']}",
        f"Statut global : {STATUTS[r['statut']]}",
        f"Version des moteurs : {projet['version_moteurs']} · empreinte {projet['empreinte'][:12]}",
        "",
    ]
    for m, libelle in MODULES.items():
        v = signes.get(m)
        signature = (f"signé par {v['nom']}" + (f" (n° {v['numero_ordre']})" if v.get("numero_ordre") else "")
                     + f" le {v['date'][:10]}") if v else MENTION
        lignes.append(f"== {libelle} — {STATUTS[r['statuts_modules'][m]]} — {signature}")
        for c in r["controles"]:
            if c["module"] == m:
                lignes.append(f"  [{NIVEAUX[c['niveau']]}] {c['id']} · {c['titre']} : {c['detail']}")
        lignes.append("")
    lignes.append("HYPOTHÈSES")
    for h in r["hypotheses"]:
        lignes.append(f"  ({MODULES[h['module']]}) {h['libelle']} : {h['valeur']}")
    lignes.append("")
    me = r["metre"]
    lignes.append(f"DEVIS ESTIMATIF : {fmt(me['total'], 2)} {me['devise']} ({me['mention_prix']})")
    if len(signes) < len(MODULES):
        lignes += ["", f"*** {MENTION} : modules non signés — document non contractuel. ***"]
    return "\n".join(lignes) + "\n"
