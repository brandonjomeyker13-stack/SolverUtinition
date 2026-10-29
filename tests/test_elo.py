from app.core.config import settings
from app.core.elo import aplicar_partida, delta_elo, esperada


def test_entre_iguales_la_esperada_es_media():
    assert esperada(1000, 1000) == 0.5


def test_victoria_entre_iguales_suma_la_mitad_de_k():
    cambio = delta_elo(1000, 1000, 1.0)
    assert cambio == round(settings.ELO_K * 0.5)


def test_tablas_entre_iguales_no_mueven():
    assert delta_elo(1000, 1000, 0.5) == 0


def test_aplicar_partida_es_simetrica():
    elo_b, elo_n, delta_b, delta_n = aplicar_partida(1000, 1000, 1.0)
    assert elo_b == 1000 + delta_b
    assert elo_n == 1000 + delta_n
    assert delta_b == -delta_n
