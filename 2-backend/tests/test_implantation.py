import itertools
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.moteurs import implantation as im
from app.moteurs.programme import Programme
from app.rendu import plan_svg

GOLDEN = Path(__file__).parent / "cas_reference" / "villa_3ch_plan.svg"
VARIANTES = [
    Programme(),
    Programme(chambres=4, garage=True, bureau=True, salles_de_bain=2, maconnerie="parpaing 15", wc_separe=False),
    Programme(chambres=1, cuisine_ouverte=True, bureau=True, veranda=False),
    Programme(chambres=0, salles_de_bain=1),
    Programme(chambres=8, salles_de_bain=4, garage=True, toiture="terrasse"),
]


@pytest.fixture
def ref(programme_ref):
    return im.calculer(programme_ref)


def _niv(r, id_):
    return next(c for c in r.controles if c.id == id_).niveau


def test_largeurs_bande_nuit(ref):
    # chambre parentale 14 / 3,6 ; chambres 11,5 / 3,6 ; bloc sanitaire 3,0
    assert ref.piece("CH1").axe.l == pytest.approx(14 / 3.6)
    assert ref.piece("CH2").axe.l == pytest.approx(11.5 / 3.6)
    w = 14 / 3.6 + 2 * 11.5 / 3.6 + 3.0
    assert ref.parametres["largeur_axe"] == pytest.approx(w)


def test_bande_jour(ref):
    w = ref.parametres["largeur_axe"]
    # Dj = (32 + 11) / W = 3,24 → borné à 4,2
    assert (32 + 11) / w < 4.2
    assert ref.parametres["profondeur_jour"] == pytest.approx(4.2)
    assert ref.piece("CUI").axe.l == pytest.approx(11 / 4.2)
    assert ref.piece("SEJ").axe.l == pytest.approx(w - 11 / 4.2)


def test_surfaces_nettes(ref):
    ch1 = ref.piece("CH1")
    # mur extérieur 0,20 à gauche et en haut, cloisons 0,10 à droite et en bas
    assert ch1.net.l == pytest.approx(14 / 3.6 - 0.10 - 0.05)
    assert ch1.net.p == pytest.approx(3.6 - 0.10 - 0.05)
    assert ch1.surface_nette == pytest.approx(ch1.net.l * ch1.net.p)
    assert ref.piece("CLR").net.p == pytest.approx(1.10)


def test_emprise_cas_reference_bloquante(ref):
    # 13,48 m + 2 × 2 m de recul > 15 m : le cas de référence est bloquant en largeur
    assert ref.emprise.largeur == pytest.approx(14 / 3.6 + 2 * 11.5 / 3.6 + 3.0 + 0.2)
    c = next(c for c in ref.controles if c.id == "IMPL-EMPRISE-L")
    assert c.niveau == "bloquant" and c.corrigeable
    assert _niv(ref, "IMPL-EMPRISE-P") == "ok"


def test_emprise_ok_terrain_large():
    r = im.calculer(Programme(terrain_largeur=20))
    assert _niv(r, "IMPL-EMPRISE-L") == "ok"


def test_controles_surfaces_couloir(ref):
    assert _niv(ref, "IMPL-SURF-CH1") == "ok"
    assert _niv(ref, "IMPL-SURF-SEJ") == "ok"
    assert _niv(ref, "IMPL-COULOIR") == "ok"


def test_eclairement_avertissement(ref):
    # chambre parentale : 1,20 × 1,35 = 1,62 m² < 12,90 / 6
    assert _niv(ref, "IMPL-FEN-CH1") == "avertissement"


def test_niveaux_bloquant():
    r = im.calculer(Programme(niveaux=2))
    assert _niv(r, "IMPL-NIVEAUX") == "bloquant"


def test_maconnerie_15():
    r = im.calculer(Programme(maconnerie="parpaing 15"))
    assert all(m.epaisseur == 0.15 for m in r.murs if m.type == "exterieur")


def _nb_pieces_avec_porte(r, prog):
    return sum(1 for p in r.pieces if p.type in im.TYPES_AVEC_PORTE
               and not (p.type == "cuisine" and prog.cuisine_ouverte))


@pytest.mark.parametrize("prog", VARIANTES)
def test_variantes_coherentes(prog):
    r = im.calculer(prog)
    # nombre de portes = nombre de pièces à desservir
    assert sum(1 for o in r.ouvertures if o.type == "porte") == _nb_pieces_avec_porte(r, prog)
    # chaque pièce habitable a une fenêtre
    for p in r.pieces:
        if p.habitable:
            assert any(o.piece_id == p.id and o.type == "fenetre" for o in r.ouvertures), p.id
    # pièces sans chevauchement (rectangles nets)
    interieures = [p for p in r.pieces if not p.exterieure]
    for a, b in itertools.combinations(interieures, 2):
        assert not (a.net.x < b.net.x2 - 1e-9 and b.net.x < a.net.x2 - 1e-9
                    and a.net.y < b.net.y2 - 1e-9 and b.net.y < a.net.y2 - 1e-9), (a.id, b.id)
    # ouvertures dans les murs, sans chevauchement entre elles sur un même mur
    murs = {m.id: m for m in r.murs}
    par_mur = {}
    for o in r.ouvertures:
        m = murs[o.mur_id]
        par_mur.setdefault(m.id, []).append(o)
        if m.horizontal:
            assert min(m.x1, m.x2) <= o.x - o.largeur / 2 and o.x + o.largeur / 2 <= max(m.x1, m.x2)
        else:
            assert min(m.y1, m.y2) <= o.y - o.largeur / 2 and o.y + o.largeur / 2 <= max(m.y1, m.y2)
    for liste in par_mur.values():
        for a, b in itertools.combinations(liste, 2):
            ca, cb = (a.x, b.x) if a.horizontal else (a.y, b.y)
            assert abs(ca - cb) >= (a.largeur + b.largeur) / 2, (a.id, b.id)
    # les chaînes de cotes s'additionnent
    for cote in ("bas", "gauche"):
        c1 = sum(k.valeur for k in r.cotes if k.cote == cote and k.chaine == 1)
        c2 = sum(k.valeur for k in r.cotes if k.cote == cote and k.chaine == 2)
        assert c1 == pytest.approx(c2)


# ---------------------------------------------------------------------------
# Rendu SVG
# ---------------------------------------------------------------------------


def _svg(r, **kw):
    return plan_svg.rendre_plan(r, nom_projet="Villa", date="2026-10-18", **kw)


def _boites_textes(racine):
    ns = "{http://www.w3.org/2000/svg}"
    for t in racine.iter(f"{ns}text"):
        x, y = float(t.get("x")), float(t.get("y"))
        taille = float(t.get("font-size"))
        larg = len(t.text or "") * taille * 0.62
        ancre = t.get("text-anchor")
        x0 = x - larg / 2 if ancre == "middle" else x - larg if ancre == "end" else x
        boite = (x0, y - taille, larg, taille * 1.25)
        rot = t.get("transform")
        if rot:
            assert re.match(r"rotate\(-90(\.0)? ", rot)
            dx, dy = boite[0] - x, boite[1] - y
            boite = (x + dy, y - dx - boite[2], boite[3], boite[2])
        yield t.text, boite


@pytest.mark.parametrize("prog", VARIANTES)
def test_svg_valide_et_textes_dans_viewbox(prog):
    svg = _svg(im.calculer(prog))
    racine = ET.fromstring(svg)
    vx, vy, vl, vh = map(float, racine.get("viewBox").split())
    for texte, (x, y, l_, h_) in _boites_textes(racine):
        assert x >= vx and y >= vy and x + l_ <= vx + vl and y + h_ <= vy + vh, texte


def test_svg_portes_egal_pieces(ref, programme_ref):
    racine = ET.fromstring(_svg(ref))
    ns = "{http://www.w3.org/2000/svg}"
    portes = [g for g in racine.iter(f"{ns}g") if "ouverture-porte" in (g.get("class") or "")]
    assert len(portes) == _nb_pieces_avec_porte(ref, programme_ref)


def test_svg_calques(ref):
    svg = _svg(ref)
    for c in ("calque-murs", "calque-textes", "calque-cotes", "calque-annotations"):
        assert f'class="{c}"' in svg
    seul = _svg(ref, calques=["murs"])
    assert 'class="calque-murs"' in seul and "calque-cotes" not in seul and "<text" not in seul.split("</style>")[1]


def test_svg_couleurs_par_variables(ref):
    svg = _svg(ref)
    corps = svg.split("</style>")[1]
    assert not re.search(r'(fill|stroke)="#', corps)
    assert "var(--plan-mur" in svg


@pytest.mark.parametrize("prog", VARIANTES)
def test_etiquettes_sans_chevauchement(prog):
    r = im.calculer(prog)
    zones = [b for _, b in plan_svg._zones_ouvrants(r)]
    etiquettes = plan_svg.placer_etiquettes(r)
    for et in etiquettes:
        p = r.piece(et.piece_id)
        assert et.boite.dans(plan_svg.Boite(p.net.x, p.net.y, p.net.l, p.net.p)), p.id
        assert not any(et.boite.chevauche(z) for z in zones), p.id
    for a, b in itertools.combinations(etiquettes, 2):
        assert not a.boite.chevauche(b.boite), (a.piece_id, b.piece_id)


def test_golden_cas_reference(programme_ref):
    from app.moteurs import chaine

    r = chaine.calculer(programme_ref)
    svg = _svg(r.implantation, elec=r.electricite.model_dump(), structure=r.structure.model_dump(),
               calques=plan_svg.CALQUES)
    if os.getenv("MAJ_GOLDEN") or not GOLDEN.exists():
        GOLDEN.write_text(svg, encoding="utf-8")
    assert svg == GOLDEN.read_text(encoding="utf-8"), "Plan modifié : relancer avec MAJ_GOLDEN=1 après revue visuelle"


def test_decalage_contour_rectangle():
    pts = plan_svg._decaler_contour([(0, 0), (4, 0), (4, 3), (0, 3)], 0.1)
    assert [tuple(round(v, 6) for v in p) for p in pts] == [(-0.1, -0.1), (4.1, -0.1), (4.1, 3.1), (-0.1, 3.1)]
    assert math.isclose(pts[0][0], -0.1)
