"""elo de partida para ranking por puntos subidos

Revision ID: 004eloinicio
Revises: 003lichess
Create Date: 2026-11-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "004eloinicio"
down_revision: Union[str, None] = "003lichess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columnas = {c["name"] for c in inspect(op.get_bind()).get_columns("ratings")}
    if "elo_inicio" in columnas:
        return
    op.add_column(
        "ratings",
        sa.Column("elo_inicio", sa.Integer(), nullable=False, server_default="1000"),
    )


def downgrade() -> None:
    columnas = {c["name"] for c in inspect(op.get_bind()).get_columns("ratings")}
    if "elo_inicio" in columnas:
        op.drop_column("ratings", "elo_inicio")
