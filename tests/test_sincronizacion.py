from datetime import datetime, timezone

from app.models.cuenta_chesscom import CuentaChesscom
from app.models.enums import ResultadoPartida, Ritmo
from app.services.sincronizacion_service import partida_es_elegible


def _cuentas() -> dict[str, CuentaChesscom]:
    corte = datetime(2026, 10, 10, tzinfo=timezone.utc)
    return {
        "ana": CuentaChesscom(
            usuario_id=1,
            username="ana",
            username_visible="Ana",
            vinculada_en=corte,
        ),
        "beto": CuentaChesscom(
            usuario_id=2,
            username="beto",
            username_visible="Beto",
            vinculada_en=corte,
        ),
    }


def _game(**overrides) -> dict:
    base = {
        "uuid": "abc-123",
        "url": "https://www.chess.com/game/live/1",
        "rules": "chess",
        "time_class": "blitz",
        "rated": False,
        "end_time": int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp()),
        "white": {"username": "Ana", "result": "win"},
        "black": {"username": "Beto", "result": "resigned"},
        "pgn": "1. e4 e5",
    }
    base.update(overrides)
    return base


def test_cuenta_partida_nueva_estandar_entre_miembros():
    candidata = partida_es_elegible(_game(), _cuentas())
    assert candidata is not None
    assert candidata.ritmo == Ritmo.BLITZ
    assert candidata.resultado == ResultadoPartida.BLANCA
    assert candidata.rated is False


def test_ignora_historial_anterior_al_vinculo():
    vieja = _game(end_time=int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()))
    assert partida_es_elegible(vieja, _cuentas()) is None


def test_ignora_si_el_rival_no_esta_en_la_comunidad():
    game = _game()
    game["black"] = {"username": "hikaru", "result": "resigned"}
    assert partida_es_elegible(game, _cuentas()) is None


def test_ignora_chess960_y_daily():
    assert partida_es_elegible(_game(rules="chess960"), _cuentas()) is None
    assert partida_es_elegible(_game(time_class="daily"), _cuentas()) is None


def test_ignora_partida_abortada_sin_ganador():
    game = _game()
    game["white"] = {"username": "Ana", "result": "abandoned"}
    game["black"] = {"username": "Beto", "result": "abandoned"}
    assert partida_es_elegible(game, _cuentas()) is None
