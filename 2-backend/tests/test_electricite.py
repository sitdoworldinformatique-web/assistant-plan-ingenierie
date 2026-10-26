import json
import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.moteurs import electricite as el
from app.moteurs import implantation as im
from app.moteurs.programme import Programme
from app.rendu import plan_svg, unifilaire

RACINE = Path(__file__).resolve().parents[2]
PROTOTYPE = RACINE / "docs" / "reference" / "prototype-electrification.html"
OUTIL = Path(__file__).parent / "outils" / "prototype_elec.cjs"
ATTENDU = Path(__file__).parent / "cas_reference" / "prototype_elec_villa_3ch.json"


@pytest.fixture
def impl_ref(programme_ref):
    return im.calculer(programme_ref)


@pytest.fixture
def elec_ref(impl_ref, programme_ref):
    return el.calculer(impl_ref, programme_ref)


def _entree_prototype(impl, prog, elec):
    """État du prototype équivalent à notre projet (mêmes pièces, mêmes longueurs)."""
    pieces = el._pieces_pour_prototype(impl, prog)
    types = {"veranda": "exterieur"}
    return {
        "projet": {"nom": prog.nom, "longueur": 15, "terre": prog.resistance_terre, "autonomie": prog.autonomie_h,
                   "soleil": prog.ensoleillement_h},
        "pieces": [{"id": p["id"], "nom": p["nom"], "type": types.get(p["type"], p["type"]),
                    "surface": p["surface"], "clim": p["clim"]} for p in pieces],
        "equip": {k: k in prog.equipements for k in el.E["ordre_specialises"]},
        "longueurs": {c.key: c.l for c in elec.circuits},
        "signature": {"nom": "", "ordre": "", "coche": False, "valeLe": None},
        "nextId": 1,
    }


def _comparer(elec, attendu):
    assert [c.key for c in elec.circuits] == [c["key"] for c in attendu["circuits"]]
    for c, a in zip(elec.circuits, attendu["circuits"]):
        assert (c.nom, c.det, c.n, c.in_, c.num, c.id, c.etat) == (a["nom"], a["det"], a["n"], a["In"], a["num"],
                                                                    a["id"], a["etat"]), c.key
        assert c.p == pytest.approx(a["P"]) and c.s == pytest.approx(a["S"])
        assert c.ib == pytest.approx(a["Ib"]) and c.du == pytest.approx(a["du"])
    assert [(d.nom, d.type, d.in_, d.circuits) for d in elec.differentiels] == \
        [(d["nom"], d["type"], d["In"], d["circuits"]) for d in attendu["ids"]]
    assert elec.bilan.kva == pytest.approx(attendu["kva"])
    assert elec.bilan.branchement == attendu["branch"]


def test_identique_au_prototype_fige(elec_ref):
    """Le cas de référence donne exactement les mêmes circuits que le prototype (sortie figée)."""
    _comparer(elec_ref, json.loads(ATTENDU.read_text(encoding="utf-8")))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js absent")
@pytest.mark.parametrize("prog", [
    None,
    Programme(chambres=6, salles_de_bain=2, garage=True, bureau=True, equipements=["plaque", "four",
              "lavelinge", "lavevaisselle", "chauffeeau", "pompe"], resistance_terre=250),
    Programme(chambres=1, clim_chambres=False, clim_sejour=False, equipements=[], veranda=False,
              longueurs_circuits={"pc-1": 60, "ecl-1": 95}),
    Programme(chambres=8, salles_de_bain=4, garage=True, resistance_terre=800),
])
def test_identique_au_prototype_execute(prog, programme_ref):
    """Exécute le JavaScript du prototype sur les mêmes données et compare tout."""
    prog = prog or programme_ref
    impl = im.calculer(prog)
    elec = el.calculer(impl, prog)
    entree = json.dumps(_entree_prototype(impl, prog, elec))
    sortie = subprocess.run(["node", str(OUTIL), str(PROTOTYPE)], input=entree, capture_output=True, text=True,
                            check=True).stdout
    attendu = json.loads(sortie)
    if prog is programme_ref and os.getenv("MAJ_GOLDEN"):
        ATTENDU.write_text(sortie, encoding="utf-8")
    _comparer(elec, attendu)


def test_regles_prises_et_points(impl_ref):
    sej = impl_ref.piece("SEJ")
    lum, pc = el.nb_points(sej)
    assert lum == math.ceil(sej.surface_nette / 20) and pc == max(5, math.ceil(sej.surface_nette / 4))
    assert el.nb_points(impl_ref.piece("CH1")) == (1, 3)
    assert el.nb_points(impl_ref.piece("CUI")) == (1, 6)
    assert el.nb_points(impl_ref.piece("WC")) == (1, 0)


def test_chute_de_tension_formule():
    # ΔU = 2 ρ L Ib / (S U) × 100 : 16 A, 30 m, 2,5 mm²
    circ, _, _ = el.calculer_circuits([{"id": "a", "nom": "Ch", "type": "chambre", "surface": 12, "clim": False}],
                                      {}, {"pc-1": 30.0}, 30.0)
    pc = next(c for c in circ if c.key == "pc-1")
    assert pc.du == pytest.approx(2 * 0.023 * 30 * 16 / (2.5 * 230) * 100)


def test_section_augmentee_puis_bloquant():
    base = [{"id": "a", "nom": "Ch", "type": "chambre", "surface": 12, "clim": False}]
    circ, _, _ = el.calculer_circuits(base, {}, {"pc-1": 60.0}, 60.0)
    pc = next(c for c in circ if c.key == "pc-1")
    assert pc.etat == "warn" and pc.s == 4.0  # 2,5 mm² → 5,12 % > 5 % ; 4 mm² → 3,2 %
    circ, _, _ = el.calculer_circuits(base, {}, {"pc-1": 300.0}, 300.0)
    pc = next(c for c in circ if c.key == "pc-1")
    assert pc.etat == "bad" and pc.s == 16.0


def test_terre():
    for r, niveau in ((None, "bloquant"), (45, "ok"), (250, "avertissement"), (800, "bloquant")):
        prog = Programme(resistance_terre=r)
        elec = el.calculer(im.calculer(prog), prog)
        assert next(c for c in elec.controles if c.id == "ELEC-TERRE").niveau == niveau


def test_differentiels(elec_ref):
    ids = elec_ref.differentiels
    assert ids[0].type == "A" and set(ids[0].circuits) == {"spe-plaque", "spe-lavelinge"}
    assert all(len(d.circuits) <= 8 for d in ids)
    eclairages = [d.nom for d in ids if any(k.startswith("ecl-") for k in d.circuits)]
    assert len(eclairages) == len(set(eclairages))  # éclairages séparés


def test_placement_symboles(impl_ref, elec_ref):
    pts = elec_ref.points
    assert sum(p.type == "tableau" for p in pts) == 1
    zones = [b for _, b in plan_svg._zones_ouvrants(impl_ref)]
    for p in pts:
        piece = impl_ref.piece(p.piece_id)
        if p.type in ("lumiere", "prise", "prise_specialisee"):
            n = piece.net
            assert n.x - 1e-9 <= p.x <= n.x2 + 1e-9 and n.y - 1e-9 <= p.y <= n.y2 + 1e-9, p.id
        if p.type in ("prise", "prise_specialisee"):
            assert not any(z.x < p.x < z.x + z.l and z.y < p.y < z.y + z.h for z in zones), p.id
            n = piece.net
            # ≥ 0,30 m des angles
            d_x = min(abs(p.x - n.x), abs(p.x - n.x2))
            d_y = min(abs(p.y - n.y), abs(p.y - n.y2))
            assert max(d_x, d_y) >= 0.30 - 1e-6, p.id
    # tous les points de circuits sont rattachés
    assert all(p.circuit for p in pts if p.type != "tableau")
    # un point lumineux au centre des pièces à 1 point
    ch1 = impl_ref.piece("CH1")
    lum = next(p for p in pts if p.type == "lumiere" and p.piece_id == "CH1")
    assert (lum.x, lum.y) == pytest.approx(ch1.net.centre)


def test_longueurs_surchargees(programme_ref):
    prog = programme_ref.model_copy(update={"longueurs_circuits": {"pc-1": 42.0}})
    elec = el.calculer(im.calculer(prog), prog)
    assert elec.circuit("pc-1").l == 42.0


def test_longueur_manhattan(impl_ref, elec_ref):
    tab = next(p for p in elec_ref.points if p.type == "tableau")
    pts = [p for p in elec_ref.points if p.circuit == "spe-pompe" and p.type != "interrupteur"]
    d = max(abs(p.x - tab.x) + abs(p.y - tab.y) for p in pts)
    assert elec_ref.circuit("spe-pompe").l == pytest.approx((d + 2) * 1.1)


def test_unifilaire_svg(elec_ref):
    svg = unifilaire.rendre(elec_ref)
    racine = ET.fromstring(svg)
    textes = " ".join(t.text or "" for t in racine.iter("{http://www.w3.org/2000/svg}text"))
    assert "Disjoncteur de branchement" in textes and "500 mA" in textes
    for c in elec_ref.circuits:
        assert f"C{c.num} " in textes
    for d in elec_ref.differentiels:
        assert d.nom in textes


def test_plan_avec_symboles(impl_ref, elec_ref):
    svg = plan_svg.rendre_plan(impl_ref, nom_projet="Villa", date="2026-10-18", elec=elec_ref.model_dump(),
                                 calques=["murs", "elec"])
    assert 'class="calque-elec"' in svg
    ET.fromstring(svg)
