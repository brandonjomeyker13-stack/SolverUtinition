from collections.abc import Iterable
from datetime import timezone
from typing import Any

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analisis.generales import PartidaGeneral, leer_pgn
from app.analisis.metricas import jugadas, totales
from app.core.exceptions import ValidationError
from app.models.analisis import AnalisisPartida
from app.models.enums import Plataforma
from app.models.usuario import Usuario
from app.schemas.analisis import AnalisisIn


def _username(usuario: Usuario, plataforma: Plataforma) -> str | None:
    cuenta = usuario.cuenta_lichess if plataforma == Plataforma.LICHESS else usuario.cuenta_chesscom
    return cuenta.username.lower() if cuenta else None


def _eval(raw: dict[str, Any]) -> dict[str, int]:
    if raw.get("mate") is not None:
        return {"mate": int(raw["mate"])}
    return {"cp": int(raw.get("cp") or 0)}


def evals_de_lichess(partida: PartidaGeneral) -> tuple[dict, list[dict], list[str | None]] | None:
    """Si alguien ya pidió el análisis en Lichess, se aprovecha tal cual."""
    analisis = partida.analisis_lichess
    juego = leer_pgn(partida.pgn)
    if not analisis or juego is None:
        return None
    plies = sum(1 for _ in juego.mainline())
    if len(analisis) < plies:
        return None
    evals: list[dict] = []
    mejores: list[str | None] = [None] * plies
    for i, item in enumerate(analisis[:plies]):
        if "mate" in item:
            evals.append({"mate": int(item["mate"])})
        elif "eval" in item:
            evals.append({"cp": int(item["eval"])})
        else:
            return None
        if item.get("best"):
            mejores[i] = str(item["best"])
    return {"cp": 20}, evals, mejores


class AnalisisService:
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, usuario_id: int, plataforma: Plataforma, partida_id: str) -> AnalisisPartida | None:
        return self.db.scalar(
            select(AnalisisPartida).where(
                AnalisisPartida.usuario_id == usuario_id,
                AnalisisPartida.plataforma == plataforma,
                AnalisisPartida.partida_id == partida_id,
            )
        )

    def precisiones(
        self, usuario_id: int, plataforma: Plataforma, ids: Iterable[str]
    ) -> dict[str, float | None]:
        ids = list(ids)
        if not ids:
            return {}
        filas = self.db.execute(
            select(AnalisisPartida.partida_id, AnalisisPartida.precision).where(
                AnalisisPartida.usuario_id == usuario_id,
                AnalisisPartida.plataforma == plataforma,
                AnalisisPartida.partida_id.in_(ids),
            )
        ).all()
        return {pid: precision for pid, precision in filas}

    def guardar_del_navegador(self, usuario: Usuario, datos: AnalisisIn) -> AnalisisPartida:
        username = _username(usuario, datos.plataforma)
        if username is None:
            raise ValidationError("Esa plataforma no está vinculada a tu cuenta")
        juego = leer_pgn(datos.pgn)
        if juego is None:
            raise ValidationError("El PGN no se pudo leer")
        cabecera = "White" if datos.color == "white" else "Black"
        if juego.headers.get(cabecera, "").lower() != username:
            raise ValidationError("Esa partida no es de tu cuenta")
        plies = sum(1 for _ in juego.mainline())
        if len(datos.evals) != plies or len(datos.mejores) != plies:
            raise ValidationError("El análisis no coincide con las jugadas de la partida")
        if datos.segundas is not None and len(datos.segundas) != plies:
            raise ValidationError("El análisis no coincide con las jugadas de la partida")
        return self.guardar(
            usuario_id=usuario.id,
            plataforma=datos.plataforma,
            partida_id=datos.partida_id,
            url=datos.url,
            color=datos.color,
            ritmo=datos.ritmo,
            resultado=datos.resultado,
            apertura=datos.apertura,
            terminada_en=datos.terminada_en,
            pgn=datos.pgn,
            eval_inicial=datos.eval_inicial.model_dump(),
            evals=[e.model_dump() for e in datos.evals],
            mejores=datos.mejores,
            segundas=None if datos.segundas is None else [s and s.model_dump() for s in datos.segundas],
            fuente="navegador",
            blancas_empiezan=juego.board().turn == chess.WHITE,
        )

    def guardar_partida(
        self,
        usuario_id: int,
        partida: PartidaGeneral,
        eval_inicial: dict,
        evals: list[dict],
        mejores: list[str | None],
        segundas: list[dict | None] | None = None,
        *,
        fuente: str,
    ) -> AnalisisPartida:
        juego = leer_pgn(partida.pgn)
        return self.guardar(
            usuario_id=usuario_id,
            plataforma=partida.plataforma,
            partida_id=partida.id,
            url=partida.url,
            color=partida.color,
            ritmo=partida.ritmo,
            resultado=partida.resultado,
            apertura=partida.apertura,
            terminada_en=partida.terminada_en,
            pgn=partida.pgn,
            eval_inicial=eval_inicial,
            evals=evals,
            mejores=mejores,
            segundas=segundas,
            fuente=fuente,
            blancas_empiezan=juego is None or juego.board().turn == chess.WHITE,
        )

    def guardar(self, *, usuario_id: int, plataforma: Plataforma, partida_id: str, blancas_empiezan: bool, **campos: Any) -> AnalisisPartida:
        eval_inicial = _eval(campos["eval_inicial"])
        evals = [_eval(e) for e in campos["evals"]]
        t = totales(jugadas(eval_inicial, evals, blancas_empiezan), campos["color"])
        fin = campos["terminada_en"]
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=timezone.utc)

        fila = self.obtener(usuario_id, plataforma, partida_id)
        if fila is None:
            fila = AnalisisPartida(usuario_id=usuario_id, plataforma=plataforma, partida_id=partida_id)
            self.db.add(fila)
        fila.url = campos.get("url")
        fila.color = campos["color"]
        fila.ritmo = campos["ritmo"][:20]
        fila.resultado = campos["resultado"]
        fila.apertura = (campos.get("apertura") or None) and campos["apertura"][:200]
        fila.terminada_en = fin
        fila.pgn = campos["pgn"]
        fila.eval_inicial = eval_inicial
        fila.evals = evals
        fila.mejores = list(campos["mejores"])
        segundas = campos.get("segundas")
        fila.segundas = None if segundas is None else [s and _eval(s) for s in segundas]
        fila.precision = t.precision
        fila.imprecisiones = t.imprecisiones
        fila.errores = t.errores
        fila.errores_graves = t.errores_graves
        fila.fuente = campos["fuente"]
        self.db.commit()
        self.db.refresh(fila)
        return fila
