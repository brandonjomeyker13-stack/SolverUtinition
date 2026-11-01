from datetime import datetime, timezone

from app.core.exceptions import ConflictError, ValidationError
from app.core.security import firmar_oauth_state
from app.models.cuenta_chesscom import CuentaChesscom
from app.services.chesscom_oauth_service import ChesscomOAuthService
from app.services.lichess_oauth_service import LichessOAuthService


class ClienteFalso:
    def __init__(self):
        self.revocado = False

    def url_autorizacion(self, state: str, code_challenge: str) -> str:
        return f"https://lichess.org/oauth?state={state}&code_challenge={code_challenge}"

    def intercambiar_codigo(self, code: str, verifier: str) -> dict:
        return {"access_token": "tok"}

    def cuenta(self, token: str) -> dict:
        return {"id": "ana", "username": "Ana"}

    def revocar(self, token: str) -> None:
        self.revocado = True


class PerfilChess:
    def perfil(self, username: str) -> dict:
        return {"username": username, "player_id": 1}


def _state(usuario_id: int) -> str:
    return firmar_oauth_state({"uid": usuario_id, "cv": "verifier", "p": "lichess"})


def test_vincula_y_revoca_el_token(db, usuario_a, monkeypatch):
    monkeypatch.setattr("app.services.lichess_oauth_service.settings.LICHESS_CLIENT_ID", "app-prueba")
    cliente = ClienteFalso()
    service = LichessOAuthService(db, cliente=cliente)
    cuenta = service.completar("codigo", _state(usuario_a.id))
    assert cuenta.username == "ana"
    assert cuenta.username_visible == "Ana"
    assert cliente.revocado is True
    assert service.auth.perfil(usuario_a).lichess.username == "ana"


def test_la_misma_cuenta_de_lichess_no_se_repite(db, usuario_a, usuario_b):
    service = LichessOAuthService(db, cliente=ClienteFalso())
    service.completar("codigo", _state(usuario_a.id))
    try:
        service.completar("codigo", _state(usuario_b.id))
        raise AssertionError("debía fallar")
    except ConflictError:
        pass


def test_no_vincula_lichess_si_ya_tiene_chesscom(db, usuario_a):
    db.add(
        CuentaChesscom(
            usuario_id=usuario_a.id,
            username="ana",
            username_visible="Ana",
            vinculada_en=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    try:
        LichessOAuthService(db, cliente=ClienteFalso()).completar("codigo", _state(usuario_a.id))
        raise AssertionError("debía fallar")
    except ConflictError:
        pass


def test_no_vincula_chesscom_si_ya_tiene_lichess(db, usuario_a):
    LichessOAuthService(db, cliente=ClienteFalso()).completar("codigo", _state(usuario_a.id))
    try:
        ChesscomOAuthService(db, cliente=PerfilChess()).vincular_por_username(usuario_a, "AnaChess")
        raise AssertionError("debía fallar")
    except ConflictError:
        pass


def test_url_exige_client_id(db, usuario_a, monkeypatch):
    monkeypatch.setattr("app.services.lichess_oauth_service.settings.LICHESS_CLIENT_ID", None)
    try:
        LichessOAuthService(db, cliente=ClienteFalso()).url_de_conexion(usuario_a)
        raise AssertionError("debía fallar")
    except ValidationError:
        pass


def test_url_de_conexion_lleva_pkce(db, usuario_a, monkeypatch):
    monkeypatch.setattr("app.services.lichess_oauth_service.settings.LICHESS_CLIENT_ID", "app-prueba")
    url = LichessOAuthService(db, cliente=ClienteFalso()).url_de_conexion(usuario_a)
    assert "code_challenge=" in url
    assert "lichess.org/oauth" in url
