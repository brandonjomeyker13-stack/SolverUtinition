from datetime import datetime, timezone

import pytest

from app.analisis.generales import (
    apertura_chesscom,
    desde_chesscom,
    desde_lichess,
    familia_apertura,
    leer_pgn,
    tiempos,
)
from app.analisis.metricas import jugadas, porcentaje_victoria, totales
from app.analisis.resumen import construir
from app.core.exceptions import ValidationError
from app.models.analisis import AnalisisPartida
from app.models.enums import Plataforma
from app.schemas.analisis import AnalisisIn
from app.services.analisis_service import AnalisisService, evals_de_lichess
from app.services.partidas_generales_service import PartidasGeneralesService

PGN_PASTOR = """[Event "Live Chess"]
[White "Rival"]
[Black "Ana"]
[Result "1-0"]
[TimeControl "180"]

1. e4 { [%clk 0:02:59] } 1... e5 { [%clk 0:02:59] } 2. Bc4 { [%clk 0:02:57] } 2... Nc6 { [%clk 0:02:58] }
3. Qh5 { [%clk 0:02:55] } 3... Nf6 { [%clk 0:02:57] } 4. Qxf7# { [%clk 0:02:54] } 1-0
"""

EVAL_INICIAL = {"cp": 20}
EVALS = [{"cp": 30}, {"cp": 25}, {"cp": 20}, {"cp": 30}, {"cp": 20}, {"mate": 1}, {"cp": 10000}]
MEJORES = ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g7g6", None]


def _analisis(partida_id: str, apertura: str = "Italian Game") -> AnalisisPartida:
    return AnalisisPartida(
        usuario_id=1,
        plataforma=Plataforma.CHESSCOM,
        partida_id=partida_id,
        url=f"https://www.chess.com/game/live/{partida_id}",
        color="black",
        ritmo="blitz",
        resultado="perdio",
        apertura=apertura,
        terminada_en=datetime(2026, 11, 16, tzinfo=timezone.utc),
        pgn=PGN_PASTOR,
        eval_inicial=EVAL_INICIAL,
        evals=EVALS,
        mejores=MEJORES,
        precision=60.0,
        imprecisiones=0,
        errores=0,
        errores_graves=1,
        fuente="servidor",
    )


def test_porcentaje_de_victoria_como_lichess():
    assert porcentaje_victoria(0) == pytest.approx(50)
    assert porcentaje_victoria(10000) == pytest.approx(97.5, abs=0.5)
    assert porcentaje_victoria(-300) < 30


def test_el_error_que_deja_mate_es_grave_para_quien_lo_juega():
    lista = jugadas(EVAL_INICIAL, EVALS)
    assert lista[5].clase == "error_grave" and not lista[5].blancas
    t = totales(lista, "black")
    assert t.errores_graves == 1
    assert totales(lista, "white").errores_graves == 0


def test_un_error_grave_baja_la_precision_mas_que_un_promedio_simple():
    tranquilas = [{"cp": 20}] * 30
    # La jugada 15 es de las negras y regala seis peones.
    con_error = tranquilas[:15] + [{"cp": 600}] * 15
    lista = jugadas(EVAL_INICIAL, con_error)
    negras = [j for j in lista if not j.blancas]
    simple = sum(j.precision for j in negras) / len(negras)
    assert totales(lista, "black").precision < simple
    assert totales(jugadas(EVAL_INICIAL, tranquilas), "white").precision == pytest.approx(100, abs=0.5)


def test_los_relojes_dicen_cuanto_tardo_cada_jugada():
    reloj = tiempos(leer_pgn(PGN_PASTOR))
    antes, tardo = reloj[5]
    assert (antes, tardo) == (178.0, 1.0)


def test_resumen_con_prisa_apertura_y_puzzles():
    resumen = construir([_analisis("g1"), _analisis("g2")])
    assert resumen.datos["perdidas_por_prisa"] == 2
    assert resumen.titulo == "Esta semana la prisa te costó partidas"
    texto = " ".join(resumen.puntos)
    assert "Perdiste 2 partidas por errores rápidos" in texto
    assert "Con negras, tu apertura Italian Game te está costando puntos: 0 de 2." in texto
    # Las dos partidas llegan a la misma posición: un solo puzzle.
    assert len(resumen.datos["puzzles"]) == 1
    puzzle = resumen.datos["puzzles"][0]
    assert (puzzle["solucion"], puzzle["jugada"]) == ("g7g6", "g8f6")


def test_sin_partidas_no_hay_resumen():
    assert construir([]) is None


def test_aperturas_se_agrupan_por_familia():
    assert familia_apertura("Sicilian Defense: Najdorf Variation") == "Sicilian Defense"
    assert apertura_chesscom("https://www.chess.com/openings/Sicilian-Defense-Old-Sicilian-2...Nc6") == (
        "Sicilian Defense Old Sicilian"
    )
    assert familia_apertura("Sicilian Defense Old Sicilian") == "Sicilian Defense"
    assert apertura_chesscom("https://www.chess.com/openings/English-Opening-Agincourt-Defense...4.b3-Bd6") == (
        "English Opening Agincourt Defense"
    )
    assert apertura_chesscom("https://www.chess.com/openings/Kings-Pawn-Opening-2.Nf3") == "Kings Pawn Opening"


def test_partida_de_lichess_desde_el_lado_del_usuario():
    game = {
        "id": "abcd1234",
        "variant": "standard",
        "speed": "blitz",
        "status": "mate",
        "winner": "white",
        "lastMoveAt": 1794500000000,
        "players": {
            "white": {"user": {"id": "rival", "name": "Rival"}, "rating": 1500},
            "black": {"user": {"id": "ana", "name": "Ana"}, "rating": 1480},
        },
        "clock": {"initial": 180, "increment": 2},
        "opening": {"name": "Italian Game"},
        "pgn": PGN_PASTOR,
        "analysis": [{"eval": e.get("cp", 0)} if "cp" in e else {"mate": e["mate"]} for e in EVALS],
    }
    partida = desde_lichess(game, "Ana")
    assert (partida.color, partida.resultado, partida.control) == ("black", "perdio", "3+2")
    assert partida.url.endswith("/black")
    eval_inicial, evals, mejores = evals_de_lichess(partida)
    assert len(evals) == 7 and mejores == [None] * 7


def test_partida_de_chesscom_y_ajena():
    game = {
        "url": "https://www.chess.com/game/live/1",
        "uuid": "u-1",
        "pgn": PGN_PASTOR,
        "end_time": 1794500000,
        "time_control": "180",
        "time_class": "blitz",
        "rules": "chess",
        "eco": "https://www.chess.com/openings/Italian-Game-2...Nc6",
        "white": {"username": "Rival", "rating": 900, "result": "win"},
        "black": {"username": "Ana", "rating": 880, "result": "checkmated"},
    }
    partida = desde_chesscom(game, "ana")
    assert (partida.id, partida.color, partida.resultado, partida.apertura) == ("u-1", "black", "perdio", "Italian Game")
    assert partida.precision_oficial is None
    revisada = desde_chesscom({**game, "accuracies": {"white": 85.41, "black": 75.96}}, "ana")
    assert revisada.precision_oficial == {"white": 85.4, "black": 76.0}
    assert desde_chesscom(game, "otro") is None
    assert desde_chesscom({**game, "rules": "chess960"}, "ana") is None


def _entrada(**cambios) -> AnalisisIn:
    datos = dict(
        plataforma="chesscom",
        partida_id="u-1",
        color="black",
        ritmo="blitz",
        resultado="perdio",
        terminada_en=datetime(2026, 11, 16, tzinfo=timezone.utc),
        pgn=PGN_PASTOR,
        eval_inicial=EVAL_INICIAL,
        evals=EVALS,
        mejores=MEJORES,
    )
    datos.update(cambios)
    return AnalisisIn(**datos)


def test_guardar_del_navegador_calcula_los_totales(db, usuario_a, cuenta_a):
    fila = AnalisisService(db).guardar_del_navegador(usuario_a, _entrada())
    assert (fila.errores_graves, fila.fuente) == (1, "navegador")
    assert AnalisisService(db).precisiones(usuario_a.id, Plataforma.CHESSCOM, ["u-1"]) == {"u-1": fila.precision}

    otra = AnalisisService(db).guardar_del_navegador(usuario_a, _entrada(evals=[{"cp": 0}] * 7))
    assert otra.id == fila.id and otra.errores_graves == 0 and otra.segundas is None


def test_guardar_la_segunda_mejor_de_cada_posicion(db, usuario_a, cuenta_a):
    segundas = [{"cp": 10}, {"cp": 40}, None, {"mate": 2}, {"cp": -50}, {"cp": 300}, None]
    fila = AnalisisService(db).guardar_del_navegador(usuario_a, _entrada(segundas=segundas))
    assert fila.segundas == segundas
    with pytest.raises(ValidationError):
        AnalisisService(db).guardar_del_navegador(usuario_a, _entrada(segundas=segundas[:3]))


def test_guardar_del_navegador_rechaza_partidas_ajenas_o_incompletas(db, usuario_a, cuenta_a):
    servicio = AnalisisService(db)
    with pytest.raises(ValidationError):
        servicio.guardar_del_navegador(usuario_a, _entrada(color="white"))
    with pytest.raises(ValidationError):
        servicio.guardar_del_navegador(usuario_a, _entrada(evals=EVALS[:3]))
    with pytest.raises(ValidationError):
        servicio.guardar_del_navegador(usuario_a, _entrada(plataforma="lichess"))


class _Chesscom:
    def archivos(self, username):
        return [(2026, 10), (2026, 11)]

    def partidas_mes(self, username, anio, mes):
        base = {
            "pgn": PGN_PASTOR,
            "time_control": "180",
            "time_class": "blitz",
            "rules": "chess",
            "white": {"username": "Rival", "result": "win"},
            "black": {"username": "Ana", "result": "resigned"},
        }
        return [
            {**base, "url": f"https://www.chess.com/game/live/{mes}{d}", "uuid": f"{mes}-{d}",
             "end_time": int(datetime(anio, mes, d, tzinfo=timezone.utc).timestamp())}
            for d in (1, 15)
        ]


def test_lista_general_de_chesscom_mas_recientes_primero(db, usuario_a, cuenta_a):
    servicio = PartidasGeneralesService(db, chesscom=_Chesscom())
    partidas = servicio.listar(usuario_a, Plataforma.CHESSCOM, limite=3)
    assert [p.id for p in partidas] == ["11-15", "11-1", "10-15"]
    desde = datetime(2026, 11, 10, tzinfo=timezone.utc)
    assert [p.id for p in servicio.listar(usuario_a, Plataforma.CHESSCOM, desde=desde)] == ["11-15"]
    with pytest.raises(ValidationError):
        servicio.listar(usuario_a, Plataforma.LICHESS)
