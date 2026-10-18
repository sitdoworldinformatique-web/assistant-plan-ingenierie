from fastapi.testclient import TestClient

from app.main import app


def test_sante():
    r = TestClient(app).get("/api/sante")
    assert r.status_code == 200
    corps = r.json()
    assert corps["etat"] == "ok"
    assert "version_moteurs" in corps
    assert isinstance(corps["ia_texte_configuree"], bool)
