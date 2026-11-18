"""Partidas generales: todas las de la cuenta, no solo las jugadas contra miembros."""
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import chess
import chess.pgn

from app.clients.chesscom import RESULTADOS_TABLAS, instante_fin
from app.models.enums import Plataforma

_TABLAS_LICHESS = frozenset({"draw", "stalemate"})
_SIN_RESULTADO_LICHESS = frozenset({"created", "started", "aborted", "noStart"})
_PALABRAS_FAMILIA = ("Defense", "Opening", "Game", "Gambit", "Attack", "System")


@dataclass
class Jugador:
    nombre: str
    elo: int | None


@dataclass
class PartidaGeneral:
    plataforma: Plataforma
    id: str
    url: str
    pgn: str
    blancas: Jugador
    negras: Jugador
    color: str
    resultado: str
    ritmo: str
    control: str
    terminada_en: datetime
    apertura: str | None
    analisis_lichess: list[dict[str, Any]] | None = field(default=None, repr=False)
    # La de Chess.com, solo si alguien abrió el Game Review: {"white": 85.4, "black": 75.9}.
    precision_oficial: dict[str, float] | None = None


def _resultado(propio: str, rival: str, tablas: bool) -> str | None:
    if propio == "win":
        return "gano"
    if rival == "win":
        return "perdio"
    return "tablas" if tablas else None


def desde_lichess(game: dict[str, Any], username: str) -> PartidaGeneral | None:
    if game.get("variant") not in ("standard", "fromPosition") or game.get("status") in _SIN_RESULTADO_LICHESS:
        return None
    pgn = game.get("pgn")
    partida_id = str(game.get("id") or "")
    fin = game.get("lastMoveAt") or game.get("createdAt")
    if not pgn or not partida_id or not isinstance(fin, int):
        return None

    players = game.get("players") or {}
    lados = {c: players.get(c) or {} for c in ("white", "black")}
    clave = username.lower()
    color = next(
        (c for c, lado in lados.items() if str((lado.get("user") or {}).get("id") or "").lower() == clave),
        None,
    )
    if color is None:
        return None

    ganador = game.get("winner")
    resultado = (
        "gano" if ganador == color else "perdio" if ganador else
        "tablas" if game.get("status") in _TABLAS_LICHESS else None
    )
    if resultado is None:
        return None

    reloj = game.get("clock") or {}
    control = (
        f"{int(reloj.get('initial', 0)) // 60}+{int(reloj.get('increment', 0))}" if reloj else "—"
    )
    analisis = game.get("analysis")
    return PartidaGeneral(
        plataforma=Plataforma.LICHESS,
        id=partida_id,
        url=f"https://lichess.org/{partida_id}" + ("/black" if color == "black" else ""),
        pgn=pgn,
        blancas=_jugador_lichess(lados["white"]),
        negras=_jugador_lichess(lados["black"]),
        color=color,
        resultado=resultado,
        ritmo=str(game.get("speed") or game.get("perf") or ""),
        control=control,
        terminada_en=datetime.fromtimestamp(fin / 1000, tz=timezone.utc),
        apertura=(game.get("opening") or {}).get("name"),
        analisis_lichess=analisis if isinstance(analisis, list) and analisis else None,
    )


def _jugador_lichess(lado: dict[str, Any]) -> Jugador:
    user = lado.get("user") or {}
    nombre = user.get("name") or ("Stockfish" if lado.get("aiLevel") else "Anónimo")
    rating = lado.get("rating")
    return Jugador(str(nombre), int(rating) if isinstance(rating, int) else None)


def desde_chesscom(game: dict[str, Any], username: str) -> PartidaGeneral | None:
    if (game.get("rules") or "chess") != "chess":
        return None
    pgn = game.get("pgn")
    fin = instante_fin(game)
    url = game.get("url")
    if not pgn or fin is None or not url:
        return None

    white = game.get("white") or {}
    black = game.get("black") or {}
    clave = username.lower()
    if str(white.get("username") or "").lower() == clave:
        color, propio, rival = "white", white, black
    elif str(black.get("username") or "").lower() == clave:
        color, propio, rival = "black", black, white
    else:
        return None

    propio_res = str(propio.get("result") or "")
    rival_res = str(rival.get("result") or "")
    resultado = _resultado(
        propio_res, rival_res, propio_res in RESULTADOS_TABLAS or rival_res in RESULTADOS_TABLAS
    )
    if resultado is None:
        return None

    return PartidaGeneral(
        plataforma=Plataforma.CHESSCOM,
        id=str(game.get("uuid") or url.rstrip("/").split("/")[-1]),
        url=str(url),
        pgn=str(pgn),
        blancas=Jugador(str(white.get("username") or "?"), _entero(white.get("rating"))),
        negras=Jugador(str(black.get("username") or "?"), _entero(black.get("rating"))),
        color=color,
        resultado=resultado,
        ritmo=str(game.get("time_class") or ""),
        control=_control_chesscom(str(game.get("time_control") or "")),
        terminada_en=fin,
        apertura=apertura_chesscom(str(game.get("eco") or "")) or _cabecera(str(pgn), "Opening"),
        precision_oficial=_precisiones(game.get("accuracies")),
    )


def _precisiones(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict):
        return None
    try:
        return {"white": round(float(raw["white"]), 1), "black": round(float(raw["black"]), 1)}
    except (KeyError, TypeError, ValueError):
        return None


def _entero(valor: Any) -> int | None:
    return int(valor) if isinstance(valor, int) else None


def _control_chesscom(raw: str) -> str:
    if "/" in raw:
        return "diaria"
    base, _, inc = raw.partition("+")
    try:
        return f"{int(base) // 60}+{int(inc or 0)}" if int(base) >= 60 else f"{int(base)}s+{int(inc or 0)}"
    except ValueError:
        return raw or "—"


def apertura_chesscom(eco_url: str) -> str | None:
    """https://www.chess.com/openings/Sicilian-Defense-Old-Sicilian-2...Nc6 → Sicilian Defense Old Sicilian."""
    if "/openings/" not in eco_url:
        return None
    slug = eco_url.rstrip("/").split("/openings/")[-1]
    # Las jugadas vienen pegadas al nombre: "Agincourt-Defense...4.b3-Bd6" o "Defense-2.Nf3".
    slug = re.split(r"\.\.\.|-?\b\d+\.", slug, maxsplit=1)[0]
    return " ".join(p for p in slug.split("-") if p) or None


def _cabecera(pgn: str, nombre: str) -> str | None:
    m = re.search(rf'^\[{nombre} "([^"]*)"\]', pgn, flags=re.MULTILINE)
    return m.group(1) if m and m.group(1) not in ("", "?") else None


def familia_apertura(apertura: str | None) -> str | None:
    """'Sicilian Defense: Najdorf' y 'Sicilian Defense Old Sicilian' quedan en 'Sicilian Defense'."""
    if not apertura:
        return None
    base = apertura.split(":")[0].strip()
    palabras = base.split()
    for i, palabra in enumerate(palabras):
        if palabra in _PALABRAS_FAMILIA:
            return " ".join(palabras[: i + 1])
    return " ".join(palabras[:2]) or None


def leer_pgn(pgn: str) -> chess.pgn.Game | None:
    try:
        partida = chess.pgn.read_game(io.StringIO(pgn))
    except (ValueError, IndexError):
        return None
    if partida is None or partida.errors:
        return None
    return partida


def control_tiempo(partida: chess.pgn.Game) -> tuple[int, int] | None:
    """(base, incremento) en segundos, o None si es por correspondencia o no viene."""
    raw = partida.headers.get("TimeControl", "")
    if not raw or "/" in raw or raw == "-":
        return None
    base, _, inc = raw.partition("+")
    try:
        return int(base), int(inc or 0)
    except ValueError:
        return None


def tiempos(partida: chess.pgn.Game) -> list[tuple[float, float] | None]:
    """Por jugada: (reloj antes de jugar, segundos que tardó). None si el PGN no trae relojes."""
    control = control_tiempo(partida)
    salida: list[tuple[float, float] | None] = []
    if control is None:
        return [None for _ in partida.mainline()]
    base, inc = control
    ultimo = {chess.WHITE: float(base), chess.BLACK: float(base)}
    for nodo in partida.mainline():
        color = not nodo.board().turn
        reloj = nodo.clock()
        if reloj is None:
            salida.append(None)
            continue
        antes = ultimo[color]
        salida.append((antes, max(0.0, antes - reloj + inc)))
        ultimo[color] = reloj
    return salida
