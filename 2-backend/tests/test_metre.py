import json
import math
from pathlib import Path

import pytest

from app.moteurs import chaine, solaire
from app.moteurs.metre import prix_par_defaut
from app.moteurs.programme import Programme

ATTENDU_PROTO = Path(__file__).parent / "cas_reference" / "prototype_elec_villa_3ch.json"


@pytest.fixture
def res(programme_ref):
    return chaine.calculer(programme_ref)


def _ligne(r, code):
    return next(lg for lg in r.metre.lignes if lg.code == code)


def test_solaire_formules(res):
    s = res.solaire
    # éclairage 1 300 W + 600 W + pompe 1 100 W = 3 000 W
    assert s.charges_essentielles_w == pytest.approx(3000)
    assert s.onduleur_kva == pytest.approx(4.0)  # 3 000 × 1,25 = 3,75 → 4,0 kVA
    assert s.batteries_kwh == pytest.approx(3000 * 0.6 * 6 / 1000 / 0.72)  # 15 kWh
    assert s.energie_jour_kwh == pytest.approx(18.0)
    assert s.panneaux_kwc == pytest.approx(18 / (4.5 * 0.75))


def test_solaire_identique_au_prototype(res):
    proto = json.loads(ATTENDU_PROTO.read_text(encoding="utf-8"))
    assert res.solaire.charges_essentielles_w == pytest.approx(proto["Pess"])
    assert res.solaire.onduleur_kva == pytest.approx(proto["ond"])
    assert res.solaire.batteries_kwh == pytest.approx(proto["bat"])
    assert res.solaire.panneaux_kwc == pytest.approx(proto["kwc"])


def test_solaire_non_demande(programme_ref):
    p = programme_ref.model_copy(update={"solaire": False})
    r = chaine.calculer(p)
    assert r.solaire.onduleur_kva == 0
    assert not any(lg.lot == "Kit solaire" for lg in r.metre.lignes)
    assert isinstance(r.solaire, solaire.ResultatSolaire)


def test_blocs_formule(res):
    q = res.metre.quantites
    assert _ligne(res, "blocs_20").quantite == math.ceil(q["murs_ext_m2"] * 12.5 * 1.05)
    assert _ligne(res, "blocs_10").quantite == math.ceil(q["cloisons_m2"] * 12.5 * 1.05)


def test_surface_murs_deduit_ouvertures(res):
    impl = res.implantation
    hsp = 3.0
    brut = sum(m.longueur for m in impl.murs if m.type != "cloison") * hsp
    murs = {m.id: m for m in impl.murs}
    ouv = sum(o.largeur * min(o.hauteur, hsp) for o in impl.ouvertures if murs[o.mur_id].type != "cloison")
    assert res.metre.quantites["murs_ext_m2"] == pytest.approx(brut - ouv)


def test_acier_ciment_granulats(res):
    q = res.metre.quantites
    acier = q["beton_semelles_m3"] * 80 + q["beton_chainages_m3"] * 120
    assert _ligne(res, "acier").quantite == pytest.approx(acier)
    mortier = _ligne(res, "mortier").quantite
    assert _ligne(res, "ciment").quantite == math.ceil((q["beton_total_m3"] + mortier) * 350 / 50)
    assert _ligne(res, "gravier").quantite == pytest.approx(q["beton_total_m3"] * 0.8)


def test_beton_fondation(res):
    v = sum(s.longueur * s.largeur * s.hauteur for s in res.structure.semelles)
    assert _ligne(res, "beton_fondation").quantite == pytest.approx(v)
    f = sum(s.longueur * s.largeur * (s.hauteur + 0.30) for s in res.structure.semelles)
    assert _ligne(res, "terrassement").quantite == pytest.approx(f)


def test_carrelage_et_menuiseries(res):
    s = sum(p.surface_nette for p in res.implantation.pieces if p.type != "garage")
    assert _ligne(res, "carrelage").quantite == pytest.approx(s * 1.10)
    assert _ligne(res, "porte_entree").quantite == 1
    assert _ligne(res, "fenetre").quantite == sum(o.type == "fenetre" for o in res.implantation.ouvertures)


def test_cables_par_section(res):
    l15 = sum(c.l for c in res.electricite.circuits if c.s == 1.5) * 3
    assert _ligne(res, "cable_1_5").quantite == pytest.approx(l15)
    assert _ligne(res, "disjoncteur").quantite == len(res.electricite.circuits)
    assert _ligne(res, "luminaire").quantite == sum(p.type == "lumiere" for p in res.electricite.points)


def test_totaux(res):
    for lg in res.metre.lignes:
        assert lg.total == pytest.approx(lg.quantite * lg.prix_unitaire)
    assert res.metre.total == pytest.approx(sum(lg.total for lg in res.metre.lignes))
    assert "indicatif" in res.metre.mention_prix


def test_prix_personnalises(programme_ref):
    prix = prix_par_defaut()
    prix["ciment"]["prix"] = 20.0
    r = chaine.calculer(programme_ref, prix)
    assert _ligne(r, "ciment").prix_unitaire == 20.0


def test_toiture_terrasse_postes():
    r = chaine.calculer(Programme(toiture="terrasse", couverture="dalle beton", pente_toiture=2, resistance_terre=40))
    codes = {lg.code for lg in r.metre.lignes}
    assert {"etancheite", "acrotere"} <= codes and "charpente" not in codes
