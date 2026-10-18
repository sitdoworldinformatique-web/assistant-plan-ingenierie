"""Authentification JWT (email + mot de passe) et rôles constructeur / ingenieur / admin."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import config as config_mod
from app import stockage
from app.stockage import Utilisateur

Role = Literal["constructeur", "ingenieur", "admin"]
ROLES: tuple[str, ...] = ("constructeur", "ingenieur", "admin")
_bearer = HTTPBearer(auto_error=False)


class ErreurApi(HTTPException):
    """Erreur renvoyée au client sous la forme {code, message}."""

    def __init__(self, statut: int, code: str, message: str):
        super().__init__(status_code=statut, detail={"code": code, "message": message})


def hacher(mot_de_passe: str) -> str:
    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verifier(mot_de_passe: str, hache: str) -> bool:
    try:
        return bcrypt.checkpw(mot_de_passe.encode("utf-8"), hache.encode("ascii"))
    except ValueError:
        return False


def creer_jeton(utilisateur: Utilisateur) -> str:
    cfg = config_mod.charger()
    maintenant = datetime.now(UTC)
    charge = {"sub": str(utilisateur.id), "role": utilisateur.role, "iat": maintenant,
              "exp": maintenant + timedelta(hours=cfg.jwt_duree_h)}
    return jwt.encode(charge, cfg.jwt_secret, algorithm="HS256")


def utilisateur_courant(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    s: Session = Depends(stockage.session),
) -> Utilisateur:
    if cred is None:
        raise ErreurApi(401, "non_authentifie", "Connectez-vous pour accéder à cette ressource.")
    try:
        charge = jwt.decode(cred.credentials, config_mod.charger().jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise ErreurApi(401, "jeton_expire", "Votre session a expiré, reconnectez-vous.") from e
    except jwt.InvalidTokenError as e:
        raise ErreurApi(401, "jeton_invalide", "Jeton d'authentification invalide.") from e
    u = s.get(Utilisateur, int(charge["sub"]))
    if u is None:
        raise ErreurApi(401, "jeton_invalide", "Utilisateur introuvable.")
    return u


def exiger_role(*roles: str):
    def dependance(u: Utilisateur = Depends(utilisateur_courant)) -> Utilisateur:
        if u.role not in roles:
            raise ErreurApi(403, "role_insuffisant", f"Action réservée au rôle : {', '.join(roles)}.")
        return u

    return dependance
