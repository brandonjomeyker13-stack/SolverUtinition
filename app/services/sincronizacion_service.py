from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.chesscom import (
    ChesscomClient,
    instante_fin,
    resultado_desde_api,
    ritmo_desde_api,
    score_blanca,
)
from app.core.elo import aplicar_partida
from app.core.exceptions import ValidationError
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.enums import VARIANTES_QUE_CUENTAN, Plataforma
from app.models.partida import Partida
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.partida_repository import PartidaRepository
from app.repositories.rating_repository import RatingRepository


@dataclass(frozen=True)
class Candidata:
    plataforma_partida_id: str
    blanca_username: str
    negra_username: str
    ritmo: Any
    rated: bool
    resultado: Any
    terminada_en: datetime
    url: str | None
    pgn: str | None


def partida_es_elegible(
    game: dict[str, Any],
    cuentas: dict[str, CuentaChesscom],
) -> Candidata | None:
    """Decide si una partida de Chess.com entra al ranking interno.

    Solo estándar, solo bullet/blitz/rapid, rated o no, y únicamente si
    ambos ya estaban vinculados cuando terminó (nada de historial viejo).
    """
    if (game.get("rules") or "chess") not in VARIANTES_QUE_CUENTAN:
        return None

    ritmo = ritmo_desde_api(game.get("time_class") or "")
    if ritmo is None:
        return None

    white = game.get("white") or {}
    black = game.get("black") or {}
    blanca = (white.get("username") or "").lower()
    negra = (black.get("username") or "").lower()
    if blanca not in cuentas or negra not in cuentas:
        return None
    if blanca == negra:
        return None

    fin = instante_fin(game)
    if fin is None:
        return None

    corte = max(cuentas[blanca].vinculada_en, cuentas[negra].vinculada_en)
    if corte.tzinfo is None:
        corte = corte.replace(tzinfo=timezone.utc)
    if fin <= corte:
        return None

    resultado = resultado_desde_api(white.get("result") or "", black.get("result") or "")
    if resultado is None:
        return None

    partida_id = str(game.get("uuid") or game.get("url") or "")
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
        url=game.get("url"),
        pgn=game.get("pgn"),
    )


class SincronizacionService:
    def __init__(self, db: Session, cliente: ChesscomClient | None = None):
        self.db = db
        self.cuentas = CuentaChesscomRepository(db)
        self.partidas = PartidaRepository(db)
        self.ratings = RatingRepository(db)
        self.cliente = cliente or ChesscomClient()

    def sincronizar(self) -> dict[str, int]:
        cuentas = {c.username: c for c in self.cuentas.listar_todas()}
        if len(cuentas) < 2:
            return {"revisadas": 0, "aplicadas": 0, "omitidas": 0}

        ahora = datetime.now(timezone.utc)
        meses = [(ahora.year, ahora.month)]
        if ahora.month == 1:
            meses.append((ahora.year - 1, 12))
        else:
            meses.append((ahora.year, ahora.month - 1))

        crudas: list[dict[str, Any]] = []
        vistos: set[str] = set()
        for cuenta in cuentas.values():
            for year, month in meses:
                for game in self.cliente.partidas_mes(cuenta.username, year, month):
                    clave = str(game.get("uuid") or game.get("url") or "")
                    if not clave or clave in vistos:
                        continue
                    vistos.add(clave)
                    crudas.append(game)

        candidatas = [c for g in crudas if (c := partida_es_elegible(g, cuentas))]
        candidatas.sort(key=lambda c: c.terminada_en)

        ya = self.partidas.ids_existentes(
            Plataforma.CHESSCOM, [c.plataforma_partida_id for c in candidatas]
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

    def _aplicar(self, item: Candidata, cuentas: dict[str, CuentaChesscom]) -> None:
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
                plataforma=Plataforma.CHESSCOM,
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
