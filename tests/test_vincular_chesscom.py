import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.core.security import firmar_oauth_state
from app.services.chesscom_oauth_service import ChesscomOAuthService, normalizar_usuario_chesscom


class PerfilFalso:
    def __init__(self, location: str = "", player_id: int = 99, status: str = "basic"):
        self.location = location
        self.player_id = player_id
        self.status = status
        self.frescos = 0

    def perfil(self, username: str, fresco: bool = False) -> dict:
        if fresco:
            self.frescos += 1
        return {
            "username": "anachess",
            "url": "https://www.chess.com/member/AnaChess",
            "player_id": self.player_id,
            "status": self.status,
            "location": self.location,
        }


def test_pide_codigo_y_vincula_cuando_esta_en_la_ubicacion(db, usuario_a):
    cliente = PerfilFalso()
    service = ChesscomOAuthService(db, cliente=cliente)
    v = service.iniciar_verificacion(usuario_a, "https://www.chess.com/member/AnaChess")
    assert v.username_visible == "AnaChess"
    assert v.codigo.startswith("SU-") and len(v.codigo) == 9

    cliente.location = f"Bogotá {v.codigo.lower()}"
    cuenta = service.confirmar_verificacion(usuario_a, v.token)
    assert cuenta.username == "anachess"
    assert cuenta.chesscom_uuid == "99"
    assert cliente.frescos == 1


def test_no_vincula_sin_el_codigo(db, usuario_a):
    cliente = PerfilFalso(location="Bogotá")
    service = ChesscomOAuthService(db, cliente=cliente)
    v = service.iniciar_verificacion(usuario_a, "AnaChess")
    with pytest.raises(ValidationError, match="Todavía no vemos"):
        service.confirmar_verificacion(usuario_a, v.token)


def test_el_codigo_es_de_quien_lo_pidio(db, usuario_a, usuario_b):
    cliente = PerfilFalso()
    service = ChesscomOAuthService(db, cliente=cliente)
    v = service.iniciar_verificacion(usuario_a, "AnaChess")
    cliente.location = v.codigo
    with pytest.raises(ValidationError):
        service.confirmar_verificacion(usuario_b, v.token)


def test_rechaza_si_cambio_la_cuenta_detras_del_nombre(db, usuario_a):
    cliente = PerfilFalso()
    service = ChesscomOAuthService(db, cliente=cliente)
    v = service.iniciar_verificacion(usuario_a, "AnaChess")
    cliente.location = v.codigo
    cliente.player_id = 1234
    with pytest.raises(ValidationError, match="cambió"):
        service.confirmar_verificacion(usuario_a, v.token)


def test_codigo_vencido(db, usuario_a):
    token = firmar_oauth_state(
        {"p": "chesscom-ubicacion", "uid": usuario_a.id, "u": "anachess", "pid": "99", "c": "SU-AAAAAA"},
        minutos=-1,
    )
    with pytest.raises(ValidationError, match="venció"):
        ChesscomOAuthService(db, cliente=PerfilFalso()).confirmar_verificacion(usuario_a, token)


def test_no_sirve_un_state_de_otro_flujo(db, usuario_a):
    token = firmar_oauth_state({"uid": usuario_a.id, "cv": "x", "p": "lichess"})
    with pytest.raises(ValidationError):
        ChesscomOAuthService(db, cliente=PerfilFalso()).confirmar_verificacion(usuario_a, token)


def test_no_repite_el_mismo_usuario(db, usuario_a, usuario_b):
    cliente = PerfilFalso()
    service = ChesscomOAuthService(db, cliente=cliente)
    v = service.iniciar_verificacion(usuario_a, "AnaChess")
    cliente.location = v.codigo
    service.confirmar_verificacion(usuario_a, v.token)
    with pytest.raises(ConflictError):
        service.iniciar_verificacion(usuario_b, "AnaChess")


def test_rechaza_cuenta_cerrada_y_nombre_invalido(db, usuario_a):
    with pytest.raises(ValidationError, match="cerrada"):
        ChesscomOAuthService(db, cliente=PerfilFalso(status="closed:fair_play_violations")).iniciar_verificacion(
            usuario_a, "AnaChess"
        )
    with pytest.raises(ValidationError):
        ChesscomOAuthService(db, cliente=PerfilFalso()).iniciar_verificacion(usuario_a, "ana chess!")


def test_normaliza_el_usuario():
    assert normalizar_usuario_chesscom(" @AnaChess ") == "AnaChess"
    assert normalizar_usuario_chesscom("chess.com/member/AnaChess/") == "AnaChess"
