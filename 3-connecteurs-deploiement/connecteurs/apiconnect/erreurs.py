"""Erreurs des connecteurs IA. Les messages sont en français et ne contiennent jamais de clé.

`ReponseInvalide` dérive aussi de ValueError : l'orchestrateur la traite comme une sortie
invalide (nouvelle tentative), alors que `IAIndisponible` déclenche directement le secours.
"""
from __future__ import annotations


class ErreurIA(Exception):
    """Classe de base. `message` est affichable tel quel à l'utilisateur."""

    message = "Erreur du service d'IA."

    def __init__(self, message: str | None = None, *, detail: str = ""):
        self.message = message or self.message
        self.detail = detail
        super().__init__(self.message)


class IANonConfiguree(ErreurIA):
    message = "Le service d'IA n'est pas configuré sur ce serveur."


class IAIndisponible(ErreurIA):
    message = "Le service d'IA n'a pas répondu, réessayez dans une minute."


class ReponseInvalide(ErreurIA, ValueError):
    message = "Le service d'IA a renvoyé une réponse inexploitable."
