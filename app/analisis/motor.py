"""Stockfish en el servidor del resumen semanal (GitHub Actions), no en Render."""
import os

import chess
import chess.engine

from app.analisis.generales import leer_pgn


def _evaluacion(puntaje: chess.engine.PovScore) -> dict[str, int]:
    blancas = puntaje.white()
    if blancas.is_mate():
        return {"mate": int(blancas.mate())}
    return {"cp": int(blancas.score())}


def _final(tablero: chess.Board) -> dict[str, int] | None:
    if tablero.is_checkmate():
        return {"cp": -10_000 if tablero.turn == chess.WHITE else 10_000}
    if tablero.is_game_over(claim_draw=False):
        return {"cp": 0}
    return None


class Motor:
    def __init__(self, ruta: str, nodos: int):
        self.nodos = nodos
        self._engine = chess.engine.SimpleEngine.popen_uci(ruta)
        self._engine.configure({"Threads": max(1, os.cpu_count() or 1), "Hash": 128})

    def analizar_pgn(self, pgn: str) -> tuple[dict, list[dict], list[str | None], list[dict | None]] | None:
        juego = leer_pgn(pgn)
        if juego is None:
            return None
        tablero = juego.board()
        posiciones = [tablero.copy()]
        for jugada in juego.mainline_moves():
            tablero.push(jugada)
            posiciones.append(tablero.copy())

        evals: list[dict] = []
        mejores: list[str | None] = []
        segundas: list[dict | None] = []
        limite = chess.engine.Limit(nodes=self.nodos)
        for posicion in posiciones:
            fin = _final(posicion)
            if fin is not None:
                evals.append(fin)
                mejores.append(None)
                segundas.append(None)
                continue
            lineas = self._engine.analyse(posicion, limite, multipv=2)
            evals.append(_evaluacion(lineas[0]["score"]))
            pv = lineas[0].get("pv") or []
            mejores.append(pv[0].uci() if pv else None)
            segundas.append(_evaluacion(lineas[1]["score"]) if len(lineas) > 1 else None)
        # La evaluación de cada posición es la "después" de la jugada anterior.
        return evals[0], evals[1:], mejores[:-1], segundas[:-1]

    def cerrar(self) -> None:
        self._engine.quit()
