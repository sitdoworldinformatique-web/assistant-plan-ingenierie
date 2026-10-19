"""Accès aux connecteurs IA (paquet `apiconnect`), injectés comme dépendances FastAPI.

Sans clé API, `client_texte` renvoie None : l'application fonctionne avec l'analyseur par
règles, sans auto-correction ni explication.
"""
from __future__ import annotations

from app import config as config_mod


def client_texte():
    cfg = config_mod.charger()
    if not cfg.ia_texte_configuree:
        return None
    from apiconnect import claude

    return claude.ClientClaude(api_key=cfg.anthropic_api_key, modele=cfg.claude_model)


def client_image():
    cfg = config_mod.charger()
    if not cfg.ia_image_configuree:
        return None
    from apiconnect import nano_banana

    return nano_banana.ClientNanoBanana(api_key=cfg.gemini_api_key, modele=cfg.nano_banana_model)
