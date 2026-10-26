"""Commandes en langage naturel : modifier un programme existant, une étape à la fois (fonction pure).

« Ajoute une chambre », « supprime la véranda », « agrandis le séjour de 5 m² », « toiture 4 pans en tuiles »…
Les règles reconnaissent des commandes simples ; l'IA texte, quand elle est configurée, élargit la compréhension
(`orchestrateur.commander`). Dans les deux cas, ce sont les moteurs qui recalculent : rien n'est calculé ici.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.moteurs.programme import _F, _N, Programme, _entier, _extraire, _flottant, _normaliser

LIBELLES = {
    "nom": "Nom", "chambres": "Chambres", "salles_de_bain": "Salles de bain", "wc_separe": "WC séparé",
    "bureau": "Bureau", "garage": "Garage", "veranda": "Véranda", "cuisine_ouverte": "Cuisine ouverte",
    "surface_sejour": "Surface du séjour (m²)", "terrain_largeur": "Largeur du terrain (m)",
    "terrain_profondeur": "Profondeur du terrain (m)", "recul": "Recul (m)",
    "hauteur_sous_plafond": "Hauteur sous plafond (m)", "toiture": "Toiture", "couverture": "Couverture",
    "pente_toiture": "Pente de toiture (%)", "maconnerie": "Maçonnerie", "portance_sol": "Portance du sol (MPa)",
    "portance_mesuree": "Portance mesurée", "clim_chambres": "Climatisation des chambres",
    "clim_sejour": "Climatisation du séjour", "equipements": "Équipements", "resistance_terre": "Résistance de terre (Ω)",
    "solaire": "Solaire", "autonomie_h": "Autonomie (h)", "ensoleillement_h": "Ensoleillement (h/j)",
    "niveaux": "Niveaux", "devise": "Devise",
}
EXEMPLES = ("« ajoute une chambre », « supprime la véranda », « agrandis le séjour de 5 m² », "
            "« toiture 4 pans en tuiles », « terrain 25 x 30 », « résistance de terre 20 ohms »")


@dataclass(frozen=True)
class Changement:
    champ: str
    libelle: str
    avant: object
    apres: object

    def en_dict(self) -> dict:
        return {"champ": self.champ, "libelle": self.libelle, "avant": self.avant, "apres": self.apres}


def _fmt(v: object) -> str:
    if isinstance(v, bool):
        return "oui" if v else "non"
    if v is None:
        return "non renseignée"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or "aucun"
    return str(v)


def decrire(c: Changement) -> str:
    return f"{c.libelle} : {_fmt(c.avant)} → {_fmt(c.apres)}"


def differences(avant: Programme, apres: Programme) -> list[Changement]:
    a, b = avant.model_dump(mode="json"), apres.model_dump(mode="json")
    return [Changement(k, LIBELLES.get(k, k), a[k], b[k]) for k in a if a[k] != b[k] and k != "longueurs_circuits"]


_AJOUTE = r"(?:ajoute[rz]?|rajoute[rz]?|ajoutons)"
_RETIRE = r"(?:supprime[rz]?|enleve[rz]?|retire[rz]?|supprimons|enlevons)"
_ARTICLE = r"(?:(?:le|la|l'|les|un|une|des|du|de la|d')\s?)?"


def _delta(t: str, mot: str, defaut: int = 1) -> int | None:
    """+n pour « ajoute (n) mot », « (n) mot de plus » ; −n pour « supprime (n) mot » ; sinon None."""
    m = re.search(_AJOUTE + r"\s+(?:" + _N + r"\s+)?(?:" + mot + r")", t)
    if m:
        return _entier(m.group(1)) if m.group(1) else defaut
    m = re.search(_N + r"\s+(?:" + mot + r")\s+(?:en plus|de plus|supplementaires?)", t)
    if m:
        return _entier(m.group(1))
    m = re.search(_RETIRE + r"\s+(?:" + _N + r"\s+)?(?:" + mot + r")", t)
    if m:
        return -(_entier(m.group(1)) if m.group(1) else defaut)
    return None


def est_annulation(texte: str) -> bool:
    """« annule », « annule la dernière étape », « reviens en arrière »…"""
    return bool(re.match(r"\s*(?:annule[rz]?|defai[st]|defaire|reviens|revenir|retour en arriere)\b", _normaliser(texte)))


def _surface_relative(t: str, defaut: float) -> float | None:
    """Variation de surface du séjour : « agrandis le séjour de 5 m2 » (+5), « réduis le séjour de 3 m2 » (−3)."""
    m = re.search(r"(agrandi\w*|augmente\w*|elargi\w*|reduis\w*|reduire|diminue\w*|retreci\w*)\s+(?:le |la |l')?(?:sejour|salon)"
                  r"(?:\s+\w+){0,2}?\s*(?:de|d'|a hauteur de)?\s*(?:" + _F + r"\s*m2)?", t)
    if not m:
        return None
    valeur = _flottant(m.group(2)) if m.group(2) else defaut
    return -valeur if re.match(r"redu|dimin|retre", m.group(1)) else valeur


def appliquer(courant: Programme, texte: str, surface_sejour_actuelle: float | None = None
              ) -> tuple[Programme, list[Changement], list[str]]:
    """Applique une commande au programme courant : (nouveau programme, changements, remarques)."""
    t = _normaliser(texte)
    v, remarques = _extraire(texte, commande=True)
    v.pop("nom", None)

    # Variations relatives : elles priment sur la lecture absolue (« ajoute 2 chambres » ≠ « 2 chambres »)
    d = _delta(t, "chambres?")
    if d is not None:
        v["chambres"] = min(8, max(0, courant.chambres + d))
    d = _delta(t, r"salles? (?:de bains?|d'eau)|sdb|douches?")
    if d is not None:
        v["salles_de_bain"] = min(4, max(1, courant.salles_de_bain + d))
    base = surface_sejour_actuelle or courant.surface_sejour or 0.0
    r = _surface_relative(t, 5.0)
    if r is not None:
        v["surface_sejour"] = round(max(12.0, base + r), 1)
        if not re.search(_F + r"\s*m2", t):
            remarques.append("Variation du séjour non précisée : 5 m² retenus.")

    # Pièces et équipements à ajouter ou à retirer
    for cle, motif in (("bureau", "bureau"), ("garage", "garage"), ("veranda", "veranda"), ("solaire", "solaire|panneaux"),
                       ("wc_separe", "wc separes?|toilettes? separees?")):
        if re.search(_RETIRE + r"\s+" + _ARTICLE + r"(?:" + motif + r")", t):
            v[cle] = False
        elif re.search(_AJOUTE + r"\s+" + _ARTICLE + r"(?:" + motif + r")", t):
            v[cle] = True
    if re.search(_RETIRE + r"\s+" + _ARTICLE + r"(?:clim|climatisation|climatiseurs?)", t):
        v["clim_chambres"] = v["clim_sejour"] = False
    elif re.search(_AJOUTE + r"\s+" + _ARTICLE + r"(?:clim|climatisation|climatiseurs?)", t) and not (
            "clim_chambres" in v or "clim_sejour" in v):
        v["clim_chambres"] = v["clim_sejour"] = True

    # Toiture : on ne garde pas une couverture « dalle béton » hors toiture terrasse
    if "toiture" in v and v["toiture"] != "terrasse" and "couverture" not in v and courant.couverture == "dalle beton":
        v["couverture"] = "tole bac acier"
        v.setdefault("pente_toiture", 25)

    m = re.search(r"(?:appelle|renomme)\w*(?: le projet| la maison| le plan)?(?: en| :)?\s+(.{2,80})$", texte.strip(), re.I)
    if m:
        v["nom"] = m.group(1).strip(" .\"«»")

    if not v:
        return courant, [], [f"Commande non comprise. Exemples : {EXEMPLES}."]
    nouveau = Programme(**{**courant.model_dump(), **v})
    return nouveau, differences(courant, nouveau), remarques
