"""Volumes de la maison : source unique de l'élévation SVG et du modèle 3D.

Repère : x vers la droite, y vers le bas du plan (façade principale en y maximal), z vers le haut.
±0,00 = plancher fini ; le terrain naturel est à -0,20 m. Unités : mètres.

Le résultat est un dictionnaire sérialisable en JSON :
- `boites`   : parallélépipèdes alignés sur les axes {t, x, y, z, dx, dy, dz} (z = bas de la boîte) ;
- `faces`    : polygones plans convexes {t, pts[[x, y, z], …]} (toiture, pignons) ;
- `terrain`  : rectangle de terrain {x, y, l, p, z} ;
- `niveaux`  : cotes de niveau ; `hypotheses` : phrases à afficher sous le modèle.
Types : mur_ext, mur_int, chainage, soubassement, semelle, dalle, dalle_veranda, vitre, porte, poteau_veranda,
acrotere, dalle_toiture, toit, toit_veranda, pignon.
"""
from __future__ import annotations

from app.moteurs import normes
from app.moteurs.chaine import Resultats
from app.moteurs.commun import fmt
from app.moteurs.implantation import EPS, Mur, Ouverture
from app.moteurs.programme import Programme

E = normes.ELEVATION
EPAISSEUR_VITRE = 0.03
EPAISSEUR_VANTAIL = 0.05


def _r(v: float) -> float:
    return round(v, 3)


def _boite(t: str, x: float, y: float, z: float, dx: float, dy: float, dz: float) -> dict:
    return {"t": t, "x": _r(x), "y": _r(y), "z": _r(z), "dx": _r(dx), "dy": _r(dy), "dz": _r(dz)}


def _face(t: str, pts: list[tuple[float, float, float]]) -> dict:
    return {"t": t, "pts": [[_r(a), _r(b), _r(c)] for a, b, c in pts]}


def _allege(o: Ouverture, appartient_sdb: bool) -> float:
    if o.type in ("porte", "baie"):
        return 0.0
    if o.hauteur >= E["seuil_porte_fenetre"]:
        return 0.0
    return E["allege_haute"] if (appartient_sdb or o.style == "allege haute") else E["allege_fenetre"]


def _murs(res: Resultats, hm: float) -> list[dict]:
    impl = res.implantation
    sdb = {p.id for p in impl.pieces if p.type == "sdb"}
    boites: list[dict] = []
    for m in impl.murs:
        ext = m.type == "exterieur"
        type_mur = "mur_ext" if ext else "mur_int"
        horiz = m.horizontal
        a, b = (min(m.x1, m.x2), max(m.x1, m.x2)) if horiz else (min(m.y1, m.y2), max(m.y1, m.y2))
        if ext:
            a, b = a - m.epaisseur / 2, b + m.epaisseur / 2
        fixe = m.y1 if horiz else m.x1
        ouv = sorted((o for o in impl.ouvertures if o.mur_id == m.id and o.type != "placard"),
                     key=lambda o: o.x if horiz else o.y)

        def poser(type_: str, s0: float, s1: float, z0: float, z1: float, ep: float | None = None, *,
                  m: Mur = m, horiz: bool = horiz, fixe: float = fixe) -> None:
            if s1 - s0 < EPS or z1 - z0 < EPS:
                return
            ep = m.epaisseur if ep is None else ep
            if horiz:
                boites.append(_boite(type_, s0, fixe - ep / 2, z0, s1 - s0, ep, z1 - z0))
            else:
                boites.append(_boite(type_, fixe - ep / 2, s0, z0, ep, s1 - s0, z1 - z0))

        curseur = a
        for o in ouv:
            c = o.x if horiz else o.y
            s0, s1 = c - o.largeur / 2, c + o.largeur / 2
            z0 = _allege(o, o.piece_id in sdb)
            z1 = min(z0 + o.hauteur, hm)
            poser(type_mur, curseur, s0, 0.0, hm)
            poser(type_mur, s0, s1, 0.0, z0)  # allège
            poser(type_mur, s0, s1, z1, hm)  # linteau
            if o.type == "fenetre":
                poser("vitre", s0, s1, z0, z1, EPAISSEUR_VITRE)
            elif o.type == "porte":
                poser("porte", s0, s1, 0.0, z1, EPAISSEUR_VANTAIL)
            curseur = s1
        poser(type_mur, curseur, b, 0.0, hm)
        if m.porteur:
            poser("chainage", a, b, hm - E["hauteur_chainage"], hm)
    return boites


def _fondations(res: Resultats, base: float) -> list[dict]:
    boites = []
    murs: dict[str, Mur] = {m.id: m for m in res.implantation.murs}
    for s in res.structure.semelles:
        x, y, l_, p = s.trace
        boites.append(_boite("semelle", x, y, base, l_, p, s.hauteur))
        m = murs.get(s.mur_id)
        if m is None:
            continue
        haut = base + s.hauteur
        if m.horizontal:
            a, b = min(m.x1, m.x2), max(m.x1, m.x2)
            if m.type == "exterieur":
                a, b = a - m.epaisseur / 2, b + m.epaisseur / 2
            boites.append(_boite("soubassement", a, m.y1 - m.epaisseur / 2, haut, b - a, m.epaisseur, -haut))
        else:
            a, b = min(m.y1, m.y2), max(m.y1, m.y2)
            if m.type == "exterieur":
                a, b = a - m.epaisseur / 2, b + m.epaisseur / 2
            boites.append(_boite("soubassement", m.x1 - m.epaisseur / 2, a, haut, m.epaisseur, b - a, -haut))
    return boites


def _toit_deux_pans(x0: float, x1: float, y0: float, y1: float, y_mur0: float, y_mur1: float, x_mur0: float,
                    x_mur1: float, hm: float, pente: float, debord: tuple[float, float, float, float]) -> tuple[list, float]:
    """Toiture à deux pans, faîtage selon x. (x0..x1, y0..y1) : emprise de la toiture, débords compris."""
    ym = (y_mur0 + y_mur1) / 2
    z_f = hm + pente * (y_mur1 - y_mur0) / 2
    d_y0, d_y1 = debord[2], debord[3]
    z_e0, z_e1 = hm - pente * d_y0, hm - pente * d_y1
    faces = [
        _face("toit", [(x0, y0, z_e0), (x1, y0, z_e0), (x1, ym, z_f), (x0, ym, z_f)]),
        _face("toit", [(x0, ym, z_f), (x1, ym, z_f), (x1, y1, z_e1), (x0, y1, z_e1)]),
        # pignons : les murs d'extrémité montent jusqu'au rampant
        _face("pignon", [(x_mur0, y_mur0, hm), (x_mur0, y_mur1, hm), (x_mur0, ym, z_f)]),
        _face("pignon", [(x_mur1, y_mur0, hm), (x_mur1, y_mur1, hm), (x_mur1, ym, z_f)]),
    ]
    return faces, z_f


def _toit_quatre_pans(x0: float, x1: float, y0: float, y1: float, hm: float, pente: float,
                      debord: tuple[float, float, float, float]) -> tuple[list, float]:
    """Toiture à quatre pans : même pente sur chaque versant, faîtage selon la plus grande dimension."""
    z_e = hm - pente * sum(debord) / 4  # débord moyen : égout horizontal
    larg, prof = x1 - x0, y1 - y0
    a = min(larg, prof) / 2
    z_f = z_e + pente * a
    c = [(x0, y0, z_e), (x1, y0, z_e), (x1, y1, z_e), (x0, y1, z_e)]
    if larg >= prof:
        ym = y0 + a
        g, dr = (x0 + a, ym, z_f), (x1 - a, ym, z_f)
        faces = [_face("toit", [c[0], c[1], dr, g]), _face("toit", [c[2], c[3], g, dr]),
                 _face("toit", [c[3], c[0], g]), _face("toit", [c[1], c[2], dr])]
    else:
        xm = x0 + a
        h_, b_ = (xm, y0 + a, z_f), (xm, y1 - a, z_f)
        faces = [_face("toit", [c[3], c[0], h_, b_]), _face("toit", [c[1], c[2], b_, h_]),
                 _face("toit", [c[0], c[1], h_]), _face("toit", [c[2], c[3], b_])]
    return faces, z_f


def _toiture(res: Resultats, prog: Programme, hm: float) -> tuple[list[dict], list[dict], float]:
    impl = res.implantation
    e = impl.emprise.epaisseur_ext
    w, d = impl.parametres["largeur_axe"], impl.parametres["profondeur_axe"]
    wg, dj = impl.parametres["largeur_garage"], impl.parametres["profondeur_jour"]
    deb = res.toiture.debord
    pente = res.toiture.pente / 100.0
    boites: list[dict] = []
    faces: list[dict] = []
    z_max = hm
    # (x0, x1, y0, y1) à l'axe des murs, débords par côté (gauche, droite, haut, bas)
    blocs = [((0.0, w, 0.0, d), (deb, deb, deb, deb))]
    if wg:
        blocs.append(((-wg, 0.0, d - dj, d), (deb, 0.0, deb, deb)))
    if prog.toiture == "terrasse":
        ep, ac = E["epaisseur_dalle_terrasse"], E["hauteur_acrotere"]
        for (ax0, ax1, ay0, ay1), _ in blocs:
            boites.append(_boite("dalle_toiture", ax0 - e / 2, ay0 - e / 2, hm, ax1 - ax0 + e, ay1 - ay0 + e, ep))
        z_max = hm + ep + ac
        ex = impl.emprise
        # acrotère sur le contour extérieur (rectangle, ou L avec garage)
        pts = [(ex.x_min, ex.y_min), (ex.x_max, ex.y_min), (ex.x_max, ex.y_max), (ex.x_min, ex.y_max)]
        if wg:
            pts = [(ex.x_min, d - dj - e / 2), (-e / 2 + 0.0, d - dj - e / 2), (-e / 2, ex.y_min), (ex.x_max, ex.y_min),
                   (ex.x_max, ex.y_max), (ex.x_min, ex.y_max)]
        for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
            t = 0.10
            if abs(ya - yb) < EPS:
                boites.append(_boite("acrotere", min(xa, xb), ya - t / 2, hm + ep, abs(xb - xa), t, ac))
            else:
                boites.append(_boite("acrotere", xa - t / 2, min(ya, yb), hm + ep, t, abs(yb - ya), ac))
        return boites, faces, z_max
    for (ax0, ax1, ay0, ay1), (dg, dd, dh, db) in blocs:
        x0, x1 = ax0 - e / 2 - dg, ax1 + e / 2 + dd
        y0, y1 = ay0 - e / 2 - dh, ay1 + e / 2 + db
        if prog.toiture == "2 pans":
            f, zf = _toit_deux_pans(x0, x1, y0, y1, ay0, ay1, ax0 - e / 2, ax1 + e / 2, hm, pente, (dg, dd, dh, db))
        else:
            f, zf = _toit_quatre_pans(x0, x1, y0, y1, hm, pente, (dg, dd, dh, db))
        faces += f
        z_max = max(z_max, zf)
    return boites, faces, z_max


def _veranda(res: Resultats, hm: float) -> tuple[list[dict], list[dict]]:
    impl = res.implantation
    v = next((p for p in impl.pieces if p.type == "veranda"), None)
    if v is None:
        return [], []
    e = impl.emprise.epaisseur_ext
    x0, x1 = v.axe.x, v.axe.x2
    y0, y1 = v.axe.y - e / 2, v.axe.y2
    boites = [_boite("dalle_veranda", x0, y0, -0.10, x1 - x0, y1 - y0, 0.10)]
    h = E["hauteur_veranda"]
    pt = E["poteau_veranda"]
    n = max(1, round((x1 - x0) / E["entraxe_poteaux_veranda"]))
    for i in range(n + 1):
        x = x0 + (x1 - x0 - pt) * i / n
        boites.append(_boite("poteau_veranda", x, y1 - pt, 0.0, pt, pt, h))
    boites.append(_boite("poutre_veranda", x0, y1 - pt, h, x1 - x0, pt, 0.15))
    z_haut = hm - E["hauteur_chainage"]
    faces = [_face("toit_veranda", [(x0 - 0.1, y0, z_haut), (x1 + 0.1, y0, z_haut), (x1 + 0.1, y1 + 0.3, h + 0.15),
                                    (x0 - 0.1, y1 + 0.3, h + 0.15)])]
    return boites, faces


def construire(res: Resultats, prog: Programme) -> dict:
    impl = res.implantation
    hm = res.structure.hauteur_mur
    terrain_z = -E["terrain_sous_plancher"]
    base = terrain_z - E["assise_sous_terrain"]
    e = impl.emprise.epaisseur_ext
    w, d = impl.parametres["largeur_axe"], impl.parametres["profondeur_axe"]
    wg, dj = impl.parametres["largeur_garage"], impl.parametres["profondeur_jour"]

    boites = _murs(res, hm)
    boites += _fondations(res, base)
    boites.append(_boite("dalle", -e / 2, -e / 2, -0.10, w + e, d + e, 0.10))
    if wg:
        boites.append(_boite("dalle", -wg - e / 2, d - dj - e / 2, -0.10, wg + e / 2, dj + e, 0.10))
    bv, fv = _veranda(res, hm)
    bt, ft, z_max = _toiture(res, prog, hm)
    boites += bv + bt
    faces = fv + ft

    em = impl.emprise
    prof_ver = max([p.axe.y2 for p in impl.pieces if p.type == "veranda"], default=em.y_max)
    y_front = max(em.y_max, prof_ver)
    x_centre = (em.x_min + em.x_max) / 2
    tl, tp = prog.terrain_largeur, prog.terrain_profondeur
    terrain = {"x": _r(x_centre - tl / 2), "y": _r(y_front + prog.recul - tp), "l": _r(tl), "p": _r(tp),
               "z": _r(terrain_z)}

    hyp = [
        f"Plancher fini à ±0,00, terrain naturel à {fmt(terrain_z)} m, assise des semelles à {fmt(base)} m "
        f"(hors gel, sol porteur à confirmer par l'étude de sol).",
        f"Hauteur de mur {fmt(hm)} m (hauteur sous plafond + chaînage) ; faîtage ou haut d'acrotère à {fmt(z_max)} m.",
        "Allèges 0,90 m (1,60 m en salle d'eau) ; les ouvertures de 2,00 m et plus sont des portes-fenêtres.",
        "Maquette de présentation : le terrain est centré autour de la maison, recul avant selon le programme.",
    ]
    return {
        "boites": boites,
        "faces": faces,
        "terrain": terrain,
        "emprise": {"x_min": _r(em.x_min), "x_max": _r(em.x_max), "y_min": _r(em.y_min), "y_max": _r(y_front)},
        "niveaux": {"terrain": _r(terrain_z), "assise": _r(base), "plancher": 0.0, "haut_mur": _r(hm),
                    "haut": _r(z_max)},
        "toiture": {"type": prog.toiture, "pente": _r(res.toiture.pente), "couverture": prog.couverture},
        "hypotheses": hyp,
        "mention": "Modèle de présentation, non contractuel. Cotes et quantités : voir plan technique.",
    }

