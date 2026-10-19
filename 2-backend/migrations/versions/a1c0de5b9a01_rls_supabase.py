"""verrouille l'API REST publique de Supabase (RLS sans politique)

Sur Supabase, toute table du schéma `public` est lisible par la clé publique (anon) via l'API REST tant que la
sécurité par ligne (RLS) n'est pas activée. L'application se connecte en direct à PostgreSQL avec le rôle propriétaire
des tables, qui contourne la RLS : l'activer sans politique ferme l'API REST sans gêner l'application. Sans effet sur
SQLite ; sur un PostgreSQL ordinaire, le propriétaire contourne aussi la RLS.

Revision ID: a1c0de5b9a01
Revises: 40b45c226e63
Create Date: 2026-10-19 18:00:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1c0de5b9a01"
down_revision: Union[str, Sequence[str], None] = "40b45c226e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("utilisateurs", "projets", "validations", "rendus", "prix_materiaux")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for t in TABLES:
        op.execute(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for t in TABLES:
        op.execute(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY')
