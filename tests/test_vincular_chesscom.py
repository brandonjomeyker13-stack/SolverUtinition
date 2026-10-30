from app.core.exceptions import ConflictError
from app.services.chesscom_oauth_service import ChesscomOAuthService


class PerfilFalso:
    def perfil(self, username: str) -> dict:
        return {"username": "AnaChess", "player_id": 99}


def test_vincula_username_publico(db, usuario_a):
    cuenta = ChesscomOAuthService(db, cliente=PerfilFalso()).vincular_por_username(usuario_a, "AnaChess")
    assert cuenta.username == "anachess"
    assert cuenta.username_visible == "AnaChess"
    assert cuenta.chesscom_uuid == "99"


def test_no_repite_el_mismo_username(db, usuario_a, usuario_b):
    service = ChesscomOAuthService(db, cliente=PerfilFalso())
    service.vincular_por_username(usuario_a, "AnaChess")
    try:
        service.vincular_por_username(usuario_b, "AnaChess")
        raise AssertionError("debía fallar")
    except ConflictError:
        pass
