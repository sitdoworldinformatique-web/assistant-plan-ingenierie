"""Configuration lue dans les variables d'environnement (jamais de secret dans le code)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

SECRET_DEV = "dev-uniquement-a-changer-cle-de-developpement-32o"


def _liste(valeur: str) -> list[str]:
    return [v.strip() for v in valeur.split(",") if v.strip()]


@dataclass(frozen=True)
class Config:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./donnees/assistant.db"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", SECRET_DEV))
    jwt_duree_h: int = field(default_factory=lambda: int(os.getenv("JWT_DUREE_H", "24")))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    nano_banana_model: str = field(default_factory=lambda: os.getenv("NANO_BANANA_MODEL", "gemini-nano-banana-2.1"))
    rendus_max_par_jour: int = field(default_factory=lambda: int(os.getenv("RENDUS_MAX_PAR_JOUR", "10")))
    cors_origins: list[str] = field(
        default_factory=lambda: _liste(os.getenv("CORS_ORIGINS", "http://localhost:5173"))
    )
    stockage_rendus: str = field(default_factory=lambda: os.getenv("STOCKAGE_RENDUS", "./donnees/rendus"))

    environnement: str = field(default_factory=lambda: os.getenv("ENVIRONNEMENT", "dev"))

    def verifier(self) -> None:
        """En production, refuse de démarrer avec la clé de signature de développement ou un secret trop court."""
        if self.environnement == "production" and (self.jwt_secret == SECRET_DEV or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET doit être défini (32 caractères minimum) quand ENVIRONNEMENT=production.")

    @property
    def ia_texte_configuree(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def ia_image_configuree(self) -> bool:
        return bool(self.gemini_api_key)


def charger() -> Config:
    return Config()
