import pytest

from app.moteurs import implantation as im
from app.moteurs import structure as st
from app.moteurs.programme import Programme


def _calc(**kw):
    p = Programme(**kw)
    return st.calculer(im.calculer(p), p), p


def _niv(r, id_):
    return next(c.niveau for c in r.controles if c.id == id_)


def test_descente_de_charges_facade_main():
    r, _ = _calc()
    s = r.semelles[0]  # façade arrière y = 0
    # mur : 2,2 kN/m² × (3,0 + 0,3) = 7,26 ; chaînage : 25 × 0,2 × 0,2 = 1,0
    assert s.q_mur == pytest.approx(7.26)
    assert s.q_chainage == pytest.approx(1.0)
    # demi-portée : D / 2 + débord = (3,6 + 1,2 + 4,2) / 2 + 0,5 = 5,0 ; tôle 0,5 kN/m²
    assert s.largeur_reprise == pytest.approx(5.0)
    assert s.q_toiture == pytest.approx(2.5)
    assert s.q_els == pytest.approx(10.76)
    # B = 10,76 / 150 = 0,072 → minimum 0,40 ; h = max(0,25 ; 0,20 / 4 + 0,05) = 0,25
    assert s.largeur == pytest.approx(0.40) and s.hauteur == pytest.approx(0.25)


def test_pignon_2_pans():
    r, _ = _calc()
    pignon = r.semelles[1]  # mur vertical droit
    assert pignon.largeur_reprise == pytest.approx(0.6)  # entraxe des fermes / 2
    assert pignon.q_els == pytest.approx(7.26 + 1.0 + 0.5 * 0.6)


def test_tuiles_et_parpaing_15():
    r, _ = _calc(couverture="tuiles", pente_toiture=45, maconnerie="parpaing 15", hauteur_sous_plafond=2.8)
    s = r.semelles[0]
    assert s.q_mur == pytest.approx(1.8 * 3.1)
    assert s.q_toiture == pytest.approx(0.9 * 5.0)


def test_semelle_large_terrasse_sol_faible():
    r, p = _calc(toiture="terrasse", couverture="dalle beton", pente_toiture=2, portance_sol=0.02)
    impl = im.calculer(p)
    refend = next(s for s in r.semelles if impl.murs[int(s.mur_id[1:]) - 1].type == "refend")
    # refend du couloir : demi-portées 3,6 / 2 + 1,2 / 2 = 2,4 m ; terrasse 6,5 + 1,5 = 8 kN/m²
    assert refend.largeur_reprise == pytest.approx(2.4)
    q = 7.26 + 1.0 + 8.0 * 2.4  # 27,46 kN/m
    assert refend.q_els == pytest.approx(q)
    # B = 27,46 / 20 = 1,373 → 1,40 ; h = (1,40 − 0,20) / 4 + 0,05 = 0,35
    assert refend.largeur == pytest.approx(1.40)
    assert refend.hauteur == pytest.approx(0.35)
    assert _niv(r, "STRUCT-SOL") == "bloquant"


def test_arrondi_aux_5_cm_superieurs():
    assert st._arrondi_sup(0.41, 0.05) == pytest.approx(0.45)
    assert st._arrondi_sup(0.45, 0.05) == pytest.approx(0.45)


def test_controles():
    r, _ = _calc()
    assert _niv(r, "STRUCT-PORTANCE") == "avertissement"
    r, _ = _calc(portance_mesuree=True, portance_sol=0.2)
    assert _niv(r, "STRUCT-PORTANCE") == "ok"
    r, _ = _calc(niveaux=2)
    assert _niv(r, "STRUCT-NIVEAUX") == "bloquant"


def test_poteaux_et_chainages():
    r, p = _calc()
    impl = im.calculer(p)
    # 4 angles au moins, et chaque extrémité de mur porte un poteau
    coins = {(round(x, 3), round(y, 3)) for x, y in impl.emprise.contour}
    pos = {(round(q.x, 3), round(q.y, 3)) for q in r.poteaux}
    assert coins <= pos
    assert all(q.section == "20 × 20" and q.armatures == "4 HA10" for q in r.poteaux)
    # chaînage horizontal sur tous les murs, linteau par ouverture (portée + 2 × 0,20)
    assert sum(c.type == "horizontal" for c in r.chainages) == len(impl.murs)
    o = impl.ouvertures[0]
    lin = next(c for c in r.chainages if c.reference == o.id)
    assert lin.longueur == pytest.approx(o.largeur + 0.40)


def test_poteaux_ouverture_large():
    r, p = _calc(garage=True)
    impl = im.calculer(p)
    porte = next(o for o in impl.ouvertures if o.style == "basculante")  # 2,40 m > 1,8 m
    d = porte.largeur / 2 + 0.10
    pos = {(round(q.x, 3), round(q.y, 3)) for q in r.poteaux}
    assert (round(porte.x - d, 3), round(porte.y, 3)) in pos and (round(porte.x + d, 3), round(porte.y, 3)) in pos


def test_dallage():
    r, p = _calc()
    impl = im.calculer(p)
    s = sum(pc.surface_nette for pc in impl.pieces if not pc.exterieure)
    assert r.dallage["surface"] == pytest.approx(s)
    assert r.dallage["volume_beton"] == pytest.approx(s * 0.10)
