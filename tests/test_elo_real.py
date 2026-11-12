from datetime import datetime, timedelta, timezone

from app.core.meses import rango_mes
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.cuenta_lichess import CuentaLichess
from app.models.elo_real import EloRealMes
from app.models.enums import Plataforma, Ritmo
from app.services.elo_real_service import (
    EloRealService,
    Mes,
    meses_a_refrescar,
    ratings_chesscom,
    resumen_chesscom,
    resumen_lichess,
)
from app.services.ranking_service import RankingService

NOVIEMBRE = Mes(*rango_mes("2026-11"))
COL = timezone(timedelta(hours=-5))


def _game(fin: datetime, rating: int, time_class: str = "blitz", rated: bool = True, uid: str = "") -> dict:
    return {
        "uuid": uid or f"g{fin.timestamp()}",
        "rules": "chess",
        "rated": rated,
        "time_class": time_class,
        "end_time": int(fin.timestamp()),
        "white": {"username": "Ana", "rating": rating},
        "black": {"username": "rival", "rating": 1500},
    }


def test_lichess_toma_el_cierre_del_mes_anterior_y_el_ultimo_del_mes():
    puntos = [[2026, 9, 20, 1400], [2026, 9, 31, 1420], [2026, 10, 3, 1450], [2026, 10, 9, 1480]]
    resumen = resumen_lichess(puntos, NOVIEMBRE)
    assert (resumen.elo_inicio, resumen.elo, resumen.partidas) == (1420, 1480, None)


def test_lichess_sin_partidas_en_el_mes_queda_en_cero():
    resumen = resumen_lichess([[2026, 8, 1, 1600]], NOVIEMBRE)
    assert (resumen.elo_inicio, resumen.elo) == (1600, 1600)


def test_lichess_cuenta_nueva_arranca_en_1500():
    resumen = resumen_lichess([[2026, 10, 5, 1620]], NOVIEMBRE)
    assert (resumen.elo_inicio, resumen.elo) == (1500, 1620)


def test_lichess_sin_historia_no_sale():
    assert resumen_lichess([[2026, 11, 1, 1700]], NOVIEMBRE) is None


def test_chesscom_usa_el_rating_despues_de_cada_partida():
    games = [
        _game(datetime(2026, 10, 30, 12, tzinfo=timezone.utc), 900),
        _game(datetime(2026, 11, 2, 12, tzinfo=timezone.utc), 910),
        _game(datetime(2026, 11, 8, 12, tzinfo=timezone.utc), 940),
        _game(datetime(2026, 11, 9, 12, tzinfo=timezone.utc), 999, rated=False),
        _game(datetime(2026, 11, 9, 12, tzinfo=timezone.utc), 1200, time_class="daily"),
        _game(datetime(2026, 11, 10, 12, tzinfo=timezone.utc), 1100, time_class="rapid"),
    ]
    eventos = ratings_chesscom(games, "ana")
    assert set(eventos) == {Ritmo.BLITZ, Ritmo.RAPID}
    blitz = resumen_chesscom(eventos[Ritmo.BLITZ], NOVIEMBRE)
    assert (blitz.elo_inicio, blitz.elo, blitz.partidas) == (900, 940, 2)
    rapid = resumen_chesscom(eventos[Ritmo.RAPID], NOVIEMBRE)
    assert (rapid.elo_inicio, rapid.elo, rapid.partidas) == (1100, 1100, 1)


def test_chesscom_la_noche_del_31_en_colombia_es_del_mes_anterior():
    noche = datetime(2026, 10, 31, 23, 30, tzinfo=COL)
    eventos = ratings_chesscom([_game(noche, 905)], "ana")[Ritmo.BLITZ]
    resumen = resumen_chesscom(eventos, NOVIEMBRE)
    assert (resumen.elo_inicio, resumen.elo, resumen.partidas) == (905, 905, 0)


def test_refresca_el_mes_en_curso_y_el_anterior():
    meses = meses_a_refrescar(datetime(2026, 12, 1, 2, tzinfo=timezone.utc))
    assert [m.etiqueta for m in meses] == ["2026-11", "2026-10"]


class _Lichess:
    def historial_rating(self, username):
        return [{"name": "Blitz", "points": [[2026, 9, 30, 1500], [2026, 10, 4, 1560]]}]


class _Chesscom:
    def __init__(self):
        self.pedidos = []

    def archivos(self, username):
        return [(2026, 8), (2026, 9), (2026, 10), (2026, 11)]

    def partidas_mes(self, username, anio, mes):
        self.pedidos.append((anio, mes))
        if (anio, mes) == (2026, 11):
            return [_game(datetime(2026, 11, 5, tzinfo=timezone.utc), 820)]
        if (anio, mes) == (2026, 9):
            return [_game(datetime(2026, 9, 5, tzinfo=timezone.utc), 800)]
        return []


def test_guarda_las_dos_plataformas_y_sale_en_su_tabla(db, usuario_a, usuario_b, cuenta_a):
    db.add(
        CuentaLichess(
            usuario_id=usuario_a.id,
            username="ana",
            username_visible="AnaLi",
            vinculada_en=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    chesscom = _Chesscom()
    EloRealService(db, lichess=_Lichess(), chesscom=chesscom).actualizar_usuario(
        usuario_a.id, ahora=datetime(2026, 11, 12, 15, tzinfo=timezone.utc)
    )
    assert chesscom.pedidos == [(2026, 10), (2026, 11), (2026, 9)]

    service = RankingService(db)
    lichess = service.listar_real(Plataforma.LICHESS, Ritmo.BLITZ, "2026-11").filas
    assert [(f.username, f.elo_inicio, f.elo, f.subida) for f in lichess] == [("AnaLi", 1500, 1560, 60)]

    cc = service.listar_real(Plataforma.CHESSCOM, Ritmo.BLITZ, "2026-11").filas
    assert [(f.username, f.elo_inicio, f.elo, f.subida, f.partidas) for f in cc] == [
        ("Ana", 800, 820, 20, 1)
    ]


def test_ordena_por_lo_que_subio_y_deja_fuera_a_quien_desvinculo(db, usuario_a, usuario_b, cuenta_a, cuenta_b):
    db.add_all(
        [
            EloRealMes(usuario_id=usuario_a.id, plataforma=Plataforma.CHESSCOM, ritmo=Ritmo.RAPID, mes="2026-11", elo_inicio=2000, elo=2010, partidas=3),
            EloRealMes(usuario_id=usuario_b.id, plataforma=Plataforma.CHESSCOM, ritmo=Ritmo.RAPID, mes="2026-11", elo_inicio=500, elo=600, partidas=9),
        ]
    )
    db.commit()
    filas = RankingService(db).listar_real(Plataforma.CHESSCOM, Ritmo.RAPID, "2026-11").filas
    assert [(f.nombre, f.subida, f.posicion) for f in filas] == [("Beto", 100, 1), ("Ana", 10, 2)]

    db.delete(db.get(CuentaChesscom, cuenta_b.id))
    db.commit()
    filas = RankingService(db).listar_real(Plataforma.CHESSCOM, Ritmo.RAPID, "2026-11").filas
    assert [f.nombre for f in filas] == ["Ana"]
