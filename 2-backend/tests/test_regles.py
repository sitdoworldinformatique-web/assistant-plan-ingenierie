import pytest

from app.moteurs import chaine, regles
from app.moteurs.commun import Controle
from app.moteurs.programme import Programme


def C(id_, niveau, module="electricite", corrigeable=False):
    return Controle(id=id_, module=module, niveau=niveau, titre=id_, corrigeable=corrigeable)


def test_statut():
    assert regles.statut([C("a", "ok")]) == "conforme"
    assert regles.statut([C("a", "ok"), C("b", "avertissement")]) == "conforme_avec_reserves"
    assert regles.statut([C("a", "bloquant"), C("b", "avertissement")]) == "bloque"
    assert regles.statut([]) == "conforme"


def test_agreger_par_module():
    tous, global_, par_mod = regles.agreger([C("a", "ok")], [C("b", "bloquant", "structure")])
    assert len(tous) == 2 and global_ == "bloque"
    assert par_mod["electricite"] == "conforme" and par_mod["structure"] == "bloque"


def test_identifiants_uniques():
    with pytest.raises(ValueError):
        regles.agreger([C("a", "ok")], [C("a", "ok")])


def test_bloquants_corrigeables():
    cs = [C("a", "bloquant", corrigeable=True), C("b", "bloquant"), C("c", "avertissement", corrigeable=True)]
    assert [c.id for c in regles.bloquants_corrigeables(cs)] == ["a"]


@pytest.mark.parametrize("prog", [
    Programme(),
    Programme(chambres=6, garage=True, bureau=True, salles_de_bain=3, toiture="4 pans", resistance_terre=10),
    Programme(toiture="terrasse", couverture="dalle beton", pente_toiture=2, cuisine_ouverte=True),
])
def test_chaine_complete_identifiants_stables(prog):
    r1 = chaine.calculer(prog)
    r2 = chaine.calculer(prog)
    assert [c.id for c in r1.controles] == [c.id for c in r2.controles]
    assert all(c.id and c.module in regles.MODULES for c in r1.controles)


def test_cas_reference_bloque_par_emprise(programme_ref):
    r = chaine.calculer(programme_ref)
    assert r.statut == "bloque"
    assert [c.id for c in r.controles if c.niveau == "bloquant"] == ["IMPL-EMPRISE-L"]


def test_terrain_suffisant_conforme_avec_reserves(programme_ref):
    r = chaine.calculer(programme_ref.model_copy(update={"terrain_largeur": 18}))
    assert r.statut == "conforme_avec_reserves"
