"""Images de présentation : contrôle de l'image envoyée et mention « non contractuelle » (Pillow)."""
from __future__ import annotations

import base64
import binascii
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TAILLE_MAX_OCTETS = 12 * 1024 * 1024
COTE_MAX_PX = 4096
# IBM Plex Mono (licence OFL, voir polices/) : la police par défaut de Pillow n'a pas les accents
POLICE = Path(__file__).parent / "polices" / "IBMPlexMono-Regular.ttf"
MENTION = "Image de présentation — non contractuelle. Cotes et quantités : voir plan technique"


class ImageInvalide(ValueError):
    pass


def lire_png_base64(donnees: str) -> tuple[str, tuple[int, int]]:
    """Accepte « data:image/png;base64,… » ou du base64 brut. Renvoie (base64 propre, (largeur, hauteur))."""
    brut = donnees.split(",", 1)[1] if donnees.startswith("data:") else donnees
    brut = "".join(brut.split())
    if len(brut) * 3 // 4 > TAILLE_MAX_OCTETS:
        raise ImageInvalide("Image trop lourde (12 Mo au maximum).")
    try:
        octets = base64.b64decode(brut, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ImageInvalide("Image illisible : base64 invalide.") from e
    if not octets.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ImageInvalide("L'image du plan doit être au format PNG.")
    try:
        with Image.open(io.BytesIO(octets)) as im:
            im.verify()
            taille = im.size
    except Exception as e:
        raise ImageInvalide("Image PNG illisible.") from e
    if max(taille) > COTE_MAX_PX or min(taille) < 64:
        raise ImageInvalide(f"Dimensions de l'image hors limites ({taille[0]} × {taille[1]} px).")
    return brut, taille


def ajouter_mention(octets: bytes, mention: str = MENTION) -> bytes:
    """Ajoute un bandeau en bas de l'image avec la mention obligatoire ; renvoie un JPEG."""
    with Image.open(io.BytesIO(octets)) as source:
        im = source.convert("RGB")
    l, h = im.size
    taille_police = max(12, round(l / 70))
    police = ImageFont.truetype(str(POLICE), taille_police)
    marge = round(taille_police * 0.6)
    mesure = ImageDraw.Draw(im)
    # La mention est obligatoire : elle passe à la ligne plutôt que d'être tronquée
    lignes: list[str] = []
    for mot in mention.split():
        essai = f"{lignes[-1]} {mot}" if lignes else mot
        if lignes and mesure.textlength(essai, font=police) <= l - 2 * marge:
            lignes[-1] = essai
        else:
            lignes.append(mot)
    interligne = round(taille_police * 1.25)
    bandeau = interligne * len(lignes) + 2 * marge
    sortie = Image.new("RGB", (l, h + bandeau), (22, 32, 44))
    sortie.paste(im, (0, 0))
    dessin = ImageDraw.Draw(sortie)
    for i, ligne in enumerate(lignes):
        dessin.text((marge, h + marge + i * interligne), ligne, font=police, fill=(255, 255, 255))
    tampon = io.BytesIO()
    sortie.save(tampon, format="JPEG", quality=88, optimize=True)
    return tampon.getvalue()
