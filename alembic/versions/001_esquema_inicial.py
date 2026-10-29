"""esquema inicial: usuarios, chess.com, ratings y partidas

Revision ID: 001esquema
Revises:
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001esquema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ritmo_enum = postgresql.ENUM("bullet", "blitz", "rapid", name="ritmo_enum")
plataforma_enum = postgresql.ENUM("chesscom", name="plataforma_enum")
resultado_enum = postgresql.ENUM("1-0", "0-1", "1/2-1/2", name="resultado_partida_enum")


def upgrade() -> None:
    ritmo_enum.create(op.get_bind(), checkfirst=True)
    plataforma_enum.create(op.get_bind(), checkfirst=True)
    resultado_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ip_origen", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_usuario_id", "refresh_tokens", ["usuario_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "cuentas_chesscom",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("username_visible", sa.String(64), nullable=False),
        sa.Column("chesscom_uuid", sa.String(64), nullable=True),
        sa.Column("vinculada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("usuario_id", name="uq_cuentas_chesscom_usuario_id"),
        sa.UniqueConstraint("username", name="uq_cuentas_chesscom_username"),
        sa.UniqueConstraint("chesscom_uuid", name="uq_cuentas_chesscom_uuid"),
    )
    op.create_index("ix_cuentas_chesscom_username", "cuentas_chesscom", ["username"])

    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ritmo", ritmo_enum, nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False),
        sa.Column("partidas_jugadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("usuario_id", "ritmo", name="uq_rating_usuario_ritmo"),
    )
    op.create_index("ix_ratings_usuario_id", "ratings", ["usuario_id"])

    op.create_table(
        "partidas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plataforma", plataforma_enum, nullable=False),
        sa.Column("plataforma_partida_id", sa.String(80), nullable=False),
        sa.Column("blanca_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("negra_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ritmo", ritmo_enum, nullable=False),
        sa.Column("rated_en_plataforma", sa.Boolean(), nullable=False),
        sa.Column("resultado", resultado_enum, nullable=False),
        sa.Column("elo_blanca_antes", sa.Integer(), nullable=False),
        sa.Column("elo_negra_antes", sa.Integer(), nullable=False),
        sa.Column("delta_blanca", sa.Integer(), nullable=False),
        sa.Column("delta_negra", sa.Integer(), nullable=False),
        sa.Column("terminada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("pgn", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plataforma", "plataforma_partida_id", name="uq_partida_plataforma_id"),
    )
    op.create_index("ix_partidas_blanca_id", "partidas", ["blanca_id"])
    op.create_index("ix_partidas_negra_id", "partidas", ["negra_id"])
    op.create_index("ix_partidas_terminada_en", "partidas", ["terminada_en"])


def downgrade() -> None:
    op.drop_table("partidas")
    op.drop_table("ratings")
    op.drop_table("cuentas_chesscom")
    op.drop_table("refresh_tokens")
    op.drop_table("usuarios")
    resultado_enum.drop(op.get_bind(), checkfirst=True)
    plataforma_enum.drop(op.get_bind(), checkfirst=True)
    ritmo_enum.drop(op.get_bind(), checkfirst=True)
