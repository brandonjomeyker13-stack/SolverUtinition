"""Reglas fijas que convierten los análisis de la semana en tres o cuatro frases cortas."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import chess

from app.analisis.generales import control_tiempo, familia_apertura, leer_pgn, tiempos
from app.analisis.metricas import jugadas
from app.models.analisis import AnalisisPartida

MAX_PUZZLES = 5
# "Rápido" es menos de 3 s o del 3 % del tiempo base; "mucho tiempo", más de la mitad.
_SEGUNDOS_RAPIDO = 3.0
_FRACCION_RAPIDO = 0.03
_FRACCION_HOLGADO = 0.5
_COLORES = {"white": "blancas", "black": "negras"}


@dataclass
class Resumen:
    titulo: str
    puntos: list[str]
    datos: dict[str, Any]


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def construir(analisis: list[AnalisisPartida]) -> Resumen | None:
    if not analisis:
        return None

    ganadas = sum(1 for a in analisis if a.resultado == "gano")
    perdidas = sum(1 for a in analisis if a.resultado == "perdio")
    tablas = len(analisis) - ganadas - perdidas
    precisiones = [a.precision for a in analisis if a.precision is not None]
    precision = round(sum(precisiones) / len(precisiones), 1) if precisiones else None

    apresuradas = 0
    perdidas_por_prisa = 0
    puzzles: list[dict[str, Any]] = []
    aperturas: dict[tuple[str, str], list[float]] = defaultdict(list)

    for a in analisis:
        familia = familia_apertura(a.apertura)
        if familia:
            puntos_partida = {"gano": 1.0, "tablas": 0.5}.get(a.resultado, 0.0)
            aperturas[(a.color, familia)].append(puntos_partida)

        juego = leer_pgn(a.pgn)
        if juego is None:
            continue
        nodos = list(juego.mainline())
        lista = jugadas(a.eval_inicial, a.evals, juego.board().turn == chess.WHITE)
        relojes = tiempos(juego)
        control = control_tiempo(juego)
        prisa_en_esta = False

        for jugada, nodo, reloj in zip(lista, nodos, relojes):
            if jugada.blancas != (a.color == "white") or jugada.clase not in ("error", "error_grave"):
                continue
            if control and reloj:
                base = control[0]
                antes, tardo = reloj
                if tardo <= max(_SEGUNDOS_RAPIDO, base * _FRACCION_RAPIDO) and antes >= base * _FRACCION_HOLGADO:
                    apresuradas += 1
                    prisa_en_esta = True
            mejor = a.mejores[jugada.indice] if jugada.indice < len(a.mejores) else None
            hecha = nodo.move.uci()
            if jugada.clase == "error_grave" and mejor and mejor != hecha:
                puzzles.append(
                    {
                        "fen": nodo.parent.board().fen(),
                        "solucion": mejor,
                        "jugada": hecha,
                        "caida": round(jugada.caida, 1),
                        "plataforma": a.plataforma.value,
                        "partida_id": a.partida_id,
                        "url": a.url,
                    }
                )
        if prisa_en_esta and a.resultado == "perdio":
            perdidas_por_prisa += 1

    puzzles.sort(key=lambda p: -p["caida"])
    vistos: set[str] = set()
    puzzles = [p for p in puzzles if not (p["fen"] in vistos or vistos.add(p["fen"]))][:MAX_PUZZLES]

    puntos: list[str] = []
    linea = (
        f"Jugaste {_plural(len(analisis), 'partida', 'partidas')}: "
        f"{ganadas} ganadas, {perdidas} perdidas y {tablas} tablas."
    )
    if precision is not None:
        linea += f" Precisión media: {precision:g} %."
    puntos.append(linea)

    if perdidas_por_prisa:
        puntos.append(
            f"Perdiste {_plural(perdidas_por_prisa, 'partida', 'partidas')} por errores rápidos "
            "teniendo mucho tiempo en el reloj."
        )
    elif apresuradas:
        puntos.append(
            f"Cometiste {_plural(apresuradas, 'error', 'errores')} jugando muy rápido con más de "
            "la mitad del tiempo. Respira antes de mover."
        )

    peor = _peor_apertura(aperturas)
    if peor:
        (color, familia), resultados = peor
        puntos.append(
            f"Con {_COLORES[color]}, tu apertura {familia} te está costando puntos: "
            f"{sum(resultados):g} de {len(resultados)}."
        )

    if puzzles:
        puntos.append(
            f"{'Este puzzle sale' if len(puzzles) == 1 else f'Estos {len(puzzles)} puzzles salen'} "
            "de tus propios errores."
        )

    titulo = "Tu semana de ajedrez"
    if perdidas_por_prisa:
        titulo = "Esta semana la prisa te costó partidas"
    elif precision is not None and precision >= 85:
        titulo = "Gran semana: jugaste muy preciso"

    datos = {
        "partidas": len(analisis),
        "ganadas": ganadas,
        "perdidas": perdidas,
        "tablas": tablas,
        "precision": precision,
        "errores_graves": sum(a.errores_graves for a in analisis),
        "apresuradas": apresuradas,
        "perdidas_por_prisa": perdidas_por_prisa,
        "aperturas": [
            {"color": c, "apertura": f, "puntos": sum(r), "partidas": len(r)}
            for (c, f), r in sorted(aperturas.items(), key=lambda kv: -len(kv[1]))
        ][:6],
        "puzzles": puzzles,
    }
    return Resumen(titulo, puntos, datos)


def _peor_apertura(aperturas: dict[tuple[str, str], list[float]]):
    candidatas = [
        (clave, r) for clave, r in aperturas.items() if len(r) >= 2 and sum(r) / len(r) <= 0.4
    ]
    if not candidatas:
        return None
    # Primero negras (es lo que más suele doler), luego la que más puntos dejó ir.
    return min(candidatas, key=lambda kv: (kv[0][0] != "black", sum(kv[1]) - len(kv[1])))
