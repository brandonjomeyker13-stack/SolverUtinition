from datetime import datetime, timedelta, timezone

from app.core.meses import rango_mes
from app.models.enums import Plataforma, ResultadoPartida, Ritmo
from app.models.partida import Partida
from app.models.usuario import Usuario
from app.services.ranking_service import RankingService

NOV = datetime(2026, 11, 10, 18, tzinfo=timezone.utc)


def _partida(
    pid: str,
    blanca: Usuario,
    negra: Usuario,
    delta_blanca: int,
    resultado: ResultadoPartida,
    cuando: datetime = NOV,
    plataforma: Plataforma = Plataforma.LICHESS,
    ritmo: Ritmo = Ritmo.RAPID,
) -> Partida:
    return Partida(
        plataforma=plataforma,
        plataforma_partida_id=pid,
        blanca_id=blanca.id,
        negra_id=negra.id,
        ritmo=ritmo,
        rated_en_plataforma=True,
        resultado=resultado,
        elo_blanca_antes=1000,
        elo_negra_antes=1000,
        delta_blanca=delta_blanca,
        delta_negra=-delta_blanca,
        terminada_en=cuando,
    )


def test_el_mes_va_de_medianoche_a_medianoche_en_colombia():
    etiqueta, desde, hasta = rango_mes("2026-12")
    assert etiqueta == "2026-12"
    assert desde.astimezone(timezone.utc) == datetime(2026, 12, 1, 5, tzinfo=timezone.utc)
    assert hasta.astimezone(timezone.utc) == datetime(2027, 1, 1, 5, tzinfo=timezone.utc)


def test_sin_mes_usa_el_mes_en_curso_de_colombia():
    # 1 de dic a las 02:00 UTC todavía es 30 de nov en Colombia.
    etiqueta, _, _ = rango_mes(None, ahora=datetime(2026, 12, 1, 2, tzinfo=timezone.utc))
    assert etiqueta == "2026-11"


def test_gana_quien_mas_sube_en_el_mes(db, usuario_a, usuario_b):
    db.add_all(
        [
            _partida("p1", usuario_a, usuario_b, 10, ResultadoPartida.BLANCA),
            _partida("p2", usuario_b, usuario_a, -10, ResultadoPartida.NEGRA),
            _partida("p3", usuario_a, usuario_b, 0, ResultadoPartida.TABLAS),
        ]
    )
    db.commit()

    ranking = RankingService(db).listar_mensual(Ritmo.RAPID, "2026-11")
    ana, beto = ranking.filas
    assert ana.usuario_id == usuario_a.id
    assert (ana.subida, ana.partidas, ana.ganadas, ana.tablas, ana.perdidas) == (20, 3, 2, 1, 0)
    assert (beto.subida, beto.perdidas) == (-20, 2)
    assert ana.posicion == 1 and beto.posicion == 2


def test_cada_mes_empieza_en_cero(db, usuario_a, usuario_b):
    octubre = datetime(2026, 10, 15, tzinfo=timezone.utc)
    db.add(_partida("vieja", usuario_a, usuario_b, 10, ResultadoPartida.BLANCA, cuando=octubre))
    db.commit()

    assert RankingService(db).listar_mensual(Ritmo.RAPID, "2026-11").filas == []
    assert RankingService(db).listar_mensual(Ritmo.RAPID, "2026-10").filas[0].subida == 10


def test_la_ultima_noche_del_mes_cuenta_para_ese_mes(db, usuario_a, usuario_b):
    # 30 de nov 23:30 en Colombia = 1 de dic 04:30 UTC.
    noche = datetime(2026, 11, 30, 23, 30, tzinfo=timezone(timedelta(hours=-5))).astimezone(
        timezone.utc
    )
    db.add(_partida("noche", usuario_a, usuario_b, 10, ResultadoPartida.BLANCA, cuando=noche))
    db.commit()

    assert len(RankingService(db).listar_mensual(Ritmo.RAPID, "2026-11").filas) == 2
    assert RankingService(db).listar_mensual(Ritmo.RAPID, "2026-12").filas == []


def test_filtra_por_plataforma_y_ritmo(db, usuario_a, usuario_b):
    db.add_all(
        [
            _partida("li", usuario_a, usuario_b, 10, ResultadoPartida.BLANCA),
            _partida(
                "cc",
                usuario_b,
                usuario_a,
                10,
                ResultadoPartida.BLANCA,
                plataforma=Plataforma.CHESSCOM,
            ),
            _partida("bz", usuario_b, usuario_a, 10, ResultadoPartida.BLANCA, ritmo=Ritmo.BLITZ),
        ]
    )
    db.commit()
    service = RankingService(db)

    solo_lichess = service.listar_mensual(Ritmo.RAPID, "2026-11", Plataforma.LICHESS)
    assert solo_lichess.filas[0].usuario_id == usuario_a.id
    assert solo_lichess.filas[0].subida == 10

    ambas = service.listar_mensual(Ritmo.RAPID, "2026-11")
    assert {f.usuario_id: f.subida for f in ambas.filas} == {usuario_a.id: 0, usuario_b.id: 0}

    blitz = service.listar_mensual(Ritmo.BLITZ, "2026-11", Plataforma.LICHESS)
    assert blitz.filas[0].usuario_id == usuario_b.id
