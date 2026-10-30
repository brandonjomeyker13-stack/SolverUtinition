"""vincular cuenta de Google al usuario

Revision ID: 002googlesub
Revises: 001esquema
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "002googlesub"
down_revision: Union[str, None] = "001esquema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columnas = {col["name"] for col in inspect(op.get_bind()).get_columns("usuarios")}
    if "google_sub" not in columnas:
        op.add_column("usuarios", sa.Column("google_sub", sa.String(255), nullable=True))
    indices = {idx["name"] for idx in inspect(op.get_bind()).get_indexes("usuarios")}
    if "ix_usuarios_google_sub" not in indices:
        op.create_index("ix_usuarios_google_sub", "usuarios", ["google_sub"], unique=True)


def downgrade() -> None:
    indices = {idx["name"] for idx in inspect(op.get_bind()).get_indexes("usuarios")}
    if "ix_usuarios_google_sub" in indices:
        op.drop_index("ix_usuarios_google_sub", table_name="usuarios")
    columnas = {col["name"] for col in inspect(op.get_bind()).get_columns("usuarios")}
    if "google_sub" in columnas:
        op.drop_column("usuarios", "google_sub")
