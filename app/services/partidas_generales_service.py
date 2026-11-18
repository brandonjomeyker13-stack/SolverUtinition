from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.analisis.generales import PartidaGeneral, desde_chesscom, desde_lichess
from app.clients.chesscom import ChesscomClient
from app.clients.lichess import LichessClient
from app.core.exceptions import ValidationError
from app.models.enums import Plataforma
from app.models.usuario import Usuario

_ARCHIVOS_MAXIMOS = 3


class PartidasGeneralesService:
    def __init__(
        self,
        db: Session,
        lichess: LichessClient | None = None,
        chesscom: ChesscomClient | None = None,
    ):
        self.db = db
        self.lichess = lichess or LichessClient()
        self.chesscom = chesscom or ChesscomClient()

    def listar(
        self,
        usuario: Usuario,
        plataforma: Plataforma,
        limite: int = 30,
        desde: datetime | None = None,
    ) -> list[PartidaGeneral]:
        """Las más recientes primero. Con `desde`, solo las que terminaron después."""
        if plataforma == Plataforma.LICHESS:
            cuenta = usuario.cuenta_lichess
            if cuenta is None:
                raise ValidationError("Primero vincula tu cuenta de Lichess")
            since_ms = int(desde.timestamp() * 1000) if desde else None
            crudas = self.lichess.partidas_generales(cuenta.username, limite, since_ms)
            partidas = [p for g in crudas if (p := desde_lichess(g, cuenta.username))]
        else:
            cuenta = usuario.cuenta_chesscom
            if cuenta is None:
                raise ValidationError("Primero vincula tu cuenta de Chess.com")
            partidas = self._chesscom(cuenta.username, limite, desde)

        partidas.sort(key=lambda p: p.terminada_en, reverse=True)
        if desde is not None:
            corte = desde if desde.tzinfo else desde.replace(tzinfo=timezone.utc)
            partidas = [p for p in partidas if p.terminada_en >= corte]
        return partidas[:limite]

    def _chesscom(self, username: str, limite: int, desde: datetime | None) -> list[PartidaGeneral]:
        partidas: list[PartidaGeneral] = []
        for anio, mes in list(reversed(self.chesscom.archivos(username)))[:_ARCHIVOS_MAXIMOS]:
            for game in self.chesscom.partidas_mes(username, anio, mes):
                if (p := desde_chesscom(game, username)) is not None:
                    partidas.append(p)
            if len(partidas) >= limite:
                break
            if desde is not None and (anio, mes) <= (desde.year, desde.month):
                break
        return partidas
