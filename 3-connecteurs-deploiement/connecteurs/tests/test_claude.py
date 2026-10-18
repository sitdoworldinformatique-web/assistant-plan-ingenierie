"""Connecteur Claude, avec réponses simulées (aucun appel réseau)."""
import json
import logging
from types import SimpleNamespace

import anthropic
import pytest

try:  # le SDK anthropic récent s'appuie sur httpx2, les versions plus anciennes sur httpx
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

from apiconnect import claude
from apiconnect.erreurs import IAIndisponible, IANonConfiguree, ReponseInvalide

CLE = "sk-ant-test-NE-DOIT-JAMAIS-APPARAITRE"
SCHEMA = {
    "type": "object", "additionalProperties": False, "title": "Programme",
    "properties": {"chambres": {"type": "integer", "default": 3},
                   "toiture": {"$ref": "#/$defs/Toiture"},
                   "portance_sol": {"type": "number", "default": 0.15}},
    "$defs": {"Toiture": {"enum": ["2 pans", "4 pans", "terrasse"], "type": "string"}},
}


class FauxMessages:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def create(self, **kwargs):
        self.appels.append(kwargs)
        r = self.reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _client(*reponses):
    faux = SimpleNamespace(messages=FauxMessages(reponses))
    return claude.ClientClaude(modele="claude-test", client=faux), faux.messages


def _outil(nom, entree):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text="…"),
                                    SimpleNamespace(type="tool_use", name=nom, input=entree)])


def _texte(t):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=t)])


def _http_erreur(cls, statut):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("erreur", response=httpx.Response(statut, request=req), body=None)


def test_sans_cle_refuse():
    with pytest.raises(IANonConfiguree):
        claude.ClientClaude(api_key="")


def test_interpreter_outil_force_et_schema():
    c, m = _client(_outil("definir_programme", {"chambres": 4, "remarques": ["Surface du séjour non précisée."]}))
    sortie = c.interpreter("Villa 4 chambres", SCHEMA)
    assert sortie == {"chambres": 4, "remarques": ["Surface du séjour non précisée."]}
    appel = m.appels[0]
    assert appel["model"] == "claude-test"
    assert appel["tool_choice"] == {"type": "tool", "name": "definir_programme"}
    schema = appel["tools"][0]["input_schema"]
    assert schema["properties"]["remarques"]["type"] == "array"
    assert schema["$defs"]["Toiture"]["enum"][0] == "2 pans"
    assert "remarques" not in SCHEMA["properties"]  # le schéma d'origine n'est pas modifié
    assert "N'invente jamais de données de terrain" in appel["system"]
    assert appel["messages"] == [{"role": "user", "content": "Villa 4 chambres"}]


def test_interpreter_sans_appel_outil():
    c, _ = _client(_texte("Je ne sais pas"))
    with pytest.raises(ReponseInvalide) as e:
        c.interpreter("x", SCHEMA)
    assert isinstance(e.value, ValueError)  # l'orchestrateur la traite comme une sortie invalide


def test_interpreter_entree_json_texte_et_remarques_non_liste():
    c, _ = _client(_outil("definir_programme", json.dumps({"chambres": 2, "remarques": "ambigu"})))
    assert c.interpreter("x", SCHEMA) == {"chambres": 2, "remarques": ["ambigu"]}


def test_corriger_preserve_le_terrain():
    prog = {"chambres": 3, "portance_sol": 0.15, "portance_mesuree": False, "resistance_terre": None}
    propose = {"programme": {"chambres": 2, "portance_sol": 0.3, "portance_mesuree": True, "resistance_terre": 5},
               "explication": "Une chambre de moins pour tenir dans le terrain.", "champs_modifies": ["chambres"]}
    c, m = _client(_outil("corriger_programme", propose))
    sortie = c.corriger(prog, [{"id": "IMPL-EMPRISE-L", "niveau": "bloquant"}], SCHEMA)
    assert sortie["programme"] == {"chambres": 2, "portance_sol": 0.15, "portance_mesuree": False,
                                   "resistance_terre": None}
    assert sortie["explication"].startswith("Une chambre")
    appel = m.appels[0]
    assert appel["tool_choice"] == {"type": "tool", "name": "corriger_programme"}
    schema = appel["tools"][0]["input_schema"]
    assert set(schema["required"]) == {"programme", "explication", "champs_modifies"}
    assert schema["$defs"]["Toiture"]  # $defs remontés à la racine
    assert schema["properties"]["programme"]["properties"]["toiture"] == {"$ref": "#/$defs/Toiture"}
    assert "IMPL-EMPRISE-L" in appel["messages"][0]["content"]


def test_corriger_sans_programme():
    c, _ = _client(_outil("corriger_programme", {"explication": "rien"}))
    with pytest.raises(ReponseInvalide):
        c.corriger({}, [], SCHEMA)


def test_expliquer_limite_120_mots():
    long = " ".join(["mot"] * 200)
    c, m = _client(_texte("Ce circuit est en 2,5 mm²."), _texte(long))
    assert c.expliquer({"id": "C4"}) == "Ce circuit est en 2,5 mm²."
    assert "tools" not in m.appels[0] and "120 mots" in m.appels[0]["system"]
    tronque = c.expliquer({"id": "C4"})
    assert len(tronque.split()) == 120 and tronque.endswith("…")


def test_expliquer_vide():
    c, _ = _client(_texte("  "))
    with pytest.raises(ReponseInvalide):
        c.expliquer({})


@pytest.mark.parametrize("erreur,attendue", [
    (lambda: _http_erreur(anthropic.RateLimitError, 429), IAIndisponible),
    (lambda: _http_erreur(anthropic.InternalServerError, 500), IAIndisponible),
    (lambda: _http_erreur(anthropic.AuthenticationError, 401), IANonConfiguree),
    (lambda: _http_erreur(anthropic.BadRequestError, 400), ReponseInvalide),
    (lambda: anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
     IAIndisponible),
])
def test_erreurs_traduites(erreur, attendue):
    c, _ = _client(erreur())
    with pytest.raises(attendue):
        c.interpreter("x", SCHEMA)


def test_vrai_sdk_transport_simule_sans_fuite_de_cle(caplog):
    """Le vrai SDK, branché sur un transport simulé : vérifie la requête HTTP réellement émise."""
    requetes = []

    def repondre(req: httpx.Request) -> httpx.Response:
        requetes.append(req)
        if len(requetes) == 1:
            return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error",
                                                                         "message": "surchargé"}})
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-test",
            "stop_reason": "tool_use", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "content": [{"type": "tool_use", "id": "toolu_1", "name": "definir_programme",
                         "input": {"chambres": 5, "remarques": []}}]})

    sdk = anthropic.Anthropic(api_key=CLE, max_retries=2,
                              http_client=httpx.Client(transport=httpx.MockTransport(repondre)))
    sdk._calculate_retry_timeout = lambda *a, **k: 0  # pas d'attente réelle dans les tests
    c = claude.ClientClaude(modele="claude-test", client=sdk)
    with caplog.at_level(logging.DEBUG):
        assert c.interpreter("Villa 5 chambres", SCHEMA)["chambres"] == 5
    assert len(requetes) == 2  # une nouvelle tentative après la surcharge
    corps = json.loads(requetes[-1].content)
    assert corps["tool_choice"] == {"type": "tool", "name": "definir_programme"}
    assert requetes[-1].headers["x-api-key"] == CLE
    assert CLE not in caplog.text and CLE not in repr(c)
