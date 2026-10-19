"""Connecteur Claude (SDK `anthropic`) : interpréter, corriger, expliquer.

Claude ne fait que proposer un `Programme` (sortie structurée par tool use forcé) ou rédiger
une explication. Aucun calcul de sécurité ne passe par ce module.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any

from apiconnect.erreurs import IAIndisponible, IANonConfiguree, ReponseInvalide

log = logging.getLogger("apiconnect.claude")

MODELE_DEFAUT = "claude-sonnet-5-5"
DELAI_S = 60.0
NOUVELLES_TENTATIVES = 2
MOTS_MAX_EXPLICATION = 120

CHAMPS_TERRAIN = ("resistance_terre", "portance_sol", "portance_mesuree")

SYSTEME_INTERPRETER = """Tu es architecte-programmiste pour des maisons individuelles en Afrique francophone (RDC).
À partir de la description en français d'un constructeur, tu remplis le programme de la maison
en appelant l'outil `definir_programme`.

Règles :
- Ne renseigne que ce que le texte dit, explicitement ou sans ambiguïté. Pour tout le reste, laisse la valeur par défaut du schéma.
- N'invente jamais de données de terrain : `resistance_terre`, `portance_sol` et `portance_mesuree` ne changent que si le texte donne une mesure.
- Dimensions en mètres, surfaces en m², pentes en %.
- Signale dans `remarques` (phrases courtes en français) ce qui est ambigu, contradictoire ou que tu as dû interpréter.
- Tu ne calcules rien : les sections, calibres, semelles et quantités sont calculés par le logiciel."""

SYSTEME_CORRIGER = """Tu es architecte-programmiste. Le logiciel a calculé un projet à partir du programme fourni et
ses contrôles réglementaires ont relevé des points bloquants. Propose un programme corrigé qui lève ces
bloquants en changeant le moins de choses possible, en appelant l'outil `corriger_programme`.

Règles :
- Ne modifie que ce qui est nécessaire (recul, pièces optionnelles, surfaces, pente ou type de toiture…).
- Ne modifie JAMAIS `resistance_terre`, `portance_sol`, `portance_mesuree` ni les dimensions du terrain.
- Explique en français simple, en une ou deux phrases, ce que tu as changé et pourquoi.
- Liste dans `champs_modifies` exactement les champs que tu as changés.
- Tu ne calcules aucune valeur de sécurité : le logiciel recalcule tout après ta proposition."""

SYSTEME_EXPLIQUER = f"""Tu expliques à un constructeur, en français simple, un résultat calculé par le logiciel
(un contrôle réglementaire ou un circuit électrique), à partir des données et hypothèses fournies.

Règles :
- {MOTS_MAX_EXPLICATION} mots au maximum, sans titre ni liste à puces.
- Ne change aucune valeur et n'en calcule aucune nouvelle : cite seulement celles qui sont fournies.
- Si une donnée manque, dis-le plutôt que de la supposer.
- Termine, si c'est utile, par ce que le constructeur peut faire."""


def _schema_outil(schema_programme: dict, enveloppe: dict | None = None) -> dict:
    """Prépare un input_schema : remonte les `$defs` à la racine pour que les `$ref` restent valides."""
    s = copy.deepcopy(schema_programme)
    defs = s.pop("$defs", None)
    if enveloppe is None:
        racine = s
        racine.setdefault("properties", {})["remarques"] = {
            "type": "array", "items": {"type": "string"},
            "description": "Points ambigus ou interprétés, en français."}
    else:
        racine = copy.deepcopy(enveloppe)
        racine["properties"]["programme"] = s
    if defs:
        racine["$defs"] = defs
    return racine


def _tronquer_mots(texte: str, n: int = MOTS_MAX_EXPLICATION) -> str:
    mots = texte.split()
    return texte.strip() if len(mots) <= n else " ".join(mots[:n]).rstrip(",;:") + "…"


class ClientClaude:
    """Client Claude. `client` permet d'injecter un faux client dans les tests."""

    def __init__(self, api_key: str = "", modele: str = MODELE_DEFAUT, *, client: Any = None,
                 delai_s: float = DELAI_S, max_tokens: int = 2048):
        self.modele = modele or MODELE_DEFAUT
        self.max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            if not api_key:
                raise IANonConfiguree()
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key, timeout=delai_s, max_retries=NOUVELLES_TENTATIVES)

    def __repr__(self) -> str:  # jamais la clé
        return f"ClientClaude(modele={self.modele!r})"

    # -- appel bas niveau ----------------------------------------------------
    def _appeler(self, **kwargs) -> Any:
        import anthropic

        try:
            return self._client.messages.create(model=self.modele, max_tokens=self.max_tokens, **kwargs)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            log.error("Claude : clé refusée (HTTP %s)", e.status_code)
            raise IANonConfiguree("La clé du service d'IA texte est refusée.") from e
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as e:
            log.warning("Claude indisponible : %s", e.__class__.__name__)
            raise IAIndisponible(detail=e.__class__.__name__) from e
        except anthropic.APIStatusError as e:
            log.warning("Claude : HTTP %s", e.status_code)
            if e.status_code >= 500:
                raise IAIndisponible(detail=f"HTTP {e.status_code}") from e
            raise ReponseInvalide(detail=f"HTTP {e.status_code}") from e

    @staticmethod
    def _entree_outil(reponse: Any, nom: str) -> dict:
        for bloc in getattr(reponse, "content", None) or []:
            if getattr(bloc, "type", None) == "tool_use" and getattr(bloc, "name", None) == nom:
                entree = getattr(bloc, "input", None)
                if isinstance(entree, str):  # tolérance : JSON renvoyé sous forme de texte
                    try:
                        entree = json.loads(entree)
                    except ValueError as e:
                        raise ReponseInvalide(detail="entrée d'outil non JSON") from e
                if isinstance(entree, dict):
                    return copy.deepcopy(entree)
        raise ReponseInvalide(detail=f"pas d'appel à l'outil {nom}")

    # -- interface utilisée par l'orchestrateur ------------------------------
    def interpreter(self, texte: str, schema: dict) -> dict:
        """Texte → dict conforme au schéma Programme, plus une clé `remarques`."""
        outil = {"name": "definir_programme",
                 "description": "Enregistre le programme de la maison décrite par le constructeur.",
                 "input_schema": _schema_outil(schema)}
        rep = self._appeler(system=SYSTEME_INTERPRETER, tools=[outil],
                            tool_choice={"type": "tool", "name": "definir_programme"},
                            messages=[{"role": "user", "content": texte}])
        entree = self._entree_outil(rep, "definir_programme")
        remarques = entree.get("remarques", [])
        if not isinstance(remarques, list):
            entree["remarques"] = [str(remarques)]
        return entree

    def corriger(self, programme: dict, controles: list[dict], schema: dict) -> dict:
        """Programme + contrôles bloquants → {programme, explication, champs_modifies}."""
        enveloppe = {"type": "object", "additionalProperties": False,
                     "required": ["programme", "explication", "champs_modifies"],
                     "properties": {
                         "programme": {},
                         "explication": {"type": "string", "description": "En français, une ou deux phrases."},
                         "champs_modifies": {"type": "array", "items": {"type": "string"}}}}
        outil = {"name": "corriger_programme",
                 "description": "Propose un programme corrigé qui lève les contrôles bloquants.",
                 "input_schema": _schema_outil(schema, enveloppe)}
        message = ("Programme actuel :\n" + json.dumps(programme, ensure_ascii=False, indent=1)
                   + "\n\nContrôles bloquants :\n" + json.dumps(controles, ensure_ascii=False, indent=1))
        rep = self._appeler(system=SYSTEME_CORRIGER, tools=[outil],
                            tool_choice={"type": "tool", "name": "corriger_programme"},
                            messages=[{"role": "user", "content": message}])
        entree = self._entree_outil(rep, "corriger_programme")
        if not isinstance(entree.get("programme"), dict):
            raise ReponseInvalide(detail="programme absent de la correction")
        # Les données de terrain sont recopiées telles quelles, quoi que propose le modèle
        for c in CHAMPS_TERRAIN:
            if c in programme:
                entree["programme"][c] = programme[c]
        entree.setdefault("explication", "")
        entree.setdefault("champs_modifies", [])
        return entree

    def expliquer(self, contexte: dict) -> str:
        """Contexte d'un contrôle ou d'un circuit → explication en français (120 mots max)."""
        message = "Élément à expliquer :\n" + json.dumps(contexte, ensure_ascii=False, indent=1, default=str)
        rep = self._appeler(system=SYSTEME_EXPLIQUER, messages=[{"role": "user", "content": message}])
        texte = " ".join(getattr(b, "text", "") for b in (getattr(rep, "content", None) or [])
                         if getattr(b, "type", None) == "text").strip()
        if not texte:
            raise ReponseInvalide(detail="explication vide")
        return _tronquer_mots(texte)
