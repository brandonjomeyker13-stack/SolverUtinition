"""Resumen semanal: `python -m app.jobs.resumen_semanal`.

Corre en GitHub Actions con Stockfish instalado. Analiza las partidas de los
últimos 7 días que nadie analizó todavía, arma el resumen y lo manda por push.
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

import chess.engine
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analisis.motor import Motor
from app.analisis.resumen import construir
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.meses import zona_ranking
from app.db.session import SessionLocal
from app.models.analisis import AnalisisPartida, ResumenSemanal
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.cuenta_lichess import CuentaLichess
from app.models.enums import Plataforma
from app.models.usuario import Usuario
from app.services.analisis_service import AnalisisService, evals_de_lichess
from app.services.partidas_generales_service import PartidasGeneralesService
from app.services.push_service import PushService

logger = logging.getLogger("resumen_semanal")


class _MotorPerezoso:
    """Stockfish solo arranca si de verdad hay algo que analizar."""

    def __init__(self) -> None:
        self._motor: Motor | None = None
        self._fallo = False

    def analizar(self, pgn: str):
        if self._fallo:
            return None
        if self._motor is None:
            try:
                self._motor = Motor(settings.STOCKFISH_PATH, settings.ANALISIS_NODOS)
            except (OSError, chess.engine.EngineError):
                self._fallo = True
                logger.exception("No arrancó Stockfish (%s); solo se usan análisis de Lichess", settings.STOCKFISH_PATH)
                return None
        return self._motor.analizar_pgn(pgn)

    def cerrar(self) -> None:
        if self._motor is not None:
            self._motor.cerrar()


def _analizar_semana(db: Session, usuario: Usuario, desde: datetime, motor: _MotorPerezoso) -> dict[str, int]:
    generales = PartidasGeneralesService(db)
    analisis = AnalisisService(db)
    cuenta = {"nuevas": 0, "reusadas": 0, "lichess": 0}
    plataformas = [
        p
        for p, cuenta_p in ((Plataforma.LICHESS, usuario.cuenta_lichess), (Plataforma.CHESSCOM, usuario.cuenta_chesscom))
        if cuenta_p is not None
    ]
    for plataforma in plataformas:
        try:
            partidas = generales.listar(usuario, plataforma, settings.RESUMEN_MAX_PARTIDAS, desde)
        except ValidationError as exc:
            logger.warning("usuario %s, %s: %s", usuario.id, plataforma.value, exc)
            continue
        for partida in partidas:
            if analisis.obtener(usuario.id, plataforma, partida.id) is not None:
                cuenta["reusadas"] += 1
                continue
            de_lichess = evals_de_lichess(partida)
            if de_lichess is not None:
                analisis.guardar_partida(usuario.id, partida, *de_lichess, fuente="lichess")
                cuenta["lichess"] += 1
                continue
            resultado = motor.analizar(partida.pgn)
            if resultado is None:
                continue
            analisis.guardar_partida(usuario.id, partida, *resultado, fuente="servidor")
            cuenta["nuevas"] += 1
    return cuenta


def _guardar_resumen(db: Session, usuario_id: int, desde: datetime, semana) -> ResumenSemanal | None:
    filas = db.scalars(
        select(AnalisisPartida)
        .where(AnalisisPartida.usuario_id == usuario_id, AnalisisPartida.terminada_en >= desde)
        .order_by(AnalisisPartida.terminada_en)
    ).all()
    resumen = construir(list(filas))
    if resumen is None:
        return None
    fila = db.scalar(
        select(ResumenSemanal).where(ResumenSemanal.usuario_id == usuario_id, ResumenSemanal.semana == semana)
    )
    if fila is None:
        fila = ResumenSemanal(usuario_id=usuario_id, semana=semana)
        db.add(fila)
    fila.titulo = resumen.titulo
    fila.puntos = resumen.puntos
    fila.datos = resumen.datos
    db.commit()
    return fila


def correr(dias: int = 7, usuario_id: int | None = None, push: bool = True) -> None:
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(days=dias)
    semana = ahora.astimezone(zona_ranking()).date()
    motor = _MotorPerezoso()
    db = SessionLocal()
    try:
        consulta = (
            select(Usuario)
            .outerjoin(CuentaLichess, CuentaLichess.usuario_id == Usuario.id)
            .outerjoin(CuentaChesscom, CuentaChesscom.usuario_id == Usuario.id)
            .where(Usuario.activo.is_(True), or_(CuentaLichess.id.isnot(None), CuentaChesscom.id.isnot(None)))
        )
        if usuario_id is not None:
            consulta = consulta.where(Usuario.id == usuario_id)
        for usuario in db.scalars(consulta).unique().all():
            try:
                cuenta = _analizar_semana(db, usuario, desde, motor)
                resumen = _guardar_resumen(db, usuario.id, desde, semana)
                enviadas = 0
                if resumen is not None and push and settings.push_listo:
                    enviadas = PushService(db).enviar(
                        usuario.id, resumen.titulo, " ".join(resumen.puntos[1:3] or resumen.puntos[:1]), "/resumen"
                    )
                logger.info(
                    "usuario %s: %s nuevas, %s de Lichess, %s ya estaban, resumen=%s, push=%s",
                    usuario.id, cuenta["nuevas"], cuenta["lichess"], cuenta["reusadas"], resumen is not None, enviadas,
                )
            except Exception:
                db.rollback()
                logger.exception("Falló el resumen del usuario %s", usuario.id)
    finally:
        motor.cerrar()
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Resumen semanal de partidas")
    parser.add_argument("--dias", type=int, default=7)
    parser.add_argument("--usuario", type=int, default=None)
    parser.add_argument("--sin-push", action="store_true")
    args = parser.parse_args()
    correr(args.dias, args.usuario, push=not args.sin_push)


if __name__ == "__main__":
    main()
