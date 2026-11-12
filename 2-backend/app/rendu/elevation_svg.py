"""Élévations SVG (façade principale, façade latérale) dessinées à partir des volumes de la maison.

Mêmes volumes que le modèle 3D (`volumes.construire`) : les deux vues ne peuvent pas se contredire.
Unités du SVG : 1 unité = 1 cm réel (échelle 1:100 à l'impression, 1 m = 1 cm papier).
Projection orthogonale, algorithme du peintre : les volumes sont dessinés du plus lointain au plus proche.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from app.moteurs import normes
from app.moteurs.chaine import Resultats
from app.moteurs.programme import Programme
from app.rendu import volumes

E = normes.ELEVATION
S = 100.0
VUES = ("facade", "pignon")
TITRES = {"facade": "Façade principale", "pignon": "Façade latérale gauche"}

STYLE = """
.fond{fill:var(--plan-fond,#ffffff)}
.trait{stroke:var(--plan-trait,#27313d);stroke-width:1.2;stroke-linejoin:round}
.trait-fin{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:0.8}
.e-mur{fill:var(--el-mur,#ece6da)}
.e-chainage{fill:var(--el-chainage,#c9c3b7)}
.e-toit{fill:var(--el-toit,#b4543a)}
.e-toit-v{fill:var(--el-toit-v,#9d8f84)}
.e-beton{fill:var(--el-beton,#cfd2d6)}
.e-vitre{fill:var(--el-vitre,#bcd8ea)}
.e-porte{fill:var(--el-porte,#8a6a4a)}
.e-bois{fill:var(--el-bois,#a78a68)}
.e-terrain{fill:url(#terrain)}
.terrain-ligne{stroke:var(--plan-trait,#27313d);stroke-width:2}
.hachure-sol{stroke:var(--plan-trait,#27313d);stroke-width:0.7;opacity:.55}
.tirets{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:0.9;stroke-dasharray:8 5}
.niveau{fill:none;stroke:var(--plan-cote,#1f5fae);stroke-width:0.7;stroke-dasharray:14 6}
.cote-ligne{fill:none;stroke:var(--plan-cote,#1f5fae);stroke-width:0.9}
.cote-plein{fill:var(--plan-cote,#1f5fae)}
.cote-texte{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:var(--plan-cote,#1f5fae)}
.titre{font-family:'IBM Plex Sans Condensed','Arial Narrow',sans-serif;font-weight:600;fill:var(--plan-texte,#16202c)}
.note{font-family:'IBM Plex Sans Condensed','Arial Narrow',sans-serif;fill:var(--plan-texte,#16202c)}
"""

CLASSES = {"mur_ext": "e-mur", "chainage": "e-chainage", "vitre": "e-vitre", "porte": "e-porte",
           "poteau_veranda": "e-bois", "poutre_veranda": "e-bois", "acrotere": "e-mur", "dalle_toiture": "e-beton",
           "dalle_veranda": "e-beton", "toit": "e-toit", "toit_veranda": "e-toit-v", "pignon": "e-mur"}
IGNORES = {"mur_int", "semelle", "soubassement", "dalle"}


def _fr(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def _niveau(z: float) -> str:
    if abs(z) < 0.005:
        return "±0,00"
    return ("+" if z > 0 else "-") + _fr(abs(z))


def _n(v: float) -> str:
    s = f"{v:.1f}"
    return "0.0" if s == "-0.0" else s


def _proj(vue: str, x: float, y: float) -> float:
    """Abscisse écran (m) d'un point du plan : façade = x ; façade gauche, vue depuis l'ouest = -y."""
    return x if vue == "facade" else -y


def _elements(volumes_: dict, vue: str) -> list[tuple[float, str, str]]:
    """Éléments à dessiner : (proximité, classe, SVG), du plus lointain au plus proche."""
    out: list[tuple[float, str, str]] = []
    for b in volumes_["boites"]:
        t = b["t"]
        if t in IGNORES:
            continue
        if vue == "facade":
            u0, u1, proche = b["x"], b["x"] + b["dx"], b["y"] + b["dy"]
        else:
            u0, u1, proche = -(b["y"] + b["dy"]), -b["y"], -b["x"]
        z0, z1 = b["z"], b["z"] + b["dz"]
        classe = CLASSES.get(t, "e-mur")
        x, y, w, h = u0 * S, -z1 * S, (u1 - u0) * S, (z1 - z0) * S
        svg = f'<rect class="{classe} trait" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}"/>'
        if t == "vitre" and w > 90:
            cx = x + w / 2
            svg += f'<line class="trait-fin" x1="{_n(cx)}" y1="{_n(y)}" x2="{_n(cx)}" y2="{_n(y + h)}"/>'
        if t == "porte" and h > 150 and w < 150:
            svg += f'<circle class="trait-fin" cx="{_n(x + w - 10)}" cy="{_n(y + h * 0.55)}" r="2.5"/>'
        out.append((proche, t, svg))
    for f in volumes_["faces"]:
        pts = [(_proj(vue, p[0], p[1]) * S, -p[2] * S) for p in f["pts"]]
        if vue == "facade":
            proche = max(p[1] for p in f["pts"])
        else:
            proche = -min(p[0] for p in f["pts"])
        # une face vue par la tranche (pignon vu de côté) est un trait : inutile de la dessiner
        if max(p[0] for p in pts) - min(p[0] for p in pts) < 1.0:
            continue
        chemin = " ".join(f"{_n(a)},{_n(b)}" for a, b in pts)
        out.append((proche, f["t"], f'<polygon class="{CLASSES.get(f["t"], "e-mur")} trait" points="{chemin}"/>'))
    # tri stable : plus lointain d'abord ; à proximité égale, murs avant ouvrants et toitures
    ordre = {"mur_ext": 0, "pignon": 0, "chainage": 1, "vitre": 2, "porte": 2, "toit": 3}
    out.sort(key=lambda e: (round(e[0], 3), ordre.get(e[1], 1)))
    return out


def _etendue(volumes_: dict, vue: str) -> tuple[float, float]:
    us: list[float] = []
    for b in volumes_["boites"]:
        if b["t"] in ("mur_ext", "poteau_veranda", "dalle_veranda"):
            if vue == "facade":
                us += [b["x"], b["x"] + b["dx"]]
            else:
                us += [-(b["y"] + b["dy"]), -b["y"]]
    return min(us), max(us)


def rendre_elevation(res: Resultats, prog: Programme, vue: str = "facade") -> str:
    if vue not in VUES:
        raise ValueError(f"vue inconnue : {vue}")
    v = volumes.construire(res, prog)
    niv = v["niveaux"]
    u_min, u_max = _etendue(v, vue)
    marge = E["terrain_marge_vue"]
    x0, x1 = (u_min - marge) * S, (u_max + marge) * S
    z_bas = niv["assise"] - 0.35
    haut = niv["haut"]

    corps: list[str] = []
    # Terrain en coupe (hachures) et assise des semelles en tirets
    corps.append(f'<rect class="e-terrain" x="{_n(x0)}" y="{_n(-niv["terrain"] * S)}" width="{_n(x1 - x0)}" '
                 f'height="{_n((niv["terrain"] - z_bas) * S)}"/>')
    for b in v["boites"]:
        if b["t"] != "semelle":
            continue
        if vue == "facade":
            a0, a1 = b["x"], b["x"] + b["dx"]
        else:
            a0, a1 = -(b["y"] + b["dy"]), -b["y"]
        corps.append(f'<rect class="tirets" x="{_n(a0 * S)}" y="{_n(-(b["z"] + b["dz"]) * S)}" '
                     f'width="{_n((a1 - a0) * S)}" height="{_n(b["dz"] * S)}"/>')
    for _, _, svg in _elements(v, vue):
        corps.append(svg)
    corps.append(f'<line class="terrain-ligne" x1="{_n(x0)}" y1="{_n(-niv["terrain"] * S)}" x2="{_n(x1)}" '
                 f'y2="{_n(-niv["terrain"] * S)}"/>')

    # Niveaux (à gauche) et cotes d'ensemble
    marge_g = 500.0
    niveaux = [("assise des semelles", niv["assise"]), ("terrain naturel", niv["terrain"]),
               ("plancher fini", 0.0), ("haut des murs", niv["haut_mur"])]
    if niv["haut"] - niv["haut_mur"] > 0.15:
        niveaux.append(("faîtage" if v["toiture"]["type"] != "terrasse" else "haut d'acrotère", niv["haut"]))
    cotes: list[str] = []
    for nom, z in niveaux:
        y = -z * S
        # sous le trait pour les niveaux enterrés : « plancher fini » (±0,00) et « terrain naturel » (-0,20) sont à 20 cm
        decalage = 36 if z < 0 else -6
        cotes.append(f'<line class="niveau" x1="{_n(x0 - marge_g)}" y1="{_n(y)}" x2="{_n(x1)}" y2="{_n(y)}"/>')
        cotes.append(f'<polygon class="cote-plein" points="{_n(x0 - marge_g + 14)},{_n(y)} {_n(x0 - marge_g + 26)},'
                     f'{_n(y - 10)} {_n(x0 - marge_g + 2)},{_n(y - 10)}"/>')
        cotes.append(f'<text class="cote-texte" x="{_n(x0 - marge_g + 50)}" y="{_n(y + decalage)}" font-size="38">'
                     f'{_niveau(z)} {escape(nom)}</text>')
    # Cote de largeur hors-tout
    yc = -z_bas * S + 50
    cotes.append(f'<line class="cote-ligne" x1="{_n(u_min * S)}" y1="{_n(yc)}" x2="{_n(u_max * S)}" y2="{_n(yc)}"/>')
    for u in (u_min, u_max):
        cotes.append(f'<line class="cote-ligne" x1="{_n(u * S)}" y1="{_n(yc - 8)}" x2="{_n(u * S)}" y2="{_n(yc + 8)}"/>')
    largeur = u_max - u_min
    cotes.append(f'<text class="cote-texte" x="{_n((u_min + u_max) / 2 * S)}" y="{_n(yc + 34)}" font-size="36" '
                 f'text-anchor="middle">{_fr(largeur)}</text>')

    # Cadre
    gauche = x0 - marge_g - 10
    droite = x1 + 20
    haut_svg = -(haut + 0.6) * S - 60
    bas_svg = yc + 100
    largeur_vb, hauteur_vb = droite - gauche, bas_svg - haut_svg
    titre = (f'<text class="titre" x="{_n(gauche + 10)}" y="{_n(haut_svg + 60)}" font-size="56">'
             f'{TITRES[vue]}</text>'
             f'<text class="note" x="{_n(droite - 10)}" y="{_n(bas_svg - 12)}" font-size="28" text-anchor="end">'
             f'Échelle 1:100 · cotes de niveau en mètres · élévation indicative, non contractuelle</text>')
    defs = ('<defs><pattern id="terrain" width="14" height="14" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><line class="hachure-sol" x1="0" y1="0" x2="0" y2="14"/></pattern></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_n(gauche)} {_n(haut_svg)} {_n(largeur_vb)} '
            f'{_n(hauteur_vb)}" width="{_n(largeur_vb / 10)}mm" height="{_n(hauteur_vb / 10)}mm" role="img" '
            f'class="elevation-technique"><title>{TITRES[vue]} — {escape(prog.nom)}</title>'
            f'<style>{STYLE}</style>{defs}'
            f'<rect class="fond" x="{_n(gauche)}" y="{_n(haut_svg)}" width="{_n(largeur_vb)}" '
            f'height="{_n(hauteur_vb)}"/>{"".join(corps)}{"".join(cotes)}{titre}</svg>')
