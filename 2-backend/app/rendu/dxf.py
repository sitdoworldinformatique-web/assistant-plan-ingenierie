"""Export DXF du plan (ezdxf) : mêmes données que le SVG, en centimètres (1 unité = 1 cm), axe Y vers le haut.

Calques : MURS, PORTES, FENETRES, COTES, TEXTES, ELEC, STRUCTURE (CdC § 4).
"""
from __future__ import annotations

import io
import math

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Matrix44

from app.moteurs.implantation import Ouverture, ResultatImplantation

MENTION = "À valider par un ingénieur qualifié"
CALQUES = {"MURS": 7, "PORTES": 3, "FENETRES": 5, "COTES": 4, "TEXTES": 7, "ELEC": 1, "STRUCTURE": 6}


def _p(x: float, y: float) -> tuple[float, float]:
    """Repère du plan (y vers le bas) → repère DXF (y vers le haut)."""
    return (x, -y)


def _rect_mur(m) -> list[tuple[float, float]]:
    h = m.epaisseur / 2
    if m.horizontal:
        x0, x1 = sorted((m.x1, m.x2))
        return [_p(x0 - h, m.y1 - h), _p(x1 + h, m.y1 - h), _p(x1 + h, m.y1 + h), _p(x0 - h, m.y1 + h)]
    y0, y1 = sorted((m.y1, m.y2))
    return [_p(m.x1 - h, y0 - h), _p(m.x1 + h, y0 - h), _p(m.x1 + h, y1 + h), _p(m.x1 - h, y1 + h)]


def _ouverture(msp, o: Ouverture) -> None:
    w, e, s = o.largeur, o.epaisseur, o.sens

    def P(t: float, n: float) -> tuple[float, float]:
        return _p(t, o.y + n) if o.horizontal else _p(o.x + n, t)

    c = o.x if o.horizontal else o.y
    a0, a1 = c - w / 2, c + w / 2
    couche = "FENETRES" if o.type in ("fenetre", "baie") else "PORTES"
    attr = {"layer": couche}
    msp.add_line(P(a0, -e / 2), P(a0, e / 2), dxfattribs=attr)
    msp.add_line(P(a1, -e / 2), P(a1, e / 2), dxfattribs=attr)
    if o.type == "fenetre":
        for k in (-e / 2, 0.0, e / 2):
            msp.add_line(P(a0, k), P(a1, k), dxfattribs=attr)
    elif o.type == "baie":
        for k in (-e / 2, e / 2):
            msp.add_line(P(a0, k), P(a1, k), dxfattribs={**attr, "linetype": "DASHED"})
    elif o.type == "placard":
        msp.add_line(P(a0, s * 0.02), P(a1, s * 0.02), dxfattribs=attr)
    elif o.style == "basculante":
        msp.add_line(P(a0, s * e / 2), P(a1, s * e / 2), dxfattribs=attr)
        msp.add_line(P(a0, s * (e / 2 + 0.6)), P(a1, s * (e / 2 + 0.6)), dxfattribs={**attr, "linetype": "DASHED"})
    else:
        t_ch, t_lib = (a1, a0) if o.charniere > 0 else (a0, a1)
        face = s * e / 2
        ch, bout, jamb = P(t_ch, face), P(t_ch, face + s * w), P(t_lib, face)
        msp.add_line(ch, bout, dxfattribs=attr)
        ang_bout = math.degrees(math.atan2(bout[1] - ch[1], bout[0] - ch[0]))
        ang_jamb = math.degrees(math.atan2(jamb[1] - ch[1], jamb[0] - ch[0]))
        # ezdxf trace l'arc dans le sens trigonométrique : on prend le sens qui fait 90°
        debut, fin = (ang_bout, ang_jamb) if (ang_jamb - ang_bout) % 360 == 90 else (ang_jamb, ang_bout)
        msp.add_arc(ch, w, debut, fin, dxfattribs=attr)


def exporter(impl: ResultatImplantation, *, nom_projet: str, statut: str = MENTION, elec: dict | None = None,
             structure: dict | None = None) -> bytes:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.CM  # unité d'échange courante en architecture ; les lecteurs la lisent comme 1 unité = 1 cm
    doc.header["$LTSCALE"] = 20  # motifs de tirets lisibles à l'échelle du plan
    doc.header["$LASTSAVEDBY"] = "Assistant Plan Ingénierie"
    for nom, couleur in CALQUES.items():
        doc.layers.add(nom, color=couleur)
    msp = doc.modelspace()
    em = impl.emprise

    for m in impl.murs:
        msp.add_lwpolyline(_rect_mur(m), close=True, dxfattribs={"layer": "MURS"})
    for o in impl.ouvertures:
        _ouverture(msp, o)

    for pc in impl.pieces:
        if pc.exterieure:
            continue
        cx, cy = pc.net.centre
        msp.add_text(pc.nom, height=0.16, dxfattribs={"layer": "TEXTES"}).set_placement(
            _p(cx, cy - 0.12), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(f"{pc.surface_nette:.2f} m2".replace(".", ","), height=0.13, dxfattribs={"layer": "TEXTES"}
                     ).set_placement(_p(cx, cy + 0.12), align=TextEntityAlignment.MIDDLE_CENTER)
    msp.add_text(f"{nom_projet} - Plan du rez-de-chaussée - échelle 1:100 - {statut}", height=0.2,
                 dxfattribs={"layer": "TEXTES"}).set_placement(_p(em.x_min, em.y_max + 2.2),
                                                              align=TextEntityAlignment.LEFT)

    # Chaînes de cotes extérieures
    for k in impl.cotes:
        ch = 0.75 + 0.6 * (k.chaine - 1)
        v = k.valeur
        texte = f"{round(v * 100):d}" if v < 0.5 else f"{v:.2f}".replace(".", ",")
        if k.cote == "bas":
            y = em.y_max + ch
            msp.add_line(_p(k.debut, y), _p(k.fin, y), dxfattribs={"layer": "COTES"})
            for x in (k.debut, k.fin):
                msp.add_line(_p(x, em.y_max + 0.12), _p(x, y + 0.1), dxfattribs={"layer": "COTES"})
            msp.add_text(texte, height=0.1, dxfattribs={"layer": "COTES"}).set_placement(
                _p((k.debut + k.fin) / 2, y - 0.05), align=TextEntityAlignment.BOTTOM_CENTER)
        else:
            x = em.x_min - ch
            msp.add_line(_p(x, k.debut), _p(x, k.fin), dxfattribs={"layer": "COTES"})
            for y in (k.debut, k.fin):
                msp.add_line(_p(em.x_min - 0.12, y), _p(x - 0.1, y), dxfattribs={"layer": "COTES"})
            t = msp.add_text(texte, height=0.1, rotation=90, dxfattribs={"layer": "COTES"})
            t.set_placement(_p(x - 0.05, (k.debut + k.fin) / 2), align=TextEntityAlignment.BOTTOM_CENTER)

    for pt in (elec or {}).get("points", []):
        x, y = pt["x"], pt["y"]
        a = {"layer": "ELEC"}
        if pt["type"] == "lumiere":
            msp.add_circle(_p(x, y), 0.12, dxfattribs=a)
            msp.add_line(_p(x - 0.085, y - 0.085), _p(x + 0.085, y + 0.085), dxfattribs=a)
            msp.add_line(_p(x - 0.085, y + 0.085), _p(x + 0.085, y - 0.085), dxfattribs=a)
        elif pt["type"] == "tableau":
            msp.add_lwpolyline([_p(x - 0.15, y - 0.1), _p(x + 0.15, y - 0.1), _p(x + 0.15, y + 0.1),
                                _p(x - 0.15, y + 0.1)], close=True, dxfattribs=a)
        elif pt["type"] == "interrupteur":
            msp.add_circle(_p(x, y), 0.06, dxfattribs=a)
        else:
            msp.add_circle(_p(x, y), 0.07, dxfattribs=a)
            if pt["type"] == "prise_specialisee":
                msp.add_circle(_p(x, y), 0.11, dxfattribs=a)

    if structure:
        for sem in structure.get("semelles", []):
            b = sem.get("trace")
            if b:
                msp.add_lwpolyline([_p(b[0], b[1]), _p(b[0] + b[2], b[1]), _p(b[0] + b[2], b[1] + b[3]),
                                    _p(b[0], b[1] + b[3])], close=True,
                                   dxfattribs={"layer": "STRUCTURE", "linetype": "DASHED"})
        for pot in structure.get("poteaux", []):
            c = 0.10
            msp.add_lwpolyline([_p(pot["x"] - c, pot["y"] - c), _p(pot["x"] + c, pot["y"] - c),
                                _p(pot["x"] + c, pot["y"] + c), _p(pot["x"] - c, pot["y"] + c)], close=True,
                               dxfattribs={"layer": "STRUCTURE"})
            msp.add_solid([_p(pot["x"] - c, pot["y"] - c), _p(pot["x"] + c, pot["y"] - c),
                           _p(pot["x"] - c, pot["y"] + c), _p(pot["x"] + c, pot["y"] + c)],
                          dxfattribs={"layer": "STRUCTURE"})

    # Le dessin est construit en mètres puis mis à l'échelle (m → cm), textes compris
    metres_en_cm = Matrix44.scale(100, 100, 100)
    for entite in msp:
        entite.transform(metres_en_cm)
    tampon = io.StringIO()
    doc.write(tampon)
    return tampon.getvalue().encode("utf-8")
