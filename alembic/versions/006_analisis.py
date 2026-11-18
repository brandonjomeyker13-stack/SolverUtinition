"""análisis de partidas, resumen semanal y suscripciones push

Revision ID: 006analisis
Revises: 005eloreal
Create Date: 2026-11-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "006analisis"
down_revision: Union[str, None] = "005eloreal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

plataforma_enum = postgresql.ENUM("chesscom", "lichess", name="plataforma_enum", create_type=False)


def _fechas() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _usuario() -> sa.Column:
    return sa.Column(
        "usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not insp.has_table("analisis_partidas"):
        op.create_table(
            "analisis_partidas",
            sa.Column("id", sa.Integer(), primary_key=True),
            _usuario(),
            sa.Column("plataforma", plataforma_enum, nullable=False),
            sa.Column("partida_id", sa.String(120), nullable=False),
            sa.Column("url", sa.String(500), nullable=True),
            sa.Column("color", sa.String(5), nullable=False),
            sa.Column("ritmo", sa.String(20), nullable=False),
            sa.Column("resultado", sa.String(8), nullable=False),
            sa.Column("apertura", sa.String(200), nullable=True),
            sa.Column("terminada_en", sa.DateTime(timezone=True), nullable=False),
            sa.Column("pgn", sa.Text(), nullable=False),
            sa.Column("eval_inicial", sa.JSON(), nullable=False),
            sa.Column("evals", sa.JSON(), nullable=False),
            sa.Column("mejores", sa.JSON(), nullable=False),
            sa.Column("precision", sa.Float(), nullable=True),
            sa.Column("imprecisiones", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errores", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errores_graves", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fuente", sa.String(16), nullable=False),
            *_fechas(),
            sa.UniqueConstraint("usuario_id", "plataforma", "partida_id", name="uq_analisis_partida"),
        )
        op.create_index("ix_analisis_partidas_usuario_id", "analisis_partidas", ["usuario_id"])
        op.create_index("ix_analisis_partidas_terminada_en", "analisis_partidas", ["terminada_en"])

    if not insp.has_table("resumenes_semanales"):
        op.create_table(
            "resumenes_semanales",
            sa.Column("id", sa.Integer(), primary_key=True),
            _usuario(),
            sa.Column("semana", sa.Date(), nullable=False),
            sa.Column("titulo", sa.String(200), nullable=False),
            sa.Column("puntos", sa.JSON(), nullable=False),
            sa.Column("datos", sa.JSON(), nullable=False),
            *_fechas(),
            sa.UniqueConstraint("usuario_id", "semana", name="uq_resumen_semana"),
        )
        op.create_index("ix_resumenes_semanales_usuario_id", "resumenes_semanales", ["usuario_id"])

    if not insp.has_table("suscripciones_push"):
        op.create_table(
            "suscripciones_push",
            sa.Column("id", sa.Integer(), primary_key=True),
            _usuario(),
            sa.Column("endpoint", sa.String(1000), nullable=False),
            sa.Column("p256dh", sa.String(200), nullable=False),
            sa.Column("auth", sa.String(100), nullable=False),
            *_fechas(),
            sa.UniqueConstraint("endpoint", name="uq_suscripciones_push_endpoint"),
        )
        op.create_index("ix_suscripciones_push_usuario_id", "suscripciones_push", ["usuario_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for tabla in ("suscripciones_push", "resumenes_semanales", "analisis_partidas"):
        if insp.has_table(tabla):
            op.drop_table(tabla)
