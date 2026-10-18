"""Pipeline IA → moteurs → contrôles, avec une IA simulée (aucun appel réseau)."""
from types import SimpleNamespace

import pytest
from apiconnect import claude
from apiconnect.erreurs import IAIndisponible

from app import orchestrateur
from app.moteurs.programme import Programme

TEXTE = "Villa de 3 chambres avec véranda sur un terrain de 15 m sur 20 m, terre mesurée à 45 ohms"


class FausseIA:
    modele = "ia-simulee"

    def __init__(self, interpretations=(), corrections=(), explications=()):
        self.interpretations = list(interpretations)
        self.corrections = list(corrections)
        self.explications = list(explications)
        self.appels: list[tuple] = []

    @staticmethod
    def _suivant(file):
        r = file.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def interpreter(self, texte, schema):
        self.appels.append(("interpreter", texte))
        return dict(self._suivant(self.interpretations))

    def corriger(self, programme, controles, schema):
        self.appels.append(("corriger", [c["id"] for c in controles]))
        maj = self._suivant(self.corrections)
        return {"programme": {**programme, **maj}, "explication": f"Modifié : {', '.join(maj)}",
                "champs_modifies": list(maj)}

    def expliquer(self, contexte):
        self.appels.append(("expliquer", contexte["type"]))
        return self._suivant(self.explications)


def _ref(programme_ref):
    return programme_ref.model_dump(mode="json")


def test_sans_cle_secours_par_regles(programme_ref):
    res = orchestrateur.generer(TEXTE, None, None)
    assert [e["modele"] for e in res["journal_ia"]] == ["analyseur-par-regles"]
    assert res["corrections"] == []
    # Les bloquants sont simplement affichés
    assert res["resultats"].statut == "bloque"
    assert "IMPL-EMPRISE-L" in [c.id for c in res["resultats"].controles]
    assert res["empreinte"] == orchestrateur.empreinte(res["programme"])


def test_interpretation_ia_sans_donnee_de_terrain_inventee(programme_ref):
    proposition = {**_ref(programme_ref), "chambres": 4, "portance_sol": 0.4, "portance_mesuree": True,
                   "remarques": ["Surface du séjour non précisée."]}
    ia = FausseIA(interpretations=[proposition], corrections=[{}])
    res = orchestrateur.generer(TEXTE, None, ia)
    prog = res["programme"]
    assert prog.chambres == 4
    assert prog.portance_sol == 0.15 and prog.portance_mesuree is False  # repris du texte (rien dit) → défaut
    assert prog.resistance_terre == 45.0
    assert "Surface du séjour non précisée." in res["remarques"]
    assert any("terrain" in r for r in res["remarques"])
    e = res["journal_ia"][0]
    assert e["etape"] == "interpreter" and e["modele"] == "ia-simulee" and e["tentative"] == 1
    assert {"date", "entree_resume", "sortie_resume", "duree_ms"} <= set(e)


def test_sortie_invalide_puis_valide(programme_ref):
    ia = FausseIA(interpretations=[{"chambres": 42}, {**_ref(programme_ref), "chambres": 2}])
    res = orchestrateur.generer(TEXTE, None, ia)
    assert res["programme"].chambres == 2
    assert [(e["tentative"], e.get("erreur", False)) for e in res["journal_ia"][:2]] == [(1, True), (2, False)]


def test_deux_sorties_invalides_puis_secours():
    ia = FausseIA(interpretations=[{"inconnu": 1}, {"chambres": "beaucoup"}])
    res = orchestrateur.generer(TEXTE, None, ia)
    assert [e["modele"] for e in res["journal_ia"]][:3] == ["ia-simulee", "ia-simulee", "analyseur-par-regles"]


def test_ia_indisponible_secours_immediat():
    ia = FausseIA(interpretations=[IAIndisponible()], corrections=[{}])
    res = orchestrateur.generer(TEXTE, None, ia)
    assert [a[0] for a in ia.appels] == ["interpreter", "corriger"]
    assert [e["modele"] for e in res["journal_ia"]][:2] == ["ia-simulee", "analyseur-par-regles"]
    assert res["corrections"] == [] and res["journal_ia"][-1]["sortie_resume"] == "aucune modification proposée"


def test_auto_correction_leve_le_bloquant_en_deux_iterations(programme_ref):
    ia = FausseIA(corrections=[{"recul": 1.0}, {"chambres": 2}])
    res = orchestrateur.generer(None, programme_ref, ia)
    assert [c["champs_modifies"] for c in res["corrections"]] == [["recul"], ["chambres"]]
    assert res["corrections"][1]["avant"] == {"chambres": 3} and res["corrections"][1]["apres"] == {"chambres": 2}
    assert res["resultats"].statut != "bloque"
    assert ia.appels == [("corriger", ["IMPL-EMPRISE-L"]), ("corriger", ["IMPL-EMPRISE-L"])]
    assert res["empreinte"] == orchestrateur.empreinte(res["programme"])


def test_auto_correction_limitee_a_deux_iterations(programme_ref):
    ia = FausseIA(corrections=[{"recul": 1.5}, {"recul": 1.0}, {"chambres": 2}])
    res = orchestrateur.generer(None, programme_ref, ia)
    assert len(res["corrections"]) == 2 and res["resultats"].statut == "bloque"
    assert len(ia.corrections) == 1  # la troisième proposition n'a jamais été demandée


@pytest.mark.parametrize("interdit", [{"portance_sol": 0.3}, {"resistance_terre": 5.0},
                                      {"portance_mesuree": True}, {"terrain_largeur": 20.0}])
def test_auto_correction_refuse_les_champs_interdits(programme_ref, interdit):
    ia = FausseIA(corrections=[{"chambres": 2, **interdit}])
    res = orchestrateur.generer(None, programme_ref, ia)
    assert res["corrections"] == [] and res["programme"] == programme_ref
    assert "refusé" in res["journal_ia"][-1]["sortie_resume"] and res["journal_ia"][-1]["erreur"]


def test_contexte_et_explication(programme_ref):
    res = orchestrateur.generer(None, programme_ref, None)
    resultats = res["resultats"].model_dump(mode="json")
    ctx = orchestrateur.contexte_element(resultats, "IMPL-EMPRISE-L")
    assert ctx["type"] == "controle" and ctx["hypotheses"]
    assert all(h["module"] == "implantation" for h in ctx["hypotheses"])
    ctx_c = orchestrateur.contexte_element(resultats, "C1")
    assert ctx_c["type"] == "circuit" and ctx_c["circuit"]["num"] == 1
    assert orchestrateur.contexte_element(resultats, "ecl-1")["circuit"]["key"] == "ecl-1"
    assert orchestrateur.contexte_element(resultats, "INCONNU") is None

    journal = orchestrateur.Journal()
    texte, source = orchestrateur.expliquer(ctx, None, journal)
    assert source == "regles" and "17,48 m" in texte and journal.entrees == []
    texte, source = orchestrateur.expliquer(ctx_c, FausseIA(explications=[IAIndisponible()]), journal)
    assert source == "regles" and texte.startswith("Circuit C1") and journal.entrees[-1]["erreur"]
    texte, source = orchestrateur.expliquer(ctx, FausseIA(explications=["La maison est trop large."]), journal)
    assert (texte, source) == ("La maison est trop large.", "ia")


# -- pipeline complet à travers le vrai connecteur Claude, SDK simulé ---------------------------

class FauxSDK:
    def __init__(self, reponses):
        self.messages = self
        self.reponses = list(reponses)
        self.appels = []

    def create(self, **kwargs):
        self.appels.append(kwargs)
        nom, entree = self.reponses.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=nom, input=entree)])


def test_pipeline_complet_connecteur_claude_simule(programme_ref):
    interpretation = {**_ref(programme_ref), "portance_sol": 0.5, "remarques": ["Garage non mentionné."]}
    sdk = FauxSDK([
        ("definir_programme", interpretation),
        ("corriger_programme", {"programme": {**_ref(programme_ref), "chambres": 2, "portance_sol": 0.9},
                                "explication": "Une chambre de moins pour respecter le recul.",
                                "champs_modifies": ["chambres"]}),
    ])
    ia = claude.ClientClaude(modele="claude-simule", client=sdk)
    res = orchestrateur.generer(TEXTE, None, ia)
    assert res["programme"].chambres == 2 and res["programme"].portance_sol == 0.15
    assert res["resultats"].statut != "bloque"
    assert res["corrections"][0]["explication"] == "Une chambre de moins pour respecter le recul."
    assert [e["etape"] for e in res["journal_ia"]] == ["interpreter", "corriger"]
    assert all(e["modele"] == "claude-simule" for e in res["journal_ia"])
    schema = sdk.appels[0]["tools"][0]["input_schema"]
    assert set(Programme.model_fields) <= set(schema["properties"])
