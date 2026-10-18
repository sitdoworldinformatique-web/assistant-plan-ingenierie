"""Rendu du plan technique en SVG, façon plan d'architecte à l'échelle 1:100 (CdC § 6.2).

Unités du SVG : 1 unité = 1 cm réel. À l'échelle 1:100, 1 m réel = 1 cm papier, donc
les attributs width/height en mm valent viewBox / 10.

Technique : l'emprise est remplie de la couleur des murs, puis chaque pièce est « creusée »
avec la couleur du sol ; les murs apparaissent avec des jonctions propres. Les murs extérieurs
sont hachurés à 45°. Toutes les couleurs passent par des variables CSS (thème clair et sombre).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape

from app.moteurs.implantation import EPS, Ouverture, ResultatImplantation

S = 100.0  # unités SVG par mètre
CALQUES = ("murs", "textes", "cotes", "mobilier", "elec", "structure", "annotations")
CALQUES_DEFAUT = ("murs", "textes", "cotes", "annotations")

# Tailles en unités SVG (cm réels ; 10 unités = 1 mm papier à 1:100)
T_NOM, T_SURF, T_DIM, T_COTE, T_CART = 26.0, 22.0, 17.0, 18.0, 22.0
FACTEUR_POLICE = {"cond": 0.52, "mono": 0.61, "sans": 0.56}

STYLE = """
.fond{fill:var(--plan-fond,#ffffff)}
.mur{fill:var(--plan-mur,#27313d)}
.sol{fill:var(--plan-sol,#ffffff)}
.piece{fill:var(--plan-sol,#ffffff);stroke:var(--plan-trait,#27313d);stroke-width:1.2}
.trait{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:1.2}
.trait-fin{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:0.8}
.trait-fort{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:2.4}
.tirets{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:0.9;stroke-dasharray:8 5}
.hachure{fill:url(#hachure)}
.hachure-ligne{stroke:var(--plan-mur,#27313d);stroke-width:1}
.vitrage{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:0.9}
.etiquette{font-family:'IBM Plex Sans Condensed','Arial Narrow',sans-serif;fill:var(--plan-texte,#16202c)}
.etiquette-nom{font-weight:600}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace}
.cote-ligne{fill:none;stroke:var(--plan-cote,#1f5fae);stroke-width:0.9}
.cote-texte{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:var(--plan-cote,#1f5fae)}
.elec{fill:none;stroke:var(--plan-elec,#c0392b);stroke-width:1.4}
.elec-plein{fill:var(--plan-elec,#c0392b);stroke:none}
.elec-texte{font-family:'IBM Plex Mono',ui-monospace,monospace;fill:var(--plan-elec,#c0392b)}
.structure{fill:none;stroke:var(--plan-structure,#7a4fbf);stroke-width:1.2;stroke-dasharray:6 4}
.structure-plein{fill:var(--plan-structure,#7a4fbf);stroke:none}
.annot{fill:none;stroke:var(--plan-trait,#27313d);stroke-width:1.2}
.annot-plein{fill:var(--plan-trait,#27313d)}
.annot-texte{font-family:'IBM Plex Sans Condensed','Arial Narrow',sans-serif;fill:var(--plan-texte,#16202c)}
"""


def _n(v: float) -> str:
    """Coordonnée SVG (m → cm), une décimale, sans « -0.0 »."""
    s = f"{v * S:.1f}"
    return "0.0" if s == "-0.0" else s


def _u(v: float) -> str:
    s = f"{v:.1f}"
    return "0.0" if s == "-0.0" else s


def fr(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def largeur_texte(texte: str, taille: float, police: str = "cond") -> float:
    """Largeur estimée d'un texte, en unités SVG."""
    return len(texte) * taille * FACTEUR_POLICE[police]


@dataclass
class Boite:
    x: float
    y: float
    l: float
    h: float

    def chevauche(self, o: "Boite") -> bool:
        return self.x < o.x + o.l and o.x < self.x + self.l and self.y < o.y + o.h and o.y < self.y + self.h

    def dans(self, o: "Boite") -> bool:
        return self.x >= o.x - EPS and self.y >= o.y - EPS and self.x + self.l <= o.x + o.l + EPS \
            and self.y + self.h <= o.y + o.h + EPS


@dataclass
class Etiquette:
    piece_id: str
    lignes: list[tuple[str, float, str, str]]  # (texte, taille, police, classes)
    cx: float  # centre, en m
    cy: float
    rotation: bool
    echelle: float
    boite: Boite  # en m


# ---------------------------------------------------------------------------
# Géométrie utilitaire
# ---------------------------------------------------------------------------


def _decaler_contour(contour: list[tuple[float, float]], d: float) -> list[tuple[float, float]]:
    """Décale un polygone orthogonal (sens horaire à l'écran, y vers le bas) de d vers l'extérieur."""
    n = len(contour)
    lignes = []
    for i in range(n):
        (x1, y1), (x2, y2) = contour[i], contour[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        long_ = math.hypot(dx, dy)
        nx, ny = dy / long_, -dx / long_  # normale extérieure pour un parcours horaire à l'écran
        lignes.append(((x1 + nx * d, y1 + ny * d), (dx, dy)))
    pts = []
    for i in range(n):
        (p1, d1), (p2, d2) = lignes[i - 1], lignes[i]
        det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
        t = ((p2[0] - p1[0]) * (-d2[1]) - (p2[1] - p1[1]) * (-d2[0])) / det
        pts.append((p1[0] + d1[0] * t, p1[1] + d1[1] * t))
    return pts


def _chemin(points: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{_n(x)} {_n(y)}" for x, y in points) + " Z"


def _zones_ouvrants(impl: ResultatImplantation) -> list[tuple[str, Boite]]:
    """Zones balayées par les ouvrants (portes battantes, placards), à garder libres de texte."""
    zones = []
    for o in impl.ouvertures:
        if o.type not in ("porte", "placard") or o.style == "basculante":
            continue
        prof = o.largeur if o.type == "porte" else 0.45
        if o.horizontal:
            y0 = o.y + o.sens * o.epaisseur / 2
            y1 = y0 + o.sens * prof
            zones.append((o.piece_id, Boite(o.x - o.largeur / 2, min(y0, y1), o.largeur, abs(y1 - y0))))
        else:
            x0 = o.x + o.sens * o.epaisseur / 2
            x1 = x0 + o.sens * prof
            zones.append((o.piece_id, Boite(min(x0, x1), o.y - o.largeur / 2, abs(x1 - x0), o.largeur)))
    return zones


def placer_etiquettes(impl: ResultatImplantation, obstacles: list[Boite] | None = None) -> list[Etiquette]:
    """Place nom, surface nette et dimensions de chaque pièce sans chevaucher les ouvrants ni les obstacles."""
    zones = [b for _, b in _zones_ouvrants(impl)] + list(obstacles or [])
    resultat: list[Etiquette] = []
    for pc in impl.pieces:
        n = pc.net
        if pc.type == "placard":
            lignes = [(pc.nom, T_DIM, "cond", "etiquette")]
        else:
            lignes = [
                (pc.nom, T_NOM, "cond", "etiquette etiquette-nom"),
                (f"{fr(pc.surface_nette)} m²", T_SURF, "cond", "etiquette"),
                (f"{fr(n.l)} × {fr(n.p)}", T_DIM, "mono", "etiquette mono"),
            ]
        marge = 0.06
        cadre = Boite(n.x + marge, n.y + marge, n.l - 2 * marge, n.p - 2 * marge)
        choisi = None
        for echelle in (1.0, 0.85, 0.7, 0.6, 0.5):
            lt = max(largeur_texte(t, s * echelle, f) for t, s, f, _ in lignes) / S
            ht = sum(s * echelle * 1.25 for _, s, _, _ in lignes) / S
            for rotation in (False, True):
                bl, bh = (ht, lt) if rotation else (lt, ht)
                if bl > cadre.l or bh > cadre.h:
                    continue
                cx0, cy0 = n.centre
                candidats = []
                for i in range(9):
                    for j in range(9):
                        cx = cadre.x + bl / 2 + (cadre.l - bl) * i / 8
                        cy = cadre.y + bh / 2 + (cadre.h - bh) * j / 8
                        candidats.append(((cx - cx0) ** 2 + (cy - cy0) ** 2, cx, cy))
                for _, cx, cy in sorted(candidats):
                    b = Boite(cx - bl / 2, cy - bh / 2, bl, bh)
                    if not any(b.chevauche(z) for z in zones):
                        choisi = Etiquette(pc.id, lignes, cx, cy, rotation, echelle, b)
                        break
                if choisi:
                    break
            if choisi:
                break
        if choisi is None:  # dernier recours : nom seul, réduit, au centre
            lignes = lignes[:1]
            ech = 0.5
            lt = largeur_texte(lignes[0][0], lignes[0][1] * ech, "cond") / S
            ht = lignes[0][1] * ech * 1.25 / S
            cx, cy = n.centre
            choisi = Etiquette(pc.id, lignes, cx, cy, False, ech, Boite(cx - lt / 2, cy - ht / 2, lt, ht))
        resultat.append(choisi)
        zones.append(choisi.boite)
    return resultat


# ---------------------------------------------------------------------------
# Dessin
# ---------------------------------------------------------------------------


def _texte(x: float, y: float, contenu: str, taille: float, classe: str, ancre: str = "middle",
           rotation: float = 0.0) -> str:
    """x, y en unités SVG."""
    rot = f' transform="rotate({_u(rotation)} {_u(x)} {_u(y)})"' if rotation else ""
    return (f'<text x="{_u(x)}" y="{_u(y)}" font-size="{_u(taille)}" text-anchor="{ancre}" class="{classe}"{rot}>'
            f"{escape(contenu)}</text>")


def _dessiner_ouverture(o: Ouverture) -> list[str]:
    out: list[str] = []
    w, e = o.largeur, o.epaisseur
    if o.horizontal:
        a0, a1 = o.x - w / 2, o.x + w / 2

        def P(t: float, n: float) -> tuple[float, float]:  # t le long du mur, n perpendiculaire (y)
            return (t, o.y + n)
    else:
        a0, a1 = o.y - w / 2, o.y + w / 2

        def P(t: float, n: float) -> tuple[float, float]:
            return (o.x + n, t)

    def ligne(p, q, classe):
        return f'<line x1="{_n(p[0])}" y1="{_n(p[1])}" x2="{_n(q[0])}" y2="{_n(q[1])}" class="{classe}"/>'

    # Percement du mur
    c1, c2 = P(a0, -e / 2 - 0.01), P(a1, e / 2 + 0.01)
    x, y = min(c1[0], c2[0]), min(c1[1], c2[1])
    lx, ly = abs(c2[0] - c1[0]), abs(c2[1] - c1[1])
    out.append(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(lx)}" height="{_n(ly)}" class="sol"/>')
    out.append(ligne(P(a0, -e / 2), P(a0, e / 2), "trait"))
    out.append(ligne(P(a1, -e / 2), P(a1, e / 2), "trait"))

    s = o.sens
    if o.type == "fenetre":
        for k in (-e / 2, 0.0, e / 2):
            out.append(ligne(P(a0, k), P(a1, k), "vitrage"))
    elif o.type == "baie":
        for k in (-e / 2, e / 2):
            out.append(ligne(P(a0, k), P(a1, k), "tirets"))
    elif o.type == "placard":
        mi = (a0 + a1) / 2
        out.append(ligne(P(a0, s * 0.02), P(mi + 0.05, s * 0.02), "trait"))
        out.append(ligne(P(mi - 0.05, s * 0.07), P(a1, s * 0.07), "trait"))
    elif o.style == "basculante":
        out.append(ligne(P(a0, s * e / 2), P(a1, s * e / 2), "trait"))
        out.append(ligne(P(a0, s * (e / 2 + 0.6)), P(a1, s * (e / 2 + 0.6)), "tirets"))
    else:  # porte battante : vantail + arc de 90°
        t_ch = a1 if o.charniere > 0 else a0
        t_lib = a0 if o.charniere > 0 else a1
        face = s * e / 2
        charn = P(t_ch, face)
        bout = P(t_ch, face + s * w)
        jamb = P(t_lib, face)
        out.append(ligne(charn, bout, "trait"))
        ax, ay = bout[0] - charn[0], bout[1] - charn[1]
        bx, by = jamb[0] - charn[0], jamb[1] - charn[1]
        balayage = 1 if ax * by - ay * bx > 0 else 0
        r = _n(w)
        out.append(f'<path d="M{_n(bout[0])} {_n(bout[1])} A{r} {r} 0 0 {balayage} {_n(jamb[0])} {_n(jamb[1])}"'
                   ' class="trait-fin"/>')
    return out


def _dessiner_cotes(impl: ResultatImplantation, y_bas: float, x_gauche: float) -> tuple[list[str], list[Boite]]:
    """Chaînes de cotes extérieures en bas et à gauche. Renvoie les éléments et les boîtes de texte (en m)."""
    out: list[str] = []
    boites: list[Boite] = []
    em = impl.emprise
    pos = {("bas", 1): y_bas + 0.75, ("bas", 2): y_bas + 1.35,
           ("gauche", 1): x_gauche - 0.75, ("gauche", 2): x_gauche - 1.35}
    tick = 0.09
    for k in impl.cotes:
        p = pos[(k.cote, k.chaine)]
        v = k.valeur
        texte = f"{round(v * 100):d}" if v < 0.5 else fr(v)
        lt = largeur_texte(texte, T_COTE, "mono") / S
        hauteur = T_COTE / S
        decal = 0.05
        petit = lt + 0.06 > v
        # Petit segment (épaisseur de mur) : texte placé à côté, du côté du voisin le plus long
        voisins = [q for q in impl.cotes if q.cote == k.cote and q.chaine == k.chaine]
        avant = next((q.valeur for q in voisins if abs(q.fin - k.debut) < EPS), 0.0)
        apres = next((q.valeur for q in voisins if abs(q.debut - k.fin) < EPS), 0.0)
        glisse = (-(lt / 2 + 0.04) if avant > apres else (lt / 2 + 0.04)) if petit else 0.0
        if k.cote == "bas":
            out.append(f'<line x1="{_n(k.debut)}" y1="{_n(p)}" x2="{_n(k.fin)}" y2="{_n(p)}" class="cote-ligne"/>')
            for x in (k.debut, k.fin):
                y0 = em.y_max + 0.12 if k.chaine == 1 else pos[("bas", 1)] + 0.08
                out.append(f'<line x1="{_n(x)}" y1="{_n(y0)}" x2="{_n(x)}" y2="{_n(p + 0.1)}" class="cote-ligne"/>')
                out.append(f'<line x1="{_n(x - tick)}" y1="{_n(p + tick)}" x2="{_n(x + tick)}" y2="{_n(p - tick)}"'
                           ' class="cote-ligne"/>')
            cx = (k.debut if glisse < 0 else k.fin) + glisse if petit else (k.debut + k.fin) / 2
            out.append(_texte(cx * S, (p - decal) * S, texte, T_COTE, "cote-texte"))
            boites.append(Boite(cx - lt / 2, p - decal - hauteur * 0.8, lt, hauteur))
        else:
            out.append(f'<line x1="{_n(p)}" y1="{_n(k.debut)}" x2="{_n(p)}" y2="{_n(k.fin)}" class="cote-ligne"/>')
            for y in (k.debut, k.fin):
                x0 = em.x_min - 0.12 if k.chaine == 1 else pos[("gauche", 1)] - 0.08
                out.append(f'<line x1="{_n(x0)}" y1="{_n(y)}" x2="{_n(p - 0.1)}" y2="{_n(y)}" class="cote-ligne"/>')
                out.append(f'<line x1="{_n(p - tick)}" y1="{_n(y + tick)}" x2="{_n(p + tick)}" y2="{_n(y - tick)}"'
                           ' class="cote-ligne"/>')
            cy = (k.debut if glisse < 0 else k.fin) + glisse if petit else (k.debut + k.fin) / 2
            out.append(_texte((p - decal) * S, cy * S, texte, T_COTE, "cote-texte", rotation=-90))
            boites.append(Boite(p - decal - hauteur * 0.8, cy - lt / 2, hauteur, lt))
    return out, boites


def _symbole_elec(pt: dict) -> list[str]:
    x, y, t = pt["x"], pt["y"], pt["type"]
    r = 0.11
    X, Y = _n(x), _n(y)
    if t == "lumiere":
        d = r * 0.7
        return [f'<circle cx="{X}" cy="{Y}" r="{_n(r)}" class="elec"/>',
                f'<line x1="{_n(x - d)}" y1="{_n(y - d)}" x2="{_n(x + d)}" y2="{_n(y + d)}" class="elec"/>',
                f'<line x1="{_n(x - d)}" y1="{_n(y + d)}" x2="{_n(x + d)}" y2="{_n(y - d)}" class="elec"/>']
    if t in ("prise", "prise_specialisee"):
        # demi-cercle tourné vers la pièce + trait de raccordement au mur
        nx, ny = pt.get("nx", 0.0), pt.get("ny", -1.0)  # normale vers la pièce
        rr = 0.09
        ax, ay = x - ny * rr, y + nx * rr
        bx, by = x + ny * rr, y - nx * rr
        balayage = 1 if (ax - x) * ny - (ay - y) * nx > 0 else 0
        el = [f'<path d="M{_n(ax)} {_n(ay)} A{_n(rr)} {_n(rr)} 0 0 {balayage} {_n(bx)} {_n(by)}" class="elec"/>',
              f'<line x1="{_n(ax)}" y1="{_n(ay)}" x2="{_n(bx)}" y2="{_n(by)}" class="elec"/>']
        if t == "prise_specialisee":
            el.append(f'<circle cx="{_n(x + nx * rr * 0.45)}" cy="{_n(y + ny * rr * 0.45)}" r="{_n(0.025)}"'
                      ' class="elec-plein"/>')
        return el
    if t == "interrupteur":
        return [f'<circle cx="{X}" cy="{Y}" r="{_n(0.05)}" class="elec-plein"/>',
                f'<line x1="{X}" y1="{Y}" x2="{_n(x + 0.12)}" y2="{_n(y - 0.12)}" class="elec"/>']
    if t == "tableau":
        return [f'<rect x="{_n(x - 0.25)}" y="{_n(y - 0.08)}" width="{_n(0.5)}" height="{_n(0.16)}"'
                ' class="elec-plein"/>']
    return []


def rendre_plan(
    impl: ResultatImplantation,
    *,
    nom_projet: str = "Projet",
    date: str = "",
    version: str = "1",
    statut: str = "À valider par un ingénieur",
    calques: list[str] | tuple[str, ...] | None = None,
    elec: dict | None = None,
    structure: dict | None = None,
) -> str:
    """Produit le SVG complet du plan du rez-de-chaussée."""
    actifs = set(calques or CALQUES_DEFAUT)
    em = impl.emprise
    e = em.epaisseur_ext
    ver = next((p for p in impl.pieces if p.type == "veranda"), None)
    y_bas_geom = max(em.y_max, ver.axe.y2 if ver else em.y_max)

    # Cadre général (en m)
    larg_cart, haut_cart = 7.4, 2.5
    x0 = em.x_min - 2.1
    y0 = em.y_min - 2.0
    y_cart = y_bas_geom + 2.0
    x1 = max(em.x_max + 0.8, x0 + 1.0 + 6.5 + 0.6 + larg_cart)
    y1 = y_cart + haut_cart + 0.5
    vb_l, vb_h = (x1 - x0) * S, (y1 - y0) * S

    els: list[str] = []
    els.append(f'<rect x="{_n(x0)}" y="{_n(y0)}" width="{_u(vb_l)}" height="{_u(vb_h)}" class="fond"/>')

    # --- Murs -----------------------------------------------------------------
    murs: list[str] = []
    ext = _decaler_contour(em.contour, e / 2)
    inte = _decaler_contour(em.contour, -e / 2)
    murs.append(f'<path d="{_chemin(ext)}" class="mur"/>')
    anneau = f"{_chemin(ext)} {_chemin(inte)}"
    murs.append(f'<path d="{anneau}" fill-rule="evenodd" class="sol"/>')
    murs.append(f'<path d="{anneau}" fill-rule="evenodd" class="hachure"/>')
    for pc in impl.pieces:
        if pc.exterieure:
            continue
        n = pc.net
        murs.append(f'<rect x="{_n(n.x)}" y="{_n(n.y)}" width="{_n(n.l)}" height="{_n(n.p)}" class="piece"'
                    f' data-piece="{pc.id}"/>')
    murs.append(f'<path d="{_chemin(ext)}" class="trait-fort"/>')
    murs.append(f'<path d="{_chemin(inte)}" class="trait"/>')
    for o in impl.ouvertures:
        murs.append(f'<g class="ouverture ouverture-{o.type}" data-id="{o.id}" data-piece="{o.piece_id}">'
                    + "".join(_dessiner_ouverture(o)) + "</g>")
    if ver:
        a = ver.axe
        murs.append(f'<rect x="{_n(a.x)}" y="{_n(a.y)}" width="{_n(a.l)}" height="{_n(a.p)}" class="tirets"'
                    ' data-piece="VER"/>')
        for px in (a.x + 0.1, a.x2 - 0.1):
            murs.append(f'<rect x="{_n(px - 0.1)}" y="{_n(a.y2 - 0.2)}" width="{_n(0.2)}" height="{_n(0.2)}"'
                        ' class="mur"/>')
    if "murs" in actifs:
        els.append('<g class="calque-murs">' + "".join(murs) + "</g>")

    # --- Électricité (symboles NF) -------------------------------------------
    obstacles: list[Boite] = []
    if elec:
        sym: list[str] = []
        for pt in elec.get("points", []):
            sym.extend(_symbole_elec(pt))
            obstacles.append(Boite(pt["x"] - 0.16, pt["y"] - 0.16, 0.32, 0.32))
        if "elec" in actifs:
            els.append('<g class="calque-elec">' + "".join(sym) + "</g>")

    # --- Structure ------------------------------------------------------------
    if structure and "structure" in actifs:
        st: list[str] = []
        for sem in structure.get("semelles", []):
            b = sem.get("trace")
            if b:
                st.append(f'<rect x="{_n(b[0])}" y="{_n(b[1])}" width="{_n(b[2])}" height="{_n(b[3])}"'
                          ' class="structure"/>')
        for pot in structure.get("poteaux", []):
            c = 0.10
            st.append(f'<rect x="{_n(pot["x"] - c)}" y="{_n(pot["y"] - c)}" width="{_n(2 * c)}" height="{_n(2 * c)}"'
                      ' class="structure-plein"/>')
        els.append('<g class="calque-structure">' + "".join(st) + "</g>")

    # --- Textes des pièces ----------------------------------------------------
    if "textes" in actifs:
        txt: list[str] = []
        for et in placer_etiquettes(impl, obstacles):
            lignes = et.lignes
            hauteurs = [s * et.echelle * 1.25 for _, s, _, _ in lignes]
            total = sum(hauteurs)
            cur = -total / 2
            for (t, s, _, cl), hl in zip(lignes, hauteurs):
                base = cur + hl * 0.8
                cur += hl
                if et.rotation:
                    x, y = et.cx * S + base, et.cy * S
                    txt.append(_texte(x, y, t, s * et.echelle, cl, rotation=-90))
                else:
                    txt.append(_texte(et.cx * S, et.cy * S + base, t, s * et.echelle, cl))
        els.append('<g class="calque-textes">' + "".join(txt) + "</g>")

    # --- Cotes ----------------------------------------------------------------
    if "cotes" in actifs:
        cotes, _ = _dessiner_cotes(impl, y_bas_geom, em.x_min)
        els.append('<g class="calque-cotes">' + "".join(cotes) + "</g>")

    # --- Annotations : nord, échelle, cartouche -------------------------------
    if "annotations" in actifs:
        an: list[str] = []
        nx, ny, r = em.x_max - 0.5, y0 + 1.0, 0.45
        an.append(f'<circle cx="{_n(nx)}" cy="{_n(ny)}" r="{_n(r)}" class="annot"/>')
        an.append(f'<path d="M{_n(nx)} {_n(ny - r * 0.95)} L{_n(nx + 0.16)} {_n(ny + 0.3)} L{_n(nx)} {_n(ny + 0.18)}'
                  f' L{_n(nx - 0.16)} {_n(ny + 0.3)} Z" class="annot-plein"/>')
        an.append(_texte((nx - r - 0.12) * S, (ny + 0.09) * S, "N", 26, "annot-texte etiquette-nom", ancre="end"))
        # Échelle graphique 0–5 m
        ex, ey = x0 + 1.0, y_cart + 0.9
        for i in range(5):
            classe = "annot-plein" if i % 2 == 0 else "annot"
            an.append(f'<rect x="{_n(ex + i)}" y="{_n(ey)}" width="{_n(1.0)}" height="{_n(0.12)}" class="{classe}"/>')
            an.append(_texte((ex + i) * S, (ey + 0.38) * S, str(i), 18, "annot-texte"))
        an.append(_texte((ex + 5) * S, (ey + 0.38) * S, "5 m", 18, "annot-texte"))
        an.append(_texte(ex * S, (ey - 0.18) * S, "Échelle 1:100", 20, "annot-texte", ancre="start"))
        # Cartouche
        cx = x1 - 0.5 - larg_cart
        cy = y_cart
        an.append(f'<rect x="{_n(cx)}" y="{_n(cy)}" width="{_n(larg_cart)}" height="{_n(haut_cart)}" class="annot"/>')
        for k in (0.75, 1.35, 1.9):
            an.append(f'<line x1="{_n(cx)}" y1="{_n(cy + k)}" x2="{_n(cx + larg_cart)}" y2="{_n(cy + k)}"'
                      ' class="trait-fin"/>')
        an.append(f'<line x1="{_n(cx + larg_cart / 2)}" y1="{_n(cy + 1.35)}" x2="{_n(cx + larg_cart / 2)}"'
                  f' y2="{_n(cy + 1.9)}" class="trait-fin"/>')
        disp = (larg_cart - 0.4) * S

        def coupe(t: str, taille: float) -> str:
            while largeur_texte(t, taille) > disp and len(t) > 4:
                t = t[:-2] + "…"
            return t

        an.append(_texte((cx + 0.2) * S, (cy + 0.5) * S, coupe(nom_projet, 30), 30,
                         "annot-texte etiquette-nom", ancre="start"))
        an.append(_texte((cx + 0.2) * S, (cy + 1.13) * S, "Plan du rez-de-chaussée", T_CART, "annot-texte",
                         ancre="start"))
        an.append(_texte((cx + 0.2) * S, (cy + 1.7) * S, "Échelle 1:100", T_CART, "annot-texte", ancre="start"))
        an.append(_texte((cx + larg_cart / 2 + 0.2) * S, (cy + 1.7) * S, f"{date} · v{version}", T_CART,
                         "annot-texte mono", ancre="start"))
        an.append(_texte((cx + 0.2) * S, (cy + 2.3) * S, coupe(f"Statut : {statut}", T_CART), T_CART,
                         "annot-texte etiquette-nom", ancre="start"))
        els.append('<g class="calque-annotations">' + "".join(an) + "</g>")

    defs = ('<defs><pattern id="hachure" patternUnits="userSpaceOnUse" width="9" height="9"'
            ' patternTransform="rotate(45)"><line x1="4.5" y1="0" x2="4.5" y2="9" class="hachure-ligne"/></pattern>'
            "</defs>")
    titre = f"<title>Plan du rez-de-chaussée — {escape(nom_projet)}</title>"
    tete = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_n(x0)} {_n(y0)} {_u(vb_l)} {_u(vb_h)}"'
            f' width="{_u(vb_l / 10)}mm" height="{_u(vb_h / 10)}mm" role="img" class="plan-technique">')
    return tete + titre + f"<style>{STYLE}</style>" + defs + "".join(els) + "</svg>\n"
