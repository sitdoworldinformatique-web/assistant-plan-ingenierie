"""Connecteur Nano Banana, avec réponses HTTP simulées (aucun appel réseau)."""
import base64
import json
import logging

import httpx
import pytest

from apiconnect import nano_banana as nb
from apiconnect.erreurs import IAIndisponible, IANonConfiguree, ReponseInvalide

CLE = "AIza-test-NE-DOIT-JAMAIS-APPARAITRE"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
B64 = base64.b64encode(JPEG).decode()
PIECES = [{"nom": "Séjour", "largeur": 5.2, "profondeur": 4.8}, {"nom": "Chambre 1", "largeur": 3.5,
                                                                   "profondeur": 3.4, "surface": 11.9}]


def _client(*reponses, attentes=None):
    requetes = []
    file = list(reponses)

    def repondre(req):
        requetes.append(req)
        r = file.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    c = nb.ClientNanoBanana(api_key=CLE, modele="gemini-nano-banana-2.1",
                            client_http=httpx.Client(transport=httpx.MockTransport(repondre)),
                            dormir=(attentes.append if attentes is not None else lambda s: None))
    return c, requetes


def _ok(corps):
    return httpx.Response(200, json=corps)


REPONSE_STEPS = {"id": "int_1", "steps": [
    {"type": "thought", "content": [{"type": "text", "text": "…"}]},
    {"type": "model_output", "content": [{"type": "text", "text": "Voici"},
                                         {"type": "image", "mime_type": "image/png",
                                          "data": base64.b64encode(PNG).decode()},
                                         {"type": "image", "mime_type": "image/jpeg", "data": B64}]}]}


def test_sans_cle():
    with pytest.raises(IANonConfiguree):
        nb.ClientNanoBanana(api_key="")


def test_prompt_gabarit():
    p = nb.construire_prompt("perspective", PIECES, "2 pans, tôle bac acier")
    assert "Séjour : 5,20 m × 4,80 m (24,96 m²)" in p and "Chambre 1 : 3,50 m × 3,40 m (11,90 m²)" in p
    assert "conserver exactement la position et la forme des murs" in p
    assert "ne pas ajouter ni supprimer de pièce" in p and "aucun texte" in p and "tropical" in p
    assert "Toiture : 2 pans" in p and "véranda" in p
    assert "Toiture" not in nb.construire_prompt("plan_meuble", PIECES, "2 pans")
    with pytest.raises(ValueError):
        nb.construire_prompt("cubiste", PIECES)


def test_requete_et_reponse_steps(caplog):
    c, req = _client(_ok(REPONSE_STEPS))
    with caplog.at_level(logging.DEBUG):
        r = c.generer_rendu(base64.b64encode(PNG).decode(), "plan_meuble", PIECES, taille="2k")
    assert r.image == JPEG and r.mime_type == "image/jpeg" and r.modele == "gemini-nano-banana-2.1"
    assert str(req[0].url) == nb.URL_API and req[0].headers["x-goog-api-key"] == CLE
    corps = json.loads(req[0].content)
    assert corps["model"] == "gemini-nano-banana-2.1"
    assert corps["input"][0]["type"] == "text" and corps["input"][0]["text"] == r.prompt
    assert corps["input"][1] == {"type": "image", "mime_type": "image/png", "data": base64.b64encode(PNG).decode()}
    assert corps["response_format"] == {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "16:9",
                                        "image_size": "2K"}
    assert CLE not in caplog.text and CLE not in repr(c)


@pytest.mark.parametrize("corps", [
    {"output_image": {"data": B64, "mime_type": "image/jpeg"}},
    {"candidates": [{"content": {"parts": [{"text": "x"}, {"inlineData": {"mimeType": "image/jpeg", "data": B64}}]}}]},
    {"outputs": [{"type": "image", "data": B64}]},
    {"input": [{"type": "image", "data": base64.b64encode(PNG).decode()}], "outputs": [{"type": "image", "data": B64}]},
])
def test_analyseur_tolerant(corps):
    octets, mime = nb.extraire_image(corps)
    assert octets == JPEG and mime == "image/jpeg"


@pytest.mark.parametrize("corps", [{"steps": [{"type": "model_output", "content": [{"type": "text",
                                                                                     "text": "refus"}]}]},
                                   {}, {"steps": [{"content": [{"type": "image", "data": ""}]}]}])
def test_sans_image(corps):
    with pytest.raises(ReponseInvalide):
        nb.extraire_image(corps)


def test_reessaie_429_puis_succes():
    attentes = []
    c, req = _client(httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(503), _ok(REPONSE_STEPS),
                     attentes=attentes)
    assert c.generer_rendu("AAAA", "facade", PIECES).image == JPEG
    assert len(req) == 3 and attentes == [3.0, 2.0]


def test_indisponible_apres_trois_essais():
    c, req = _client(httpx.Response(500), httpx.ReadTimeout("lent"), httpx.Response(502))
    with pytest.raises(IAIndisponible) as e:
        c.generer_rendu("AAAA", "iso_coupe", PIECES)
    assert len(req) == 3
    assert e.value.message == "Le service d'images n'a pas répondu, réessayez dans une minute."


def test_erreur_client_sans_nouvelle_tentative():
    c, req = _client(httpx.Response(400, json={"error": {"message": "image_size invalide"}}))
    with pytest.raises(ReponseInvalide):
        c.generer_rendu("AAAA", "facade", PIECES)
    assert len(req) == 1


def test_aucune_cle_reelle_dans_le_depot():
    """Garde-fou : aucune clé Anthropic ou Google réelle dans les fichiers suivis."""
    import re
    import subprocess
    from pathlib import Path

    racine = Path(__file__).resolve().parents[3]
    try:
        fichiers = subprocess.run(["git", "ls-files"], cwd=racine, capture_output=True, text=True,
                                  check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("pas de dépôt git")
    motif = re.compile(r"sk-ant-(api|admin)\d{2}-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}")
    for f in fichiers:
        chemin = racine / f
        if chemin.suffix in (".png", ".jpg", ".ico") or not chemin.is_file():
            continue
        assert not motif.search(chemin.read_text(encoding="utf-8", errors="ignore")), f
