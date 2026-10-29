from datetime import datetime, timezone

from app.core.config import settings
from app.models.enums import Ritmo
from app.repositories.rating_repository import RatingRepository
from app.services.sincronizacion_service import SincronizacionService


class ClienteFalso:
    def __init__(self, games: list[dict]):
        self.games = games

    def partidas_mes(self, username: str, year: int, month: int) -> list[dict]:
        return self.games


def test_aplica_elo_una_sola_vez(db, cuenta_a, cuenta_b):
    game = {
        "uuid": "unica-1",
        "url": "https://www.chess.com/game/live/1",
        "rules": "chess",
        "time_class": "rapid",
        "rated": True,
        "end_time": int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()),
        "white": {"username": "Ana", "result": "win"},
        "black": {"username": "Beto", "result": "checkmated"},
        "pgn": "1. e4 e5",
    }
    service = SincronizacionService(db, cliente=ClienteFalso([game]))

    primera = service.sincronizar()
    segunda = service.sincronizar()

    assert primera["aplicadas"] == 1
    assert segunda["aplicadas"] == 0

    ratings = RatingRepository(db)
    ana = ratings.get(cuenta_a.usuario_id, Ritmo.RAPID)
    beto = ratings.get(cuenta_b.usuario_id, Ritmo.RAPID)
    assert ana is not None and beto is not None
    assert ana.elo == settings.ELO_INICIAL + round(settings.ELO_K * 0.5)
    assert beto.elo == settings.ELO_INICIAL - round(settings.ELO_K * 0.5)
    assert ana.partidas_jugadas == 1
    assert beto.partidas_jugadas == 1
