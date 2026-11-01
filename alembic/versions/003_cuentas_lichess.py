"""cuenta de Lichess y plataforma lichess en las partidas

Revision ID: 003lichess
Revises: 002googlesub
Create Date: 2026-11-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "003lichess"
down_revision: Union[str, None] = "002googlesub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tiene_tabla(nombre: str) -> bool:
    return inspect(op.get_bind()).has_table(nombre)


def upgrade() -> None:
    bind = op.get_bind()
    # El valor nuevo no se usa en este mismo script: solo se inserta en runtime,
    # cuando esta transacción ya terminó.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE plataforma_enum ADD VALUE IF NOT EXISTS 'lichess'")

    if _tiene_tabla("cuentas_lichess"):
        return

    op.create_table(
        "cuentas_lichess",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("username_visible", sa.String(64), nullable=False),
        sa.Column("vinculada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("usuario_id", name="uq_cuentas_lichess_usuario_id"),
        sa.UniqueConstraint("username", name="uq_cuentas_lichess_username"),
    )
    op.create_index("ix_cuentas_lichess_username", "cuentas_lichess", ["username"])


def downgrade() -> None:
    if _tiene_tabla("cuentas_lichess"):
        op.drop_table("cuentas_lichess")
    # Postgres no deja quitar un valor de un ENUM sin recrear el tipo.
    # 'lichess' se queda en plataforma_enum.
