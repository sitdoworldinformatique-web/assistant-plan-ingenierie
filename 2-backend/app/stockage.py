"""Stockage SQLAlchemy 2 : PostgreSQL 16 en production, SQLite en développement et en test."""
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.moteurs.prix_defaut import PRIX_DEFAUT

JsonType = JSON().with_variant(JSONB(), "postgresql")


def maintenant() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    mot_de_passe_hache: Mapped[str] = mapped_column(String(255))
    nom: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="constructeur")
    numero_ordre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


class Projet(Base):
    __tablename__ = "projets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proprietaire_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"), index=True)
    nom: Mapped[str] = mapped_column(String(255))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant, onupdate=maintenant)
    texte_initial: Mapped[str] = mapped_column(Text, default="")
    programme: Mapped[dict] = mapped_column(JsonType)
    resultats: Mapped[dict] = mapped_column(JsonType)
    statut: Mapped[str] = mapped_column(String(40))
    empreinte: Mapped[str] = mapped_column(String(64))
    journal_ia: Mapped[list] = mapped_column(JsonType, default=list)
    remarques: Mapped[list] = mapped_column(JsonType, default=list)
    version_moteurs: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Validation(Base):
    __tablename__ = "validations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(40))
    ingenieur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    nom: Mapped[str] = mapped_column(String(255))
    numero_ordre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    empreinte: Mapped[str] = mapped_column(String(64))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
    commentaire: Mapped[str] = mapped_column(Text, default="")


class Rendu(Base):
    __tablename__ = "rendus"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"), index=True)
    style: Mapped[str] = mapped_column(String(60))
    chemin_fichier: Mapped[str] = mapped_column(String(500))
    prompt: Mapped[str] = mapped_column(Text)
    modele: Mapped[str] = mapped_column(String(100))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


class PrixMateriau(Base):
    __tablename__ = "prix_materiaux"
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    libelle: Mapped[str] = mapped_column(String(255))
    unite: Mapped[str] = mapped_column(String(20))
    prix: Mapped[float]
    devise: Mapped[str] = mapped_column(String(10), default="USD")
    mis_a_jour_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)


# ---------------------------------------------------------------------------

_moteur = None
_fabrique: sessionmaker | None = None


def configurer(url: str) -> None:
    """Crée le moteur et la fabrique de sessions (appelé au démarrage ou par les tests)."""
    global _moteur, _fabrique
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        chemin = url.split("///", 1)[-1]
        if chemin and chemin != ":memory:":
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        if chemin == ":memory:" or url == "sqlite://":
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    _moteur = create_engine(url, pool_pre_ping=True, **kwargs)
    _fabrique = sessionmaker(bind=_moteur, expire_on_commit=False)


def initialiser() -> None:
    """Crée les tables manquantes (si AUTO_CREATE_TABLES ≠ 0) et amorce la table des prix."""
    assert _moteur is not None and _fabrique is not None
    if os.getenv("AUTO_CREATE_TABLES", "1") != "0":
        Base.metadata.create_all(_moteur)
    with _fabrique() as s:
        existants = set(s.scalars(select(PrixMateriau.code)))
        for code, (libelle, unite, prix) in PRIX_DEFAUT.items():
            if code not in existants:
                s.add(PrixMateriau(code=code, libelle=libelle, unite=unite, prix=prix, devise="USD"))
        s.commit()


def session() -> Iterator[Session]:
    assert _fabrique is not None, "stockage non configuré"
    with _fabrique() as s:
        yield s


def table_prix(s: Session) -> dict[str, dict]:
    return {p.code: {"libelle": p.libelle, "unite": p.unite, "prix": p.prix, "devise": p.devise}
            for p in s.scalars(select(PrixMateriau))}
