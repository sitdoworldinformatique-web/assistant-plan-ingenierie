"""Rendus Nano Banana : quotas, mention non contractuelle, erreurs, avec un service d'images simulé."""
import base64
import io
import json

import httpx
import pytest
from apiconnect import nano_banana
from apiconnect.erreurs import IAIndisponible
from fastapi.testclient import TestClient
from PIL import Image

from app import ia
from app.main import app
from app.rendu import images


def _png(l=400, h=300, couleur=(255, 255, 255)) -> bytes:
    t = io.BytesIO()
    Image.new("RGB", (l, h), couleur).save(t, format="PNG")
    return t.getvalue()


def _jpeg(l=320, h=180) -> bytes:
    t = io.BytesIO()
    Image.new("RGB", (l, h), (120, 160, 200)).save(t, format="JPEG")
    return t.getvalue()


PLAN = base64.b64encode(_png()).decode()


class FauxImages:
    modele = "image-simulee"

    def __init__(self, erreur=None):
        self.appels = []
        self.erreur = erreur

    def generer_rendu(self, image_b64, style, pieces, toiture=None):
        self.appels.append({"image": image_b64, "style": style, "pieces": pieces, "toiture": toiture})
        if self.erreur:
            raise self.erreur
        return nano_banana.Rendu(image=_jpeg(), mime_type="image/jpeg", prompt=nano_banana.construire_prompt(
            style, pieces, toiture), modele=self.modele)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STOCKAGE_RENDUS", str(tmp_path / "rendus"))
    monkeypatch.setenv("RENDUS_MAX_PAR_JOUR", "2")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def projet(client):
    r = client.post("/api/auth/inscription", json={"email": "b@exemple.cd", "mot_de_passe": "motdepasse123",
                                                   "nom": "B"})
    h = {"Authorization": f"Bearer {r.json()['jeton']}"}
    p = client.post("/api/projets/generer", json={"programme": {"terrain_largeur": 18, "toiture": "4 pans"}},
                    headers=h).json()
    return p["id"], h


def test_sans_cle_message_clair(client, projet):
    pid, h = projet
    liste = client.get(f"/api/projets/{pid}/rendus", headers=h).json()
    assert liste["ia_image_configuree"] is False and liste["quota"] == {"max": 2, "utilises": 0}
    assert set(liste["styles"]) == {"plan_meuble", "iso_coupe", "facade", "perspective", "realiste"}
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "facade", "image_base64": PLAN}, headers=h)
    assert r.status_code == 503 and r.json()["code"] == "ia_image_non_configuree"


def test_rendu_complet_mention_et_quota(client, projet, tmp_path):
    pid, h = projet
    faux = FauxImages()
    app.dependency_overrides[ia.client_image] = lambda: faux
    r = client.post(f"/api/projets/{pid}/rendus",
                    json={"style": "perspective", "image_base64": "data:image/png;base64," + PLAN}, headers=h)
    assert r.status_code == 201, r.text
    rendu = r.json()
    assert rendu["libelle"] == "Perspective extérieure" and rendu["mention"].startswith("Image de présentation")
    appel = faux.appels[0]
    assert appel["image"] == PLAN and appel["toiture"].startswith("4 pans")
    sejour = next(x for x in appel["pieces"] if x["nom"] == "Séjour")
    assert sejour["largeur"] > 3 and sejour["surface"] > 20

    img = client.get(rendu["url"], headers=h)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(img.content)) as im:
        assert im.size[0] == 320 and im.size[1] > 180  # bandeau ajouté sous l'image
        bas = im.convert("RGB").getpixel((2, im.size[1] - 2))
        assert sum(bas) < 150  # bandeau sombre
    assert client.get(rendu["url"]).status_code == 401

    detail = client.get(f"/api/projets/{pid}", headers=h).json()
    assert detail["journal_ia"][-1]["etape"] == "rendre" and detail["journal_ia"][-1]["modele"] == "image-simulee"

    assert client.post(f"/api/projets/{pid}/rendus", json={"style": "facade", "image_base64": PLAN},
                       headers=h).status_code == 201
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "facade", "image_base64": PLAN}, headers=h)
    assert r.status_code == 429 and r.json()["code"] == "quota_atteint"
    liste = client.get(f"/api/projets/{pid}/rendus", headers=h).json()
    assert len(liste["rendus"]) == 2 and liste["quota"]["utilises"] == 2

    # Suppression d'un rendu, puis du projet : les fichiers disparaissent
    assert client.delete(f"/api/projets/{pid}/rendus/{rendu['id']}", headers=h).status_code == 204
    assert client.get(rendu["url"], headers=h).status_code == 404
    assert len(list((tmp_path / "rendus" / str(pid)).iterdir())) == 1
    assert client.delete(f"/api/projets/{pid}", headers=h).status_code == 204
    assert list((tmp_path / "rendus" / str(pid)).iterdir()) == []


@pytest.mark.parametrize("corps,code", [
    ({"style": "cubiste", "image_base64": PLAN}, "style_inconnu"),
    ({"style": "facade", "image_base64": base64.b64encode(_jpeg()).decode()}, "image_invalide"),
    ({"style": "facade", "image_base64": "pas du base64 !!!"}, "image_invalide"),
    ({"style": "facade", "image_base64": base64.b64encode(_png(20, 20)).decode()}, "image_invalide"),
])
def test_demandes_invalides(client, projet, corps, code):
    pid, h = projet
    app.dependency_overrides[ia.client_image] = lambda: FauxImages()
    r = client.post(f"/api/projets/{pid}/rendus", json=corps, headers=h)
    assert r.status_code == 422 and r.json()["code"] == code


def test_service_indisponible(client, projet):
    pid, h = projet
    app.dependency_overrides[ia.client_image] = lambda: FauxImages(erreur=IAIndisponible())
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "facade", "image_base64": PLAN}, headers=h)
    assert r.status_code == 503
    assert r.json()["message"] == "Le service d'images n'a pas répondu, réessayez dans une minute."
    assert client.get(f"/api/projets/{pid}/rendus", headers=h).json()["quota"]["utilises"] == 0
    assert client.get(f"/api/projets/{pid}", headers=h).json()["journal_ia"][-1]["erreur"] is True


def test_chaine_complete_avec_le_vrai_connecteur(client, projet):
    """API → ClientNanoBanana → HTTP simulé : vérifie la requête Gemini réellement émise."""
    pid, h = projet
    requetes = []

    def repondre(req):
        requetes.append(json.loads(req.content))
        return httpx.Response(200, json={"steps": [{"type": "model_output", "content": [
            {"type": "image", "mime_type": "image/jpeg", "data": base64.b64encode(_jpeg(640, 360)).decode()}]}]})

    vrai = nano_banana.ClientNanoBanana(api_key="AIza-test", client_http=httpx.Client(
        transport=httpx.MockTransport(repondre)))
    app.dependency_overrides[ia.client_image] = lambda: vrai
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "plan_meuble", "image_base64": PLAN}, headers=h)
    assert r.status_code == 201, r.text
    corps = requetes[0]
    assert corps["model"] == "gemini-nano-banana-2.1" and corps["input"][1]["data"] == PLAN
    assert "Séjour" in corps["input"][0]["text"] and "ne pas ajouter ni supprimer de pièce" in corps["input"][0]["text"]


def test_mention_sur_plusieurs_lignes_si_image_etroite():
    large = Image.open(io.BytesIO(images.ajouter_mention(_jpeg(2000, 1000))))
    etroite = Image.open(io.BytesIO(images.ajouter_mention(_jpeg(200, 100))))
    assert large.format == "JPEG" and etroite.size[0] == 200
    assert large.size[1] - 1000 == round(2000 / 70 * 1.25) + 2 * round(2000 / 70 * 0.6)  # une seule ligne
    assert etroite.size[1] - 100 >= 3 * round(12 * 1.25)  # au moins trois lignes, rien de coupé


def test_stockage_supabase_ecriture_lecture_suppression(client, projet, monkeypatch):
    """Avec SUPABASE_URL et la clé service_role, l'image part dans le bucket privé, pas sur le disque."""
    from app.rendu import fichiers

    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "cle-service-secrete")
    monkeypatch.setenv("SUPABASE_BUCKET", "rendus")
    objets: dict[str, bytes] = {}
    vus: list[httpx.Request] = []

    def stockage(req: httpx.Request) -> httpx.Response:
        vus.append(req)
        chemin = req.url.path.removeprefix("/storage/v1/object/rendus/")
        if req.method == "POST":
            objets[chemin] = req.content
            return httpx.Response(200, json={"Key": chemin})
        if req.method == "GET":
            return httpx.Response(200, content=objets[chemin]) if chemin in objets else httpx.Response(404)
        objets.pop(chemin, None)
        return httpx.Response(200, json={})

    monkeypatch.setattr(fichiers, "_client", lambda: httpx.Client(transport=httpx.MockTransport(stockage)))
    pid, h = projet
    app.dependency_overrides[ia.client_image] = lambda: FauxImages()
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "realiste", "image_base64": PLAN}, headers=h)
    assert r.status_code == 201, r.text
    assert len(objets) == 1 and next(iter(objets)).startswith(f"{pid}/")
    assert all(v.headers["authorization"] == "Bearer cle-service-secrete" for v in vus)
    assert objets[next(iter(objets))][:2] == b"\xff\xd8"  # JPEG avec mention

    img = client.get(r.json()["url"], headers=h)
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
    assert client.get(r.json()["url"]).status_code == 401  # l'image n'est jamais publique

    assert client.delete(f"/api/projets/{pid}/rendus/{r.json()['id']}", headers=h).status_code == 204
    assert objets == {}


def test_stockage_supabase_en_panne(client, projet, monkeypatch):
    from app.rendu import fichiers

    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "cle")
    monkeypatch.setattr(fichiers, "_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(500))))
    pid, h = projet
    app.dependency_overrides[ia.client_image] = lambda: FauxImages()
    r = client.post(f"/api/projets/{pid}/rendus", json={"style": "facade", "image_base64": PLAN}, headers=h)
    assert r.status_code == 503 and r.json()["code"] == "stockage_indisponible"
    assert client.get(f"/api/projets/{pid}/rendus", headers=h).json()["rendus"] == []
