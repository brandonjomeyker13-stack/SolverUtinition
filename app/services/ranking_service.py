from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.meses import rango_mes
from app.models.enums import Plataforma, ResultadoPartida, Ritmo
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.cuenta_lichess_repository import CuentaLichessRepository
from app.repositories.partida_repository import PartidaRepository
from app.repositories.rating_repository import RatingRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.ranking import RankingFilaOut, RankingMensualFilaOut, RankingMensualOut


@dataclass
class _Mes:
    subida: int = 0
    partidas: int = 0
    ganadas: int = 0
    tablas: int = 0
    perdidas: int = 0

    def sumar(self, delta: int, puntos: float) -> None:
        self.subida += delta
        self.partidas += 1
        if puntos == 1.0:
            self.ganadas += 1
        elif puntos == 0.0:
            self.perdidas += 1
        else:
            self.tablas += 1


def _en_utc(instante: datetime) -> datetime:
    return instante.replace(tzinfo=timezone.utc) if instante.tzinfo is None else instante


def _puntos_blanca(resultado: ResultadoPartida) -> float:
    if resultado == ResultadoPartida.BLANCA:
        return 1.0
    if resultado == ResultadoPartida.NEGRA:
        return 0.0
    return 0.5


class RankingService:
    def __init__(self, db: Session):
        self.ratings = RatingRepository(db)
        self.usuarios = UsuarioRepository(db)
        self.partidas = PartidaRepository(db)
        self.cuentas = CuentaChesscomRepository(db)
        self.lichess = CuentaLichessRepository(db)

    def listar(self, ritmo: Ritmo, limit: int = 100) -> list[RankingFilaOut]:
        filas = self.ratings.ranking(ritmo, limit)
        cuentas = {c.usuario_id: c.username_visible for c in self.cuentas.listar_todas()}
        lichess = {c.usuario_id: c.username_visible for c in self.lichess.listar_todas()}
        salida: list[RankingFilaOut] = []
        for posicion, rating in enumerate(filas, start=1):
            usuario = self.usuarios.get_by_id(rating.usuario_id)
            if usuario is None or not usuario.activo:
                continue
            salida.append(
                RankingFilaOut(
                    posicion=posicion,
                    usuario_id=usuario.id,
                    nombre=usuario.nombre,
                    chesscom_username=cuentas.get(usuario.id),
                    lichess_username=lichess.get(usuario.id),
                    ritmo=ritmo,
                    elo=rating.elo,
                    partidas_jugadas=rating.partidas_jugadas,
                )
            )
        return salida

    def listar_mensual(
        self,
        ritmo: Ritmo,
        mes: str | None = None,
        plataforma: Plataforma | None = None,
        limit: int = 100,
    ) -> RankingMensualOut:
        """Todos los vinculados salen, aunque no hayan jugado (+0).

        El elo con el que cada uno empezó el mes se reconstruye desde el actual
        restando lo que movieron las partidas posteriores al día 1: no hace
        falta guardar una foto ni un cron.
        """
        etiqueta, desde, hasta = rango_mes(mes)
        elos = self.ratings.elo_por_usuario(ritmo)
        desde_inicio: dict[int, int] = defaultdict(int)
        desde_cierre: dict[int, int] = defaultdict(int)
        del_mes: dict[int, _Mes] = {}
        for p in self.partidas.desde_instante(ritmo, desde):
            fin = _en_utc(p.terminada_en)
            for usuario_id, delta in ((p.blanca_id, p.delta_blanca), (p.negra_id, p.delta_negra)):
                desde_inicio[usuario_id] += delta
                if fin >= hasta:
                    desde_cierre[usuario_id] += delta
            if fin < hasta and (plataforma is None or p.plataforma == plataforma):
                puntos = _puntos_blanca(p.resultado)
                del_mes.setdefault(p.blanca_id, _Mes()).sumar(p.delta_blanca, puntos)
                del_mes.setdefault(p.negra_id, _Mes()).sumar(p.delta_negra, 1.0 - puntos)

        cuentas = {c.usuario_id: c.username_visible for c in self.cuentas.listar_todas()}
        lichess = {c.usuario_id: c.username_visible for c in self.lichess.listar_todas()}
        if plataforma == Plataforma.LICHESS:
            vinculados = set(lichess)
        elif plataforma == Plataforma.CHESSCOM:
            vinculados = set(cuentas)
        else:
            vinculados = set(lichess) | set(cuentas)

        candidatas: list[tuple[int, str, int, int, _Mes]] = []
        for usuario_id in (vinculados | set(del_mes)) & set(elos):
            usuario = self.usuarios.get_by_id(usuario_id)
            if usuario is None or not usuario.activo:
                continue
            actual = elos[usuario_id]
            candidatas.append(
                (
                    usuario_id,
                    usuario.nombre,
                    actual - desde_inicio[usuario_id],
                    actual - desde_cierre[usuario_id],
                    del_mes.get(usuario_id, _Mes()),
                )
            )
        candidatas.sort(key=lambda c: (-c[4].subida, -c[4].partidas, -c[3], c[0]))

        filas = [
            RankingMensualFilaOut(
                posicion=posicion,
                usuario_id=usuario_id,
                nombre=nombre,
                chesscom_username=cuentas.get(usuario_id),
                lichess_username=lichess.get(usuario_id),
                elo_inicio=inicio,
                elo=cierre,
                subida=datos.subida,
                partidas=datos.partidas,
                ganadas=datos.ganadas,
                tablas=datos.tablas,
                perdidas=datos.perdidas,
            )
            for posicion, (usuario_id, nombre, inicio, cierre, datos) in enumerate(
                candidatas[:limit], start=1
            )
        ]

        return RankingMensualOut(
            mes=etiqueta,
            ritmo=ritmo,
            plataforma=plataforma,
            desde=desde,
            hasta=hasta,
            filas=filas,
        )
