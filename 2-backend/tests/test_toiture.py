import math

import pytest

from app.moteurs import implantation as im
from app.moteurs import toiture as to
from app.moteurs.programme import Programme


def _calc(**kw):
    p = Programme(**kw)
    return to.calculer(im.calculer(p), p)


def _niv(r, id_):
    return next(c.niveau for c in r.controles if c.id == id_)


W = 14 / 3.6 + 2 * 11.5 / 3.6 + 3.0  # largeur à l'axe du cas par défaut
D = 3.6 + 1.2 + 4.2


def test_surfaces_2_pans():
    r = _calc()
    l_, p_ = W + 0.2 + 1.0, D + 0.2 + 1.0  # nus extérieurs + 2 débords de 0,50
    assert r.surface_plan == pytest.approx(l_ * p_)
    assert r.surface == pytest.approx(l_ * p_ / math.cos(math.atan(0.25)))
    assert r.fermes == math.ceil(l_ / 1.2) + 1
    assert r.gouttieres == pytest.approx(2 * l_)
    assert r.descentes == max(2, math.ceil(l_ * p_ / 80))
    # pannes : tôle 1,0 m ; rampant = 5,1 / cos(atan 0,25)
    rampant = p_ / 2 / math.cos(math.atan(0.25))
    assert r.pannes_ml == pytest.approx(2 * (math.ceil(rampant / 1.0) + 1) * l_)
    assert r.liteaux_ml == 0


def test_tuiles_liteaux_et_pannes_rapprochees():
    r = _calc(couverture="tuiles", pente_toiture=45)
    assert r.liteaux_ml > 0
    p_ = D + 1.2
    rampant = p_ / 2 / math.cos(math.atan(0.45))
    assert r.pannes_ml == pytest.approx(2 * (math.ceil(rampant / 0.6) + 1) * (W + 1.2))


def test_4_pans_aretiers():
    r = _calc(toiture="4 pans")
    l_, p_ = W + 1.2, D + 1.2
    demi = p_ / 2
    assert r.aretiers_ml == pytest.approx(4 * math.sqrt(2 * demi ** 2 + (demi * 0.25) ** 2))
    assert r.gouttieres == pytest.approx(2 * (l_ + p_))


def test_terrasse():
    r = _calc(toiture="terrasse", couverture="dalle beton", pente_toiture=2)
    l_, p_ = W + 0.2, D + 0.2
    assert r.debord == 0 and r.surface == pytest.approx(l_ * p_)
    assert r.dalle_volume == pytest.approx(l_ * p_ * 0.15)
    assert r.acrotere_ml == pytest.approx(2 * (l_ + p_))
    assert r.charpente_ml == 0


@pytest.mark.parametrize("couverture,pente,niveau", [
    ("tole bac acier", 9, "bloquant"), ("tole bac acier", 10, "ok"),
    ("tole ondulee", 14, "bloquant"), ("tole ondulee", 15, "ok"),
    ("tuiles", 39, "bloquant"), ("tuiles", 40, "ok"),
])
def test_pentes_minimales(couverture, pente, niveau):
    r = _calc(couverture=couverture, pente_toiture=pente)
    assert _niv(r, "TOIT-PENTE") == niveau


def test_incoherences_couverture():
    assert _niv(_calc(toiture="terrasse", couverture="tole bac acier", pente_toiture=2), "TOIT-COUVERTURE") == \
        "bloquant"
    assert _niv(_calc(couverture="dalle beton"), "TOIT-COUVERTURE") == "bloquant"


def test_vent_avertissement():
    assert _niv(_calc(), "TOIT-VENT") == "avertissement"


def test_garage_ajoute_un_pan():
    sans = _calc()
    avec = _calc(garage=True)
    dj = 4.2
    assert avec.surface_plan == pytest.approx(sans.surface_plan + 3.2 * (dj + 0.2 + 1.0))
