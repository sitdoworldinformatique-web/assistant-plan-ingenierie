"""Point d'entrée FastAPI."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config as config_mod
from app.moteurs.normes import VERSION_MOTEURS

cfg = config_mod.charger()

app = FastAPI(
    title="Assistant Plan Ingénierie",
    version=VERSION_MOTEURS,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sante")
def sante() -> dict:
    return {
        "etat": "ok",
        "version_moteurs": VERSION_MOTEURS,
        "ia_texte_configuree": cfg.ia_texte_configuree,
        "ia_image_configuree": cfg.ia_image_configuree,
    }
