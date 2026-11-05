from datetime import datetime, timezone

from app.models.cuenta_lichess import CuentaLichess
from app.models.enums import Ritmo
from app.repositories.rating_repository import RatingRepository
from app.services.ranking_service import RankingService


def test_subida_gana_al_elo_alto(db, usuario_a, usuario_b):
    ratings = RatingRepository(db)
    baja = ratings.get(usuario_a.id, Ritmo.RAPID)
    alta = ratings.get(usuario_b.id, Ritmo.RAPID)
    assert baja is not None and alta is not None
    baja.elo_inicio = 500
    baja.elo = 600
    baja.partidas_jugadas = 8
    alta.elo_inicio = 2000
    alta.elo = 2010
    alta.partidas_jugadas = 8
    db.commit()

    por_elo = RankingService(db).listar(Ritmo.RAPID)
    assert [f.usuario_id for f in por_elo[:2]] == [usuario_b.id, usuario_a.id]

    progreso = RankingService(db).listar_progreso(Ritmo.RAPID)
    assert progreso[0].usuario_id == usuario_a.id
    assert progreso[0].subida == 100
    assert progreso[1].usuario_id == usuario_b.id
    assert progreso[1].subida == 10


def test_progreso_incluye_lichess_y_chesscom(db, cuenta_a, usuario_b):
    db.add(
        CuentaLichess(
            usuario_id=usuario_b.id,
            username="beto",
            username_visible="BetoLichess",
            vinculada_en=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    filas = {f.usuario_id: f for f in RankingService(db).listar_progreso(Ritmo.BLITZ)}
    assert filas[cuenta_a.usuario_id].chesscom_username == "Ana"
    assert filas[usuario_b.id].lichess_username == "BetoLichess"
