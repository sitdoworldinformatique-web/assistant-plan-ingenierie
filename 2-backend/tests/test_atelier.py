"""Atelier : volumes 3D, élévations SVG et commandes en langage naturel."""
import xml.dom.minidom

import pytest
from test_api import client, comptes  # noqa: F401  (fixtures partagées)
from test_orchestrateur import FausseIA

from app import orchestrateur
from app.moteurs import chaine, commandes
from app.moteurs.programme import Programme, analyser
from app.rendu import elevation_svg, volumes

TEXTES = {
    "4pans": "Villa 3 chambres, toiture 4 pans en tuiles, terrain 25 x 30",
    "2pans_garage": "Maison 2 chambres avec garage, toiture 2 pans en tuiles, terrain 25 x 30",
    "terrasse": "Maison 3 chambres toit terrasse terrain 25 x 30",
}


def _calcul(cle):
    p, _ = analyser(TEXTES[cle])
    return p, chaine.calculer(p)


@pytest.mark.parametrize("cle", TEXTES)
def test_volumes_coherents(cle):
    p, r = _calcul(cle)
    v = volumes.construire(r, p)
    hm = r.structure.hauteur_mur
    murs = [b for b in v["boites"] if b["t"] == "mur_ext"]
    assert murs and max(b["z"] + b["dz"] for b in murs) == pytest.approx(hm)
    # les semelles sont sous le terrain naturel, à l'assise normative
    semelles = [b for b in v["boites"] if b["t"] == "semelle"]
    assert len(semelles) == len(r.structure.semelles)
    assert min(b["z"] for b in semelles) == pytest.approx(v["niveaux"]["assise"])
    assert v["niveaux"]["assise"] < v["niveaux"]["terrain"] < 0 < hm <= v["niveaux"]["haut"]
    # la maison tient dans le terrain
    t, em = v["terrain"], v["emprise"]
    assert t["x"] <= em["x_min"] and em["x_max"] <= t["x"] + t["l"]
    assert t["y"] <= em["y_min"] and em["y_max"] <= t["y"] + t["p"]
    # toutes les ouvertures de l'implantation sont percées : une vitre ou un vantail par fenêtre ou porte
    n_ouv = sum(1 for o in r.implantation.ouvertures if o.type in ("fenetre", "porte"))
    assert sum(1 for b in v["boites"] if b["t"] in ("vitre", "porte")) == n_ouv


def test_volumes_toiture_selon_le_type():
    p, r = _calcul("4pans")
    v = volumes.construire(r, p)
    assert sum(1 for f in v["faces"] if f["t"] == "toit") == 4
    assert v["niveaux"]["haut"] > v["niveaux"]["haut_mur"]
    # faîtage = haut des murs + pente × demi-portée (pente en %, portée à l'axe)
    demi = min(r.implantation.parametres["largeur_axe"], r.implantation.parametres["profondeur_axe"]) / 2
    assert v["niveaux"]["haut"] - v["niveaux"]["haut_mur"] == pytest.approx(
        r.toiture.pente / 100 * (demi + r.toiture.debord / 2), abs=0.35)
    p2, r2 = _calcul("2pans_garage")
    v2 = volumes.construire(r2, p2)
    assert sum(1 for f in v2["faces"] if f["t"] == "pignon") == 4  # deux pignons par bloc (maison, garage)
    p3, r3 = _calcul("terrasse")
    v3 = volumes.construire(r3, p3)
    assert not [f for f in v3["faces"] if f["t"] == "toit"]
    assert any(b["t"] == "acrotere" for b in v3["boites"])


@pytest.mark.parametrize("cle", TEXTES)
@pytest.mark.parametrize("vue", elevation_svg.VUES)
def test_elevation_svg_valide(cle, vue):
    p, r = _calcul(cle)
    svg = elevation_svg.rendre_elevation(r, p, vue)
    xml.dom.minidom.parseString(svg)  # XML bien formé
    assert elevation_svg.TITRES[vue] in svg
    assert "±0,00 plancher fini" in svg and "assise des semelles" in svg
    assert "non contractuelle" in svg


def test_elevation_vue_inconnue():
    p, r = _calcul("4pans")
    with pytest.raises(ValueError):
        elevation_svg.rendre_elevation(r, p, "dessus")


def _prog(texte="Villa 3 chambres, terrain 25 x 30, toiture 2 pans"):
    return analyser(texte)[0]


@pytest.mark.parametrize("commande,champ,valeur", [
    ("ajoute une chambre", "chambres", 4),
    ("Ajoute 2 chambres en plus", "chambres", 5),
    ("supprime une chambre", "chambres", 2),
    ("passe à 5 chambres", "chambres", 5),
    ("supprime la véranda", "veranda", False),
    ("ajoute un garage", "garage", True),
    ("toiture 4 pans en tuiles", "toiture", "4 pans"),
    ("mets un toit terrasse", "couverture", "dalle beton"),
    ("terrain 20 x 25", "terrain_largeur", 20.0),
    ("résistance de terre 20 ohms", "resistance_terre", 20.0),
    ("supprime la clim", "clim_sejour", False),
    ("agrandis le séjour de 5 m²", "surface_sejour", 33.0),
    ("réduis le séjour de 3 m2", "surface_sejour", 25.0),
])
def test_commandes_regles(commande, champ, valeur):
    nouveau, changements, _ = commandes.appliquer(_prog(), commande, surface_sejour_actuelle=28.0)
    assert getattr(nouveau, champ) == valeur
    assert changements and all(c.avant != c.apres for c in changements)


def test_commande_incomprise_ne_change_rien():
    courant = _prog()
    nouveau, changements, remarques = commandes.appliquer(courant, "fais-moi un café")
    assert nouveau == courant and not changements and "non comprise" in remarques[0]


def test_commande_retour_a_une_toiture_avec_dalle():
    terrasse = _prog("Maison 3 chambres toit terrasse terrain 25 x 30")
    nouveau, _, _ = commandes.appliquer(terrasse, "toiture 2 pans")
    assert nouveau.couverture == "tole bac acier" and nouveau.toiture == "2 pans"


def test_commande_ia_ne_touche_jamais_aux_donnees_de_terrain():
    courant = _prog("Villa 3 chambres terrain 25 x 30 terre 20 ohms")
    ia = FausseIA(interpretations=[{**courant.model_dump(mode="json"), "chambres": 4, "resistance_terre": 3.0,
                                    "portance_sol": 0.9, "portance_mesuree": True, "remarques": ["ok"]}])
    prog, changements, remarques, source = orchestrateur.commander("ajoute une chambre", courant, None, ia,
                                                                    orchestrateur.Journal())
    assert source == "ia" and prog.chambres == 4
    assert prog.resistance_terre == 20.0 and prog.portance_sol == courant.portance_sol
    assert [c.champ for c in changements] == ["chambres"] and remarques == ["ok"]


def test_commande_ia_en_panne_retombe_sur_les_regles():
    courant = _prog()
    ia = FausseIA(interpretations=[RuntimeError("hors ligne")])
    journal = orchestrateur.Journal()
    prog, _, _, source = orchestrateur.commander("ajoute une chambre", courant, None, ia, journal)
    assert source == "regles" and prog.chambres == 4 and journal.entrees[-1]["erreur"] is True


def test_api_atelier(client, comptes):  # noqa: F811
    h = comptes["constructeur"]
    p = client.post("/api/projets/generer", json={"texte": TEXTES["4pans"]}, headers=h).json()
    pid = p["id"]
    # élévations et 3D
    for vue in ("facade", "pignon"):
        r = client.get(f"/api/projets/{pid}/elevation.svg?vue={vue}", headers=h)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert client.get(f"/api/projets/{pid}/elevation.svg?vue=dessus", headers=h).status_code == 422
    m = client.get(f"/api/projets/{pid}/modele3d.json", headers=h).json()
    assert m["boites"] and m["niveaux"]["plancher"] == 0 and "non contractuel" in m["mention"]
    assert client.get(f"/api/projets/{pid}/modele3d.json").status_code == 401
    # commande : une étape, recalcul complet, version + 1, journal avec l'état d'avant
    r = client.post(f"/api/projets/{pid}/commande", json={"texte": "ajoute une chambre"}, headers=h)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["programme"]["chambres"] == 4 and c["version"] == p["version"] + 1
    assert c["commande"]["comprise"] and c["commande"]["changements"][0]["champ"] == "chambres"
    assert "Chambres : 3 → 4" in c["commande"]["message"]
    dernier = c["journal_ia"][-1]
    assert dernier["etape"] == "commande" and dernier["programme_avant"]["chambres"] == 3
    assert any(x["id"] == "CH4" for x in c["resultats"]["implantation"]["pieces"])
    # commande incomprise : rien ne change
    r = client.post(f"/api/projets/{pid}/commande", json={"texte": "fais-moi un café"}, headers=h)
    assert r.json()["commande"]["comprise"] is False and r.json()["version"] == c["version"]
    # un autre constructeur n'y a pas accès
    autre = {"Authorization": "Bearer " + client.post("/api/auth/inscription", json={
        "email": "autre@exemple.cd", "mot_de_passe": "motdepasse123", "nom": "Autre"}).json()["jeton"]}
    assert client.post(f"/api/projets/{pid}/commande", json={"texte": "ajoute une chambre"}, headers=autre
                       ).status_code == 403


def test_commande_annule_les_validations(client, comptes):  # noqa: F811
    h, ing = comptes["constructeur"], comptes["ingenieur"]
    prog = Programme(**{**analyser(TEXTES["4pans"])[0].model_dump(), "resistance_terre": 20.0}).model_dump()
    p = client.post("/api/projets/generer", json={"programme": prog}, headers=h).json()
    pid = p["id"]
    assert client.post(f"/api/projets/{pid}/validations", json={"module": "electricite"}, headers=ing).status_code == 201
    assert client.get(f"/api/projets/{pid}/validations", headers=h).json()["modules"]["electricite"] is True
    client.post(f"/api/projets/{pid}/commande", json={"texte": "ajoute une chambre"}, headers=h)
    v = client.get(f"/api/projets/{pid}/validations", headers=h).json()
    assert v["validations"] and not any(x["encore_valide"] for x in v["validations"])
    assert v["modules"]["electricite"] is False


def test_api_annuler_la_derniere_etape(client, comptes):  # noqa: F811
    h = comptes["constructeur"]
    p = client.post("/api/projets/generer", json={"texte": TEXTES["4pans"]}, headers=h).json()
    pid = p["id"]
    r = client.post(f"/api/projets/{pid}/commande", json={"texte": "annule"}, headers=h).json()
    assert r["commande"]["comprise"] is False and "aucune étape" in r["commande"]["message"]
    client.post(f"/api/projets/{pid}/commande", json={"texte": "ajoute une chambre"}, headers=h)
    client.post(f"/api/projets/{pid}/commande", json={"texte": "supprime la véranda"}, headers=h)
    r = client.post(f"/api/projets/{pid}/commande", json={"texte": "annule la dernière étape"}, headers=h).json()
    assert r["commande"]["comprise"] and "annulée" in r["commande"]["message"]
    assert r["programme"]["veranda"] is True and r["programme"]["chambres"] == 4
    r = client.post(f"/api/projets/{pid}/commande", json={"texte": "annule"}, headers=h).json()
    assert r["programme"]["chambres"] == 3  # la deuxième annulation remonte à l'étape précédente
    journal = [e for e in r["journal_ia"] if e["etape"] == "commande"]
    assert [bool(e.get("annulee")) for e in journal[:2]] == [True, True]
