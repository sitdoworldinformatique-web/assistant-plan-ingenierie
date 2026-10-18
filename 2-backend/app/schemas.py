"""Schémas d'entrée/sortie de l'API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.moteurs.programme import Programme
from app.moteurs.regles import MODULES


class Inscription(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    mot_de_passe: str = Field(min_length=8, max_length=200)
    nom: str = Field(min_length=1, max_length=255)


class Connexion(BaseModel):
    email: str
    mot_de_passe: str


class UtilisateurSortie(BaseModel):
    id: int
    email: str
    nom: str
    role: str
    numero_ordre: str | None = None


class SessionUtilisateur(BaseModel):
    jeton: str
    utilisateur: UtilisateurSortie


class DemandeInterpreter(BaseModel):
    texte: str = Field(min_length=1, max_length=5000)


class DemandeGenerer(BaseModel):
    texte: str | None = Field(None, max_length=5000)
    programme: Programme | None = None
    nom: str | None = Field(None, max_length=255)


class DemandeValidation(BaseModel):
    module: str = Field(pattern="^(" + "|".join(MODULES) + ")$")
    commentaire: str = Field("", max_length=2000)


class DemandeExpliquer(BaseModel):
    element_id: str = Field(min_length=1, max_length=100)


class DemandeRendu(BaseModel):
    style: str
    image_base64: str = Field(min_length=10)


class PrixEntree(BaseModel):
    code: str
    libelle: str | None = None
    unite: str | None = None
    prix: float = Field(ge=0)
    devise: str | None = None


class ModifUtilisateur(BaseModel):
    role: str = Field(pattern="^(constructeur|ingenieur|admin)$")
    numero_ordre: str | None = None
