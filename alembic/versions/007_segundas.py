"""evaluación de la segunda mejor jugada en cada posición analizada

Revision ID: 007segundas
Revises: 006analisis
Create Date: 2026-11-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "007segundas"
down_revision: Union[str, None] = "006analisis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tiene_columna() -> bool:
    return any(c["name"] == "segundas" for c in inspect(op.get_bind()).get_columns("analisis_partidas"))


def upgrade() -> None:
    if not _tiene_columna():
        op.add_column("analisis_partidas", sa.Column("segundas", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _tiene_columna():
        op.drop_column("analisis_partidas", "segundas")
