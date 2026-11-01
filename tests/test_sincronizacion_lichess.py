from datetime import datetime, timezone

from app.models.cuenta_lichess import CuentaLichess
from app.models.enums import ResultadoPartida, Ritmo
from app.services.sincronizacion_lichess_service import partida_lichess_es_elegible


def _cuentas() -> dict[str, CuentaLichess]:
    corte = datetime(2026, 10, 10, tzinfo=timezone.utc)
    return {
        "ana": CuentaLichess(
            usuario_id=1,
            username="ana",
            username_visible="Ana",
            vinculada_en=corte,
        ),
        "beto": CuentaLichess(
            usuario_id=2,
            username="beto",
            username_visible="Beto",
            vinculada_en=corte,
        ),
    }


def _fin(cuando: datetime) -> int:
    return int(cuando.timestamp() * 1000)


def _game(**overrides) -> dict:
    base = {
        "id": "abcd1234",
        "rated": True,
        "variant": "standard",
        "speed": "blitz",
        "status": "resign",
        "winner": "white",
        "lastMoveAt": _fin(datetime(2026, 10, 20, tzinfo=timezone.utc)),
        "players": {
            "white": {"user": {"name": "Ana", "id": "ana"}},
            "black": {"user": {"name": "Beto", "id": "beto"}},
        },
    }
    base.update(overrides)
    return base


def test_cuenta_partida_nueva_estandar_entre_miembros():
    candidata = partida_lichess_es_elegible(_game(), _cuentas())
    assert candidata is not None
    assert candidata.ritmo == Ritmo.BLITZ
    assert candidata.resultado == ResultadoPartida.BLANCA
    assert candidata.url == "https://lichess.org/abcd1234"


def test_ignora_historial_anterior_al_vinculo():
    vieja = _game(lastMoveAt=_fin(datetime(2026, 9, 1, tzinfo=timezone.utc)))
    assert partida_lichess_es_elegible(vieja, _cuentas()) is None


def test_ignora_si_el_rival_no_esta_en_la_comunidad():
    game = _game()
    game["players"]["black"] = {"user": {"name": "Hikaru", "id": "hikaru"}}
    assert partida_lichess_es_elegible(game, _cuentas()) is None


def test_ignora_variante_y_clasica():
    assert partida_lichess_es_elegible(_game(variant="crazyhouse"), _cuentas()) is None
    assert partida_lichess_es_elegible(_game(speed="classical"), _cuentas()) is None


def test_ignora_abortada_y_acepta_tablas():
    assert partida_lichess_es_elegible(_game(status="aborted", winner=None), _cuentas()) is None
    tablas = _game(status="draw", winner=None)
    candidata = partida_lichess_es_elegible(tablas, _cuentas())
    assert candidata is not None
    assert candidata.resultado == ResultadoPartida.TABLAS
