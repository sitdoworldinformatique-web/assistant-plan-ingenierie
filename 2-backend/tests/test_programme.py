import pytest
from pydantic import ValidationError

from app.moteurs.programme import EQUIPEMENTS_DEFAUT, Programme, analyser, schema_json


def test_defauts():
    p = Programme()
    assert p.niveaux == 1 and p.chambres == 3 and p.salles_de_bain == 1
    assert p.wc_separe and p.veranda and not p.garage and not p.bureau
    assert p.toiture == "2 pans" and p.couverture == "tole bac acier"
    assert p.portance_sol == 0.15 and p.portance_mesuree is False
    assert p.resistance_terre is None
    assert p.equipements == EQUIPEMENTS_DEFAUT


def test_bornes():
    with pytest.raises(ValidationError):
        Programme(chambres=9)
    with pytest.raises(ValidationError):
        Programme(salles_de_bain=0)
    with pytest.raises(ValidationError):
        Programme(toiture="1 pan")
    with pytest.raises(ValidationError):
        Programme(champ_inconnu=1)


def test_schema_json_pour_outil_claude():
    s = schema_json()
    assert s["type"] == "object"
    assert "chambres" in s["properties"]
    assert s["properties"]["toiture"]["enum"] == ["2 pans", "4 pans", "terrasse"]


def test_cas_reference(cas_reference):
    p, remarques = analyser(cas_reference["texte"])
    assert p.model_dump() == Programme(**cas_reference["programme"]).model_dump()
    assert not any("terre" in r.lower() for r in remarques)


# 15 phrases : (texte, valeurs attendues)
PHRASES = [
    (
        "villa plain-pied, 3 chambres, terrain 15×20, toiture 2 pans en tôle",
        {"niveaux": 1, "chambres": 3, "terrain_largeur": 15, "terrain_profondeur": 20,
         "toiture": "2 pans", "couverture": "tole bac acier"},
    ),
    (
        "Maison de 4 chambres avec 2 salles de bain et un garage, terrain de 20 x 30 m",
        {"chambres": 4, "salles_de_bain": 2, "garage": True, "terrain_largeur": 20, "terrain_profondeur": 30},
    ),
    (
        "Petite maison deux chambres, sans véranda, cuisine américaine, parcelle 12 par 18",
        {"chambres": 2, "veranda": False, "cuisine_ouverte": True, "terrain_largeur": 12, "terrain_profondeur": 18},
    ),
    (
        "F5 en briques avec bureau, toit à quatre pans en tuiles, pente 45 %",
        {"chambres": 4, "maconnerie": "brique", "bureau": True, "toiture": "4 pans",
         "couverture": "tuiles", "pente_toiture": 45},
    ),
    (
        "Maison avec toit terrasse, 3 chambres, parpaing de 15, terrain 18 sur 25",
        {"toiture": "terrasse", "couverture": "dalle beton", "pente_toiture": 2,
         "maconnerie": "parpaing 15", "terrain_largeur": 18, "terrain_profondeur": 25},
    ),
    (
        "R+1 avec 5 chambres et 3 salles de bains",
        {"niveaux": 2, "chambres": 5, "salles_de_bain": 3},
    ),
    (
        "Villa 3 chambres sans climatisation, sans solaire, terrain 15x20",
        {"clim_chambres": False, "clim_sejour": False, "solaire": False},
    ),
    (
        "Maison 3 chambres, clim dans les chambres uniquement, terrain 15 x 20",
        {"clim_chambres": True, "clim_sejour": False},
    ),
    (
        "Maison 2 chambres, cuisinière, lave-vaisselle et chauffe-eau, terre 120 ohms",
        {"chambres": 2, "equipements": ["plaque", "lavevaisselle", "chauffeeau"], "resistance_terre": 120},
    ),
    (
        "Villa 4 chambres, séjour de 40 m², hauteur sous plafond 2,80 m, recul de 3 m",
        {"chambres": 4, "surface_sejour": 40, "hauteur_sous_plafond": 2.8, "recul": 3},
    ),
    (
        "Maison 3 chambres en tôle ondulée pente 20 %, WC dans la salle de bain",
        {"couverture": "tole ondulee", "pente_toiture": 20, "wc_separe": False},
    ),
    (
        "Maison 3 chambres, étude géotechnique : portance mesurée 0,25 MPa",
        {"portance_sol": 0.25, "portance_mesuree": True},
    ),
    (
        "Maison 3 chambres, sol 2 bars",
        {"portance_sol": 0.2, "portance_mesuree": False},
    ),
    (
        "Studio plain-pied, terrain 10 x 15, solaire avec autonomie de 8 h et ensoleillement 5 h",
        {"chambres": 0, "terrain_largeur": 10, "terrain_profondeur": 15, "solaire": True,
         "autonomie_h": 8, "ensoleillement_h": 5},
    ),
    (
        "Maison trois chambres sans pompe, devis en francs congolais",
        {"chambres": 3, "equipements": ["plaque", "four", "lavelinge", "chauffeeau"], "devise": "CDF"},
    ),
]


@pytest.mark.parametrize("texte,attendu", PHRASES, ids=[f"phrase-{i + 1:02d}" for i in range(len(PHRASES))])
def test_15_phrases(texte, attendu):
    p, _ = analyser(texte)
    obtenu = {k: getattr(p, k) for k in attendu}
    assert obtenu == attendu


def test_pas_de_donnee_de_terrain_inventee():
    p, remarques = analyser("Villa 3 chambres, terrain 15x20")
    assert p.resistance_terre is None
    assert p.portance_sol == 0.15 and p.portance_mesuree is False
    assert any("terre" in r.lower() for r in remarques)


def test_remarques_ambiguites():
    _, remarques = analyser("maison en tôle sur deux niveaux R+1")
    assert any("niveaux" in r for r in remarques)
    assert any("tôle" in r.lower() for r in remarques)
    assert any("terrain" in r.lower() for r in remarques)


def test_trop_de_chambres_borne():
    p, remarques = analyser("maison de 12 chambres")
    assert p.chambres == 8
    assert remarques
