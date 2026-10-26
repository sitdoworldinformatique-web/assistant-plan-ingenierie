"""Stockage des images de rendus : disque local ou Supabase Storage (bucket privé, API REST, clé service_role).

La clé stockée en base dit où est le fichier : « supabase:<chemin> » ou un chemin disque. Les deux coexistent, donc
passer d'un mode à l'autre ne casse pas les anciens rendus. La clé `service_role` reste sur le serveur.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx

from app.config import Config

PREFIXE = "supabase:"
DELAI_S = 30.0


class StockageIndisponible(Exception):
    pass


def _entetes(cfg: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.supabase_service_key}", "apikey": cfg.supabase_service_key}


def _url(cfg: Config, chemin: str) -> str:
    return f"{cfg.supabase_url.rstrip('/')}/storage/v1/object/{cfg.supabase_bucket}/{chemin}"


def _client() -> httpx.Client:  # remplaçable dans les tests
    return httpx.Client(timeout=DELAI_S)


def ecrire(cfg: Config, projet_id: int, octets: bytes) -> str:
    nom = f"{uuid.uuid4().hex}.jpg"
    if cfg.supabase_configure:
        chemin = f"{projet_id}/{nom}"
        try:
            with _client() as c:
                r = c.post(_url(cfg, chemin), content=octets, headers={**_entetes(cfg), "Content-Type": "image/jpeg"})
        except httpx.HTTPError as e:
            raise StockageIndisponible("Supabase Storage n'a pas répondu.") from e
        if r.status_code >= 300:
            raise StockageIndisponible(f"Supabase Storage a refusé l'image (code {r.status_code}).")
        return PREFIXE + chemin
    dossier = Path(cfg.stockage_rendus) / str(projet_id)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / nom
    fichier.write_bytes(octets)
    return str(fichier)


def lire(cfg: Config, cle: str) -> bytes | None:
    if cle.startswith(PREFIXE):
        if not cfg.supabase_configure:
            return None
        try:
            with _client() as c:
                r = c.get(_url(cfg, cle[len(PREFIXE):]), headers=_entetes(cfg))
        except httpx.HTTPError:
            return None
        return r.content if r.status_code == 200 else None
    fichier = Path(cle)
    return fichier.read_bytes() if fichier.is_file() else None


def supprimer(cfg: Config, cle: str) -> None:
    if cle.startswith(PREFIXE):
        if cfg.supabase_configure:
            try:
                with _client() as c:
                    c.delete(_url(cfg, cle[len(PREFIXE):]), headers=_entetes(cfg))
            except httpx.HTTPError:
                pass  # image orpheline côté Supabase : sans conséquence pour l'utilisateur
        return
    Path(cle).unlink(missing_ok=True)
