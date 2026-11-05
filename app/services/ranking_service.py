from dataclasses import dataclass

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
        etiqueta, desde, hasta = rango_mes(mes)
        por_usuario: dict[int, _Mes] = {}
        for p in self.partidas.del_periodo(ritmo, desde, hasta, plataforma):
            puntos = _puntos_blanca(p.resultado)
            por_usuario.setdefault(p.blanca_id, _Mes()).sumar(p.delta_blanca, puntos)
            por_usuario.setdefault(p.negra_id, _Mes()).sumar(p.delta_negra, 1.0 - puntos)

        elos = self.ratings.elo_por_usuario(ritmo)
        cuentas = {c.usuario_id: c.username_visible for c in self.cuentas.listar_todas()}
        lichess = {c.usuario_id: c.username_visible for c in self.lichess.listar_todas()}

        orden = sorted(
            por_usuario.items(),
            key=lambda par: (-par[1].subida, -par[1].partidas, par[0]),
        )
        filas: list[RankingMensualFilaOut] = []
        for usuario_id, datos in orden:
            usuario = self.usuarios.get_by_id(usuario_id)
            if usuario is None or not usuario.activo:
                continue
            filas.append(
                RankingMensualFilaOut(
                    posicion=len(filas) + 1,
                    usuario_id=usuario_id,
                    nombre=usuario.nombre,
                    chesscom_username=cuentas.get(usuario_id),
                    lichess_username=lichess.get(usuario_id),
                    elo=elos.get(usuario_id, 0),
                    subida=datos.subida,
                    partidas=datos.partidas,
                    ganadas=datos.ganadas,
                    tablas=datos.tablas,
                    perdidas=datos.perdidas,
                )
            )
            if len(filas) >= limit:
                break

        return RankingMensualOut(
            mes=etiqueta,
            ritmo=ritmo,
            plataforma=plataforma,
            desde=desde,
            hasta=hasta,
            filas=filas,
        )
