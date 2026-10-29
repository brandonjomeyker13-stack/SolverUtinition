from app.core.config import settings


def esperada(elo_propio: int, elo_rival: int) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_rival - elo_propio) / 400.0))


def delta_elo(elo_propio: int, elo_rival: int, score: float, k: int | None = None) -> int:
    """Cambio entero de elo. score: 1 victoria, 0.5 tablas, 0 derrota."""
    factor = settings.ELO_K if k is None else k
    return round(factor * (score - esperada(elo_propio, elo_rival)))


def aplicar_partida(
    elo_blanca: int,
    elo_negra: int,
    score_blanca: float,
    k: int | None = None,
) -> tuple[int, int, int, int]:
    """Devuelve (elo_blanca_nuevo, elo_negra_nuevo, delta_blanca, delta_negra)."""
    cambio_blanca = delta_elo(elo_blanca, elo_negra, score_blanca, k)
    cambio_negra = delta_elo(elo_negra, elo_blanca, 1.0 - score_blanca, k)
    return (
        elo_blanca + cambio_blanca,
        elo_negra + cambio_negra,
        cambio_blanca,
        cambio_negra,
    )
