"""Connecteur Nano Banana (API Gemini « interactions ») : rendus de présentation à partir du plan exact.

Les images produites sont NON CONTRACTUELLES : le backend y ajoute la mention `MENTION`.
API relue sur https://ai.google.dev/gemini-api/docs/nanobanana le 2026-10-18 :
POST {URL_API}, en-tête x-goog-api-key, corps {model, input[], response_format{type: image, …}},
image renvoyée en base64 dans steps[].content[] (blocs type "image").
"""
from __future__ import annotations

import base64
import binascii
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from apiconnect import http
from apiconnect.erreurs import IANonConfiguree, ReponseInvalide

log = logging.getLogger("apiconnect.nano_banana")

URL_API = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODELE_DEFAUT = "gemini-nano-banana-2.1"
MODELES = ("gemini-nano-banana-2.1", "gemini-3-pro-image", "gemini-3.1-flash-lite-image")
DELAI_S = 90.0
MENTION = "Image de présentation — non contractuelle. Cotes et quantités : voir plan technique"
MESSAGE_INDISPONIBLE = "Le service d'images n'a pas répondu, réessayez dans une minute."

STYLES: dict[str, str] = {
    "plan_meuble": ("Plan coloré meublé : vue de dessus orthogonale, sols texturés (carrelage dans les pièces "
                    "d'eau et la cuisine, parquet clair ou carrelage dans les chambres et le séjour), mobilier "
                    "réaliste à l'échelle, ombres douces."),
    "iso_coupe": ("Vue 3D isométrique coupée : la maison sans toit, vue à 45° depuis l'angle avant gauche, "
                  "murs extrudés à hauteur réelle, mobilier, lumière naturelle."),
    "facade": ("Façade principale : rendu photoréaliste de la façade côté rue, à hauteur d'œil, végétation "
               "tropicale sobre, ciel clair."),
    "perspective": ("Perspective extérieure : vue d'ensemble à hauteur d'œil, depuis l'avant et un peu de côté, "
                    "la véranda bien visible, jardin tropical sobre."),
    "realiste": ("Rendu photoréaliste de la maison entière, vue à hauteur d'œil depuis l'avant et un peu de côté, "
                 "enduits, toiture et menuiseries réalistes, jardin tropical sobre, ciel clair, lumière naturelle."),
}
STYLES_MAQUETTE = ("realiste",)  # l'image fournie est une capture de la maquette 3D, pas le plan
LIBELLES_STYLES = {
    "plan_meuble": "Plan coloré meublé",
    "iso_coupe": "Vue 3D isométrique coupée",
    "facade": "Façade principale",
    "perspective": "Perspective extérieure",
    "realiste": "Rendu réaliste (depuis la maquette 3D)",
}

GABARIT_PROMPT = """Rendu de présentation architectural d'une maison individuelle de plain-pied (RDC, climat tropical).

Style demandé : {style}

L'image fournie est le plan technique exact de la maison (murs, portes, fenêtres). Pièces :
{pieces}
{toiture}
Consignes strictes :
- conserver exactement la position et la forme des murs, des portes et des fenêtres de l'image fournie ;
- ne pas ajouter ni supprimer de pièce, ne pas changer les proportions ;
- aucun texte, chiffre, cote, logo ou filigrane inventé dans l'image ;
- style architectural professionnel, lumière naturelle, matériaux adaptés au climat tropical
  (enduits clairs, tôle, carrelage)."""

GABARIT_PROMPT_MAQUETTE = """Rendu photoréaliste d'une maison individuelle de plain-pied (RDC, climat tropical).

Style demandé : {style}

L'image fournie est une capture de la maquette 3D exacte de la maison (volumes, toiture, véranda, portes, fenêtres).
Pièces :
{pieces}
{toiture}
Consignes strictes :
- conserver exactement la forme, les proportions, la toiture, la véranda, les portes et les fenêtres de la maquette ;
- ne pas ajouter ni supprimer de volume, d'étage ou d'ouverture ;
- aucun texte, chiffre, cote, logo ou filigrane inventé dans l'image ;
- matériaux adaptés au climat tropical (enduits clairs, tôle ou tuiles selon la toiture indiquée)."""


@dataclass(frozen=True)
class Rendu:
    image: bytes
    mime_type: str
    prompt: str
    modele: str


def _fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def construire_prompt(style: str, pieces: Iterable[dict], toiture: str | None = None) -> str:
    """`pieces` : dicts {nom, largeur, profondeur[, surface]} en mètres (dimensions nettes)."""
    if style not in STYLES:
        raise ValueError(f"style inconnu : {style}")
    lignes = []
    for p in pieces:
        surface = p.get("surface") or p["largeur"] * p["profondeur"]
        lignes.append(f"- {p['nom']} : {_fmt(p['largeur'])} m × {_fmt(p['profondeur'])} m ({_fmt(surface)} m²)")
    ligne_toit = f"Toiture : {toiture}.\n" if toiture and style in ("facade", "perspective", *STYLES_MAQUETTE) else ""
    gabarit = GABARIT_PROMPT_MAQUETTE if style in STYLES_MAQUETTE else GABARIT_PROMPT
    return gabarit.format(style=STYLES[style], pieces="\n".join(lignes) or "- (non précisé)",
                          toiture=ligne_toit)


def _blocs_image(noeud: Any) -> Iterable[dict]:
    """Parcourt la réponse et renvoie, dans l'ordre, tous les blocs image (formats tolérés)."""
    if isinstance(noeud, dict):
        type_ = noeud.get("type")
        if type_ == "image" and isinstance(noeud.get("data"), str):
            yield {"data": noeud["data"], "mime_type": noeud.get("mime_type") or noeud.get("mimeType")}
        # Ancien format generateContent : parts[].inline_data / inlineData
        for cle in ("inline_data", "inlineData"):
            bloc = noeud.get(cle)
            if isinstance(bloc, dict) and isinstance(bloc.get("data"), str):
                yield {"data": bloc["data"], "mime_type": bloc.get("mime_type") or bloc.get("mimeType")}
        for cle, valeur in noeud.items():
            if cle in ("inline_data", "inlineData") or (type_ == "image" and cle == "data"):
                continue
            yield from _blocs_image(valeur)
    elif isinstance(noeud, list):
        for v in noeud:
            yield from _blocs_image(v)


def extraire_image(reponse: dict) -> tuple[bytes, str]:
    """Renvoie (octets, mime) de la DERNIÈRE image de la réponse (comme `output_image` du SDK)."""
    if not isinstance(reponse, dict):
        raise ReponseInvalide(detail="réponse non objet")
    sortie = reponse.get("output_image")
    if isinstance(sortie, dict) and isinstance(sortie.get("data"), str):
        candidats = [{"data": sortie["data"], "mime_type": sortie.get("mime_type")}]
    elif "steps" in reponse:
        candidats = list(_blocs_image(reponse["steps"]))
    else:  # format inconnu : tout sauf l'entrée éventuellement renvoyée en écho
        candidats = list(_blocs_image({k: v for k, v in reponse.items() if k != "input"}))
    if not candidats:
        raise ReponseInvalide("Le service d'images n'a renvoyé aucune image.", detail="aucun bloc image")
    dernier = candidats[-1]
    try:
        octets = base64.b64decode(dernier["data"], validate=False)
    except (binascii.Error, ValueError) as e:
        raise ReponseInvalide(detail="base64 invalide") from e
    if len(octets) < 16:
        raise ReponseInvalide(detail="image vide")
    mime = dernier.get("mime_type") or ("image/png" if octets.startswith(b"\x89PNG") else "image/jpeg")
    return octets, mime


class ClientNanoBanana:
    def __init__(self, api_key: str = "", modele: str = MODELE_DEFAUT, *, client_http: Any = None,
                 delai_s: float = DELAI_S, url: str = URL_API, dormir=None):
        if not api_key:
            raise IANonConfiguree("Les rendus IA sont désactivés : aucune clé du service d'images n'est configurée.")
        self._cle = api_key
        self.modele = modele or MODELE_DEFAUT
        self._client_http = client_http
        self._delai_s = delai_s
        self._url = url
        self._dormir = dormir

    def __repr__(self) -> str:  # jamais la clé
        return f"ClientNanoBanana(modele={self.modele!r})"

    def generer_rendu(self, image_png_base64: str, style: str, pieces: Iterable[dict],
                      toiture: str | None = None, *, aspect_ratio: str = "16:9", taille: str = "2K") -> Rendu:
        prompt = construire_prompt(style, pieces, toiture)
        corps = {
            "model": self.modele,
            "input": [
                {"type": "text", "text": prompt},
                {"type": "image", "mime_type": "image/png", "data": image_png_base64},
            ],
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect_ratio,
                                "image_size": taille.upper()},
        }
        kwargs = {} if self._dormir is None else {"dormir": self._dormir}
        reponse = http.post_json(self._url, corps, entetes={"x-goog-api-key": self._cle},
                                 delai_s=self._delai_s, client=self._client_http,
                                 message_indisponible=MESSAGE_INDISPONIBLE, **kwargs)
        octets, mime = extraire_image(reponse)
        log.info("rendu %s : %d octets (%s)", style, len(octets), self.modele)
        return Rendu(image=octets, mime_type=mime, prompt=prompt, modele=self.modele)
