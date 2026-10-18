import pytest
from fastapi.testclient import TestClient

from app import ia, stockage
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@exemple.cd")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _compte(client, email, nom="Test", role=None, admin=None):
    r = client.post("/api/auth/inscription", json={"email": email, "mot_de_passe": "motdepasse123", "nom": nom})
    assert r.status_code == 201, r.text
    corps = r.json()
    if role:
        uid = corps["utilisateur"]["id"]
        r = client.put(f"/api/admin/utilisateurs/{uid}", json={"role": role, "numero_ordre": "ONI-0042"},
                       headers=admin)
        assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {corps['jeton']}"}


@pytest.fixture
def comptes(client):
    admin = _compte(client, "admin@exemple.cd", "Admin")
    constructeur = _compte(client, "batisseur@exemple.cd", "Bâtisseur")
    ingenieur = _compte(client, "ing@exemple.cd", "Ir. Mukendi", role="ingenieur", admin=admin)
    return {"admin": admin, "constructeur": constructeur, "ingenieur": ingenieur}


def test_sante(client):
    r = client.get("/api/sante")
    assert r.status_code == 200
    corps = r.json()
    assert corps["etat"] == "ok" and corps["ia_texte_configuree"] is False and "version_moteurs" in corps


def test_auth(client, comptes):
    assert client.get("/api/auth/moi", headers=comptes["admin"]).json()["role"] == "admin"
    assert client.get("/api/auth/moi", headers=comptes["constructeur"]).json()["role"] == "constructeur"
    r = client.post("/api/auth/connexion", json={"email": "batisseur@exemple.cd", "mot_de_passe": "faux"})
    assert r.status_code == 401 and r.json() == {"code": "identifiants_invalides",
                                                 "message": "Email ou mot de passe incorrect."}
    r = client.post("/api/auth/connexion", json={"email": "BATISSEUR@exemple.cd", "mot_de_passe": "motdepasse123"})
    assert r.status_code == 200 and r.json()["jeton"]
    assert client.get("/api/projets").status_code == 401
    r = client.post("/api/auth/inscription", json={"email": "batisseur@exemple.cd", "mot_de_passe": "motdepasse123",
                                                   "nom": "x"})
    assert r.status_code == 409


def test_erreur_validation_en_francais(client, comptes):
    r = client.post("/api/projets/generer", json={"programme": {"chambres": 20}}, headers=comptes["constructeur"])
    assert r.status_code == 422 and r.json()["code"] == "donnees_invalides"


def test_interpreter_sans_cle(client, comptes):
    r = client.post("/api/ia/interpreter", json={"texte": "villa 4 chambres, terrain 20x25"},
                    headers=comptes["constructeur"])
    assert r.status_code == 200
    assert r.json()["programme"]["chambres"] == 4 and r.json()["source"] == "analyseur-par-regles"


def test_parcours_generer_modifier_valider_modifier(client, comptes):
    """générer → modifier → valider → modifier (validation annulée)."""
    c, i = comptes["constructeur"], comptes["ingenieur"]
    texte = ("Villa plain-pied, 3 chambres, 1 salle de bain, WC séparé, cuisine fermée, véranda, terrain 15×20, "
             "toiture 2 pans en tôle bac acier, parpaing 20, résistance de terre 45 Ω.")
    r = client.post("/api/projets/generer", json={"texte": texte}, headers=c)
    assert r.status_code == 201, r.text
    projet = r.json()
    pid = projet["id"]
    assert projet["statut"] == "bloque"  # emprise trop large (sans IA : pas d'auto-correction)
    assert projet["journal_ia"][0]["modele"] == "analyseur-par-regles"
    assert projet["resultats"]["implantation"]["pieces"]

    # Validation refusée tant que le module implantation a un bloquant
    r = client.post(f"/api/projets/{pid}/validations", json={"module": "implantation"}, headers=i)
    assert r.status_code == 409 and r.json()["code"] == "module_bloque"

    # Modifier : terrain plus large → plus de bloquant
    prog = {**projet["programme"], "terrain_largeur": 18}
    r = client.put(f"/api/projets/{pid}/programme", json=prog, headers=c)
    assert r.status_code == 200
    projet = r.json()
    assert projet["statut"] == "conforme_avec_reserves" and projet["version"] == 2
    empreinte_1 = projet["empreinte"]

    # Valider (ingénieur) ; le constructeur ne peut pas
    assert client.post(f"/api/projets/{pid}/validations", json={"module": "electricite"},
                       headers=c).status_code == 403
    r = client.post(f"/api/projets/{pid}/validations", json={"module": "implantation", "commentaire": "RAS"},
                    headers=i)
    assert r.status_code == 201
    v = r.json()
    assert v["encore_valide"] and v["empreinte"] == empreinte_1 and v["nom"] == "Ir. Mukendi"
    assert v["numero_ordre"] == "ONI-0042"
    etat = client.get(f"/api/projets/{pid}/validations", headers=c).json()
    assert etat["modules"]["implantation"] is True and etat["modules"]["structure"] is False
    assert "Signé par Ir. Mukendi" in client.get(f"/api/projets/{pid}/plan.svg", headers=c).text

    # Modifier à nouveau : la validation est annulée
    prog["chambres"] = 2
    projet = client.put(f"/api/projets/{pid}/programme", json=prog, headers=c).json()
    assert projet["empreinte"] != empreinte_1
    etat = client.get(f"/api/projets/{pid}/validations", headers=c).json()
    assert etat["modules"]["implantation"] is False
    assert etat["validations"][0]["encore_valide"] is False
    assert "À valider par un ingénieur" in client.get(f"/api/projets/{pid}/plan.svg", headers=c).text


def test_empreinte_stable_meme_programme(client, comptes):
    c = comptes["constructeur"]
    p1 = client.post("/api/projets/generer", json={"programme": {"terrain_largeur": 18}}, headers=c).json()
    p2 = client.post("/api/projets/generer", json={"programme": {"terrain_largeur": 18}}, headers=c).json()
    assert p1["empreinte"] == p2["empreinte"] and len(p1["empreinte"]) == 64


def test_droits_acces(client, comptes):
    c = comptes["constructeur"]
    autre = _compte(client, "autre@exemple.cd")
    pid = client.post("/api/projets/generer", json={"programme": {}}, headers=c).json()["id"]
    assert client.get(f"/api/projets/{pid}", headers=autre).status_code == 403
    assert client.get("/api/projets", headers=autre).json() == []
    assert client.get(f"/api/projets/{pid}", headers=comptes["ingenieur"]).status_code == 200
    assert client.put(f"/api/projets/{pid}/programme", json={}, headers=comptes["ingenieur"]).status_code == 403
    assert client.delete(f"/api/projets/{pid}", headers=autre).status_code == 403
    assert client.delete(f"/api/projets/{pid}", headers=c).status_code == 204
    assert client.get(f"/api/projets/{pid}", headers=c).status_code == 404


def test_exports_svg_et_rapport(client, comptes):
    c = comptes["constructeur"]
    pid = client.post("/api/projets/generer", json={"programme": {"terrain_largeur": 18, "resistance_terre": 30}},
                      headers=c).json()["id"]
    r = client.get(f"/api/projets/{pid}/plan.svg?calques=murs,cotes,elec", headers=c)
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "calque-elec" in r.text and "calque-textes" not in r.text
    assert client.get(f"/api/projets/{pid}/plan.svg?calques=inconnu", headers=c).status_code == 422
    r = client.get(f"/api/projets/{pid}/unifilaire.svg", headers=c)
    assert r.status_code == 200 and "ID1" in r.text
    r = client.get(f"/api/projets/{pid}/rapport.txt", headers=c)
    assert r.status_code == 200 and "À valider par un ingénieur qualifié" in r.text


def test_admin_prix(client, comptes):
    a, c = comptes["admin"], comptes["constructeur"]
    assert client.get("/api/admin/prix", headers=c).status_code == 403
    prix = client.get("/api/admin/prix", headers=a).json()
    assert any(p["code"] == "ciment" for p in prix)
    r = client.put("/api/admin/prix", json=[{"code": "ciment", "prix": 13.5}], headers=a)
    assert next(p for p in r.json() if p["code"] == "ciment")["prix"] == 13.5
    projet = client.post("/api/projets/generer", json={"programme": {}}, headers=c).json()
    ligne = next(lg for lg in projet["resultats"]["metre"]["lignes"] if lg["code"] == "ciment")
    assert ligne["prix_unitaire"] == 13.5


def test_openapi(client):
    assert client.get("/api/docs").status_code == 200
    assert "/api/projets/generer" in client.get("/api/openapi.json").json()["paths"]


def test_dependance_ia_remplacable(client, comptes):
    class Faux:
        modele = "faux-modele"

        def interpreter(self, texte, schema):
            return {"chambres": 5, "remarques": ["ambigu : nombre de salles de bain"]}

    app.dependency_overrides[ia.client_texte] = lambda: Faux()
    r = client.post("/api/ia/interpreter", json={"texte": "maison"}, headers=comptes["constructeur"])
    assert r.json()["programme"]["chambres"] == 5 and r.json()["source"] == "faux-modele"
    assert "ambigu : nombre de salles de bain" in r.json()["remarques"]
    assert stockage is not None
