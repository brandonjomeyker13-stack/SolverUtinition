"""rating real de Lichess y Chess.com por mes

Revision ID: 005eloreal
Revises: 004eloinicio
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "005eloreal"
down_revision: Union[str, None] = "004eloinicio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ritmo_enum = postgresql.ENUM("bullet", "blitz", "rapid", name="ritmo_enum", create_type=False)
plataforma_enum = postgresql.ENUM("chesscom", "lichess", name="plataforma_enum", create_type=False)


def upgrade() -> None:
    if inspect(op.get_bind()).has_table("elo_real_mensual"):
        return
    op.create_table(
        "elo_real_mensual",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plataforma", plataforma_enum, nullable=False),
        sa.Column("ritmo", ritmo_enum, nullable=False),
        sa.Column("mes", sa.String(7), nullable=False),
        sa.Column("elo_inicio", sa.Integer(), nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False),
        sa.Column("partidas", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("usuario_id", "plataforma", "ritmo", "mes", name="uq_elo_real_mes"),
    )
    op.create_index("ix_elo_real_mensual_usuario_id", "elo_real_mensual", ["usuario_id"])
    op.create_index("ix_elo_real_mensual_mes", "elo_real_mensual", ["mes"])


def downgrade() -> None:
    if inspect(op.get_bind()).has_table("elo_real_mensual"):
        op.drop_table("elo_real_mensual")
