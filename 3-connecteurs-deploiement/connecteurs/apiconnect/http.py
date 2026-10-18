"""Appels HTTP JSON avec délai d'attente et nouvelles tentatives (429 et 5xx).

Les clés ne sont jamais journalisées : seuls la méthode, l'hôte, le chemin et le statut le sont.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from apiconnect.erreurs import IAIndisponible, ReponseInvalide

log = logging.getLogger("apiconnect.http")

STATUTS_A_REESSAYER = frozenset({429, 500, 502, 503, 504})


def _cible(url: str) -> str:
    p = urlsplit(url)
    return f"{p.netloc}{p.path}"


def post_json(url: str, corps: dict, *, entetes: dict[str, str], delai_s: float = 60.0,
              tentatives: int = 3, attente_base_s: float = 1.0, client: httpx.Client | None = None,
              dormir: Callable[[float], None] = time.sleep, message_indisponible: str | None = None) -> dict:
    """POST JSON → dict. 2 nouvelles tentatives (par défaut) avec attente exponentielle sur 429/5xx/réseau."""
    propre = client is None
    client = client or httpx.Client(timeout=delai_s)
    derniere = ""
    try:
        for n in range(1, tentatives + 1):
            try:
                r = client.post(url, json=corps, headers=entetes, timeout=delai_s)
            except httpx.TimeoutException:
                derniere = "délai dépassé"
            except httpx.TransportError as e:
                derniere = f"réseau : {e.__class__.__name__}"
            else:
                if r.status_code in STATUTS_A_REESSAYER:
                    derniere = f"HTTP {r.status_code}"
                elif r.status_code >= 400:
                    log.warning("POST %s → HTTP %s", _cible(url), r.status_code)
                    raise ReponseInvalide(detail=f"HTTP {r.status_code}")
                else:
                    try:
                        return r.json()
                    except ValueError as e:
                        raise ReponseInvalide(detail="corps non JSON") from e
            log.warning("POST %s → %s (tentative %d/%d)", _cible(url), derniere, n, tentatives)
            if n < tentatives:
                retry_after = 0.0
                if derniere == "HTTP 429":
                    try:
                        retry_after = float(r.headers.get("retry-after", 0))
                    except (TypeError, ValueError):
                        retry_after = 0.0
                dormir(max(retry_after, attente_base_s * 2 ** (n - 1)))
        raise IAIndisponible(message_indisponible, detail=derniere)
    finally:
        if propre:
            client.close()
