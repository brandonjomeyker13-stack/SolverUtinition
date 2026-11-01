from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.chesscom import ritmo_desde_api, score_blanca
from app.clients.lichess import LichessClient
from app.core.elo import aplicar_partida
from app.core.exceptions import ValidationError
from app.models.cuenta_lichess import CuentaLichess
from app.models.enums import Plataforma, ResultadoPartida
from app.models.partida import Partida
from app.repositories.cuenta_lichess_repository import CuentaLichessRepository
from app.repositories.partida_repository import PartidaRepository
from app.repositories.rating_repository import RatingRepository
from app.services.sincronizacion_service import Candidata

_SIN_RESULTADO = frozenset({"created", "started", "aborted", "noStart"})
_TABLAS = frozenset({"draw", "stalemate"})


def partida_lichess_es_elegible(
    game: dict[str, Any],
    cuentas: dict[str, CuentaLichess],
) -> Candidata | None:
    """Estándar, bullet/blitz/rapid, y solo si ambos ya estaban vinculados al terminar."""
    if game.get("variant") != "standard":
        return None

    ritmo = ritmo_desde_api(str(game.get("speed") or ""))
    if ritmo is None:
        return None

    players = game.get("players") or {}
    blanca = _id_jugador(players.get("white"))
    negra = _id_jugador(players.get("black"))
    if blanca not in cuentas or negra not in cuentas or blanca == negra:
        return None

    fin = _instante_fin(game.get("lastMoveAt"))
    if fin is None:
        return None

    corte = max(cuentas[blanca].vinculada_en, cuentas[negra].vinculada_en)
    if corte.tzinfo is None:
        corte = corte.replace(tzinfo=timezone.utc)
    if fin <= corte:
        return None

    resultado = _resultado(game)
    if resultado is None:
        return None

    partida_id = str(game.get("id") or "")
    if not partida_id:
        return None

    return Candidata(
        plataforma_partida_id=partida_id,
        blanca_username=blanca,
        negra_username=negra,
        ritmo=ritmo,
        rated=bool(game.get("rated")),
        resultado=resultado,
        terminada_en=fin,
        url=f"https://lichess.org/{partida_id}",
        pgn=None,
    )


def _id_jugador(lado: Any) -> str:
    user = (lado or {}).get("user") or {}
    return str(user.get("id") or "").lower()


def _instante_fin(raw: Any) -> datetime | None:
    if not isinstance(raw, int):
        return None
    return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)


def _resultado(game: dict[str, Any]) -> ResultadoPartida | None:
    status = str(game.get("status") or "")
    if status in _SIN_RESULTADO:
        return None
    winner = game.get("winner")
    if winner == "white":
        return ResultadoPartida.BLANCA
    if winner == "black":
        return ResultadoPartida.NEGRA
    if status in _TABLAS:
        return ResultadoPartida.TABLAS
    return None


class SincronizacionLichessService:
    def __init__(self, db: Session, cliente: LichessClient | None = None):
        self.db = db
        self.cuentas = CuentaLichessRepository(db)
        self.partidas = PartidaRepository(db)
        self.ratings = RatingRepository(db)
        self.cliente = cliente or LichessClient()

    def sincronizar(self) -> dict[str, int]:
        cuentas = {c.username: c for c in self.cuentas.listar_todas()}
        return self._sincronizar_cuentas(cuentas, cuentas.values())

    def sincronizar_usuario(self, usuario_id: int) -> dict[str, int]:
        """Solo las partidas recientes de esta persona. Una petición a Lichess."""
        todas = {c.username: c for c in self.cuentas.listar_todas()}
        mia = next((c for c in todas.values() if c.usuario_id == usuario_id), None)
        if mia is None or len(todas) < 2:
            return {"revisadas": 0, "aplicadas": 0, "omitidas": 0}
        return self._sincronizar_cuentas(todas, [mia])

    def _sincronizar_cuentas(
        self,
        cuentas: dict[str, CuentaLichess],
        consultar: Iterable[CuentaLichess],
    ) -> dict[str, int]:
        if len(cuentas) < 2:
            return {"revisadas": 0, "aplicadas": 0, "omitidas": 0}

        crudas: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for cuenta in consultar:
            desde = cuenta.vinculada_en
            if desde.tzinfo is None:
                desde = desde.replace(tzinfo=timezone.utc)
            since_ms = int(desde.timestamp() * 1000)
            for game in self.cliente.partidas(cuenta.username, since_ms):
                clave = str(game.get("id") or "")
                if not clave or clave in vistos:
                    continue
                vistos.add(clave)
                crudas.append(game)

        candidatas = [c for g in crudas if (c := partida_lichess_es_elegible(g, cuentas))]
        candidatas.sort(key=lambda c: c.terminada_en)
        ya = self.partidas.ids_existentes(
            Plataforma.LICHESS, [c.plataforma_partida_id for c in candidatas]
        )

        aplicadas = 0
        omitidas = 0
        for item in candidatas:
            if item.plataforma_partida_id in ya:
                omitidas += 1
                continue
            try:
                self._aplicar(item, cuentas)
                aplicadas += 1
                ya.add(item.plataforma_partida_id)
            except IntegrityError:
                self.db.rollback()
                omitidas += 1
            except ValidationError:
                self.db.rollback()
                omitidas += 1

        return {"revisadas": len(crudas), "aplicadas": aplicadas, "omitidas": omitidas}

    def _aplicar(self, item: Candidata, cuentas: dict[str, CuentaLichess]) -> None:
        blanca = cuentas[item.blanca_username]
        negra = cuentas[item.negra_username]
        rating_blanca = self.ratings.get(blanca.usuario_id, item.ritmo)
        rating_negra = self.ratings.get(negra.usuario_id, item.ritmo)
        if rating_blanca is None or rating_negra is None:
            raise ValidationError("Faltan ratings iniciales")

        nuevo_b, nuevo_n, delta_b, delta_n = aplicar_partida(
            rating_blanca.elo,
            rating_negra.elo,
            score_blanca(item.resultado),
        )
        self.partidas.create(
            Partida(
                plataforma=Plataforma.LICHESS,
                plataforma_partida_id=item.plataforma_partida_id,
                blanca_id=blanca.usuario_id,
                negra_id=negra.usuario_id,
                ritmo=item.ritmo,
                rated_en_plataforma=item.rated,
                resultado=item.resultado,
                elo_blanca_antes=rating_blanca.elo,
                elo_negra_antes=rating_negra.elo,
                delta_blanca=delta_b,
                delta_negra=delta_n,
                terminada_en=item.terminada_en,
                url=item.url,
                pgn=item.pgn,
            )
        )
        rating_blanca.elo = nuevo_b
        rating_negra.elo = nuevo_n
        rating_blanca.partidas_jugadas += 1
        rating_negra.partidas_jugadas += 1
        self.db.commit()
