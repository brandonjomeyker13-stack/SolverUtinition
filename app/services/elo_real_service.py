import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.chesscom import ChesscomClient, instante_fin
from app.clients.lichess import LichessClient
from app.core.exceptions import ValidationError
from app.core.meses import rango_mes
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.cuenta_lichess import CuentaLichess
from app.models.elo_real import EloRealMes
from app.models.enums import VARIANTES_QUE_CUENTAN, Plataforma, Ritmo

logger = logging.getLogger(__name__)

LICHESS_RATING_INICIAL = 1500
_ARCHIVOS_HACIA_ATRAS = 3


@dataclass(frozen=True)
class Mes:
    etiqueta: str
    desde: datetime
    hasta: datetime


@dataclass(frozen=True)
class Resumen:
    elo_inicio: int
    elo: int
    partidas: int | None


def meses_a_refrescar(ahora: datetime | None = None) -> list[Mes]:
    """El mes en curso y el anterior, para no perder las partidas de la última noche."""
    etiqueta, desde, hasta = rango_mes(None, ahora)
    previo = rango_mes(None, (desde - timedelta(days=1)).astimezone(timezone.utc))
    return [Mes(etiqueta, desde, hasta), Mes(*previo)]


def resumen_lichess(puntos: Iterable[list[int]], mes: Mes) -> Resumen | None:
    """Los puntos de Lichess son el rating al cierre de cada día con partidas.

    Sin historia previa la cuenta arrancó el mes con el rating inicial de Lichess.
    """
    inicio_mes = mes.desde.date()
    fin_mes = mes.hasta.date()
    antes: int | None = None
    ultimo_del_mes: int | None = None
    for punto in puntos:
        try:
            dia = date(int(punto[0]), int(punto[1]) + 1, int(punto[2]))
            rating = int(punto[3])
        except (TypeError, ValueError, IndexError):
            continue
        if dia < inicio_mes:
            antes = rating
        elif dia < fin_mes:
            ultimo_del_mes = rating
    if antes is None and ultimo_del_mes is None:
        return None
    inicio = antes if antes is not None else LICHESS_RATING_INICIAL
    return Resumen(inicio, ultimo_del_mes if ultimo_del_mes is not None else inicio, None)


def ratings_chesscom(games: Iterable[dict[str, Any]], username: str) -> dict[Ritmo, list[tuple[datetime, int]]]:
    """Rating de la cuenta después de cada partida rated estándar, por ritmo y en orden."""
    clave = username.lower()
    salida: dict[Ritmo, list[tuple[datetime, int]]] = {}
    vistos: set[str] = set()
    for game in games:
        if (game.get("rules") or "chess") not in VARIANTES_QUE_CUENTAN or not game.get("rated"):
            continue
        try:
            ritmo = Ritmo(game.get("time_class") or "")
        except ValueError:
            continue
        lado = next(
            (
                game.get(color) or {}
                for color in ("white", "black")
                if str((game.get(color) or {}).get("username") or "").lower() == clave
            ),
            None,
        )
        fin = instante_fin(game)
        if lado is None or fin is None or not isinstance(lado.get("rating"), int):
            continue
        id_partida = str(game.get("uuid") or game.get("url") or fin.timestamp())
        if id_partida in vistos:
            continue
        vistos.add(id_partida)
        salida.setdefault(ritmo, []).append((fin, int(lado["rating"])))
    for lista in salida.values():
        lista.sort(key=lambda e: e[0])
    return salida


def resumen_chesscom(eventos: list[tuple[datetime, int]], mes: Mes) -> Resumen | None:
    """Chess.com da el rating después de cada partida, no el cambio.

    Sin partidas antes del mes, el inicio es el rating tras la primera del mes.
    """
    antes = [r for fin, r in eventos if fin < mes.desde]
    dentro = [r for fin, r in eventos if mes.desde <= fin < mes.hasta]
    if not antes and not dentro:
        return None
    inicio = antes[-1] if antes else dentro[0]
    return Resumen(inicio, dentro[-1] if dentro else inicio, len(dentro))


class EloRealService:
    def __init__(
        self,
        db: Session,
        lichess: LichessClient | None = None,
        chesscom: ChesscomClient | None = None,
    ):
        self.db = db
        self.lichess = lichess or LichessClient()
        self.chesscom = chesscom or ChesscomClient()

    def actualizar_usuario(self, usuario_id: int, ahora: datetime | None = None) -> None:
        meses = meses_a_refrescar(ahora)
        cuenta_l = self.db.scalar(select(CuentaLichess).where(CuentaLichess.usuario_id == usuario_id))
        cuenta_c = self.db.scalar(select(CuentaChesscom).where(CuentaChesscom.usuario_id == usuario_id))
        if cuenta_l is not None:
            self._con_aviso(lambda: self._lichess(cuenta_l, meses))
        if cuenta_c is not None:
            self._con_aviso(lambda: self._chesscom(cuenta_c, meses))
        self.db.commit()

    def actualizar_todos(self, ahora: datetime | None = None) -> None:
        meses = meses_a_refrescar(ahora)
        for cuenta_l in self.db.scalars(select(CuentaLichess)).all():
            self._con_aviso(lambda: self._lichess(cuenta_l, meses))
        for cuenta_c in self.db.scalars(select(CuentaChesscom)).all():
            self._con_aviso(lambda: self._chesscom(cuenta_c, meses))
        self.db.commit()

    def _con_aviso(self, paso) -> None:
        try:
            paso()
        except ValidationError as exc:
            logger.warning("No se pudo leer el rating real: %s", exc)

    def _lichess(self, cuenta: CuentaLichess, meses: list[Mes]) -> None:
        historial = self.lichess.historial_rating(cuenta.username)
        por_ritmo = {str(h.get("name") or "").lower(): h.get("points") or [] for h in historial}
        for ritmo in Ritmo:
            for mes in meses:
                resumen = resumen_lichess(por_ritmo.get(ritmo.value, []), mes)
                if resumen is not None:
                    self._guardar(cuenta.usuario_id, Plataforma.LICHESS, ritmo, mes, resumen)

    def _chesscom(self, cuenta: CuentaChesscom, meses: list[Mes]) -> None:
        archivos = self.chesscom.archivos(cuenta.username)
        if not archivos:
            return
        primero = min(m.desde for m in meses).astimezone(timezone.utc)
        recientes = [a for a in archivos if a >= (primero.year, primero.month)]
        viejos = [a for a in archivos if a < (primero.year, primero.month)]

        games: list[dict[str, Any]] = []
        for anio, numero in recientes:
            games.extend(self.chesscom.partidas_mes(cuenta.username, anio, numero))
        eventos = ratings_chesscom(games, cuenta.username)

        def falta_previa() -> bool:
            return any(not lista or lista[0][0] >= primero for lista in eventos.values())

        for anio, numero in list(reversed(viejos))[:_ARCHIVOS_HACIA_ATRAS]:
            if eventos and not falta_previa():
                break
            games.extend(self.chesscom.partidas_mes(cuenta.username, anio, numero))
            eventos = ratings_chesscom(games, cuenta.username)

        for ritmo, lista in eventos.items():
            for mes in meses:
                resumen = resumen_chesscom(lista, mes)
                if resumen is not None:
                    self._guardar(cuenta.usuario_id, Plataforma.CHESSCOM, ritmo, mes, resumen)

    def _guardar(
        self,
        usuario_id: int,
        plataforma: Plataforma,
        ritmo: Ritmo,
        mes: Mes,
        resumen: Resumen,
    ) -> None:
        fila = self.db.scalar(
            select(EloRealMes).where(
                EloRealMes.usuario_id == usuario_id,
                EloRealMes.plataforma == plataforma,
                EloRealMes.ritmo == ritmo,
                EloRealMes.mes == mes.etiqueta,
            )
        )
        if fila is None:
            fila = EloRealMes(usuario_id=usuario_id, plataforma=plataforma, ritmo=ritmo, mes=mes.etiqueta)
            self.db.add(fila)
        fila.elo_inicio = resumen.elo_inicio
        fila.elo = resumen.elo
        fila.partidas = resumen.partidas
