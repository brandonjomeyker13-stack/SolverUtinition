from unittest.mock import patch

from app.core.exceptions import CUENTA_NO_REGISTRADA, ConflictError, NotFoundError, UnauthorizedError
from app.schemas.auth import LoginRequest, RegistroRequest
from app.services.auth_service import AuthService


def test_registro_crea_ratings_en_1000(db):
    service = AuthService(db)
    usuario = service.registrar(
        RegistroRequest(nombre="Carla", email="Carla@Prueba.com", password="clave-segura-1")
    )
    perfil = service.perfil(usuario)
    assert usuario.email == "carla@prueba.com"
    assert {r.ritmo.value: r.elo for r in perfil.ratings} == {
        "bullet": 1000,
        "blitz": 1000,
        "rapid": 1000,
    }


def test_email_duplicado(db, usuario_a):
    service = AuthService(db)
    try:
        service.registrar(
            RegistroRequest(nombre="Otra", email="ana@prueba.com", password="clave-segura-1")
        )
        raise AssertionError("debía fallar")
    except ConflictError:
        pass


def test_login_ok_y_malo(db, usuario_a):
    service = AuthService(db)
    ok = service.autenticar(LoginRequest(email="ana@prueba.com", password="clave-de-prueba-123"))
    assert ok.id == usuario_a.id
    try:
        service.autenticar(LoginRequest(email="ana@prueba.com", password="no"))
        raise AssertionError("debía fallar")
    except UnauthorizedError:
        pass


def _claims(email: str = "ana@prueba.com", sub: str = "google-ana") -> dict:
    return {"email": email, "email_verified": True, "sub": sub, "name": "Ana"}


def test_google_sin_cuenta_avisa_con_codigo(db):
    service = AuthService(db)
    with patch("app.services.auth_service.verificar_id_token_google", return_value=_claims()):
        try:
            service.autenticar_con_google("token-falso")
            raise AssertionError("debía fallar")
        except NotFoundError as exc:
            assert exc.codigo == CUENTA_NO_REGISTRADA


def test_google_con_cuenta_vincula_y_entra(db, usuario_a):
    service = AuthService(db)
    with patch("app.services.auth_service.verificar_id_token_google", return_value=_claims()):
        usuario = service.autenticar_con_google("token-falso")
    assert usuario.id == usuario_a.id
    assert usuario.google_sub == "google-ana"


def test_registro_google_crea_cuenta_en_1000(db):
    service = AuthService(db)
    with patch(
        "app.services.auth_service.verificar_id_token_google",
        return_value=_claims(email="nueva@prueba.com", sub="google-nueva"),
    ):
        usuario = service.registrar_con_google("token-falso")
    perfil = service.perfil(usuario)
    assert usuario.email == "nueva@prueba.com"
    assert usuario.google_sub == "google-nueva"
    assert {r.elo for r in perfil.ratings} == {1000}


def test_refresh_rota_el_token_y_el_viejo_deja_de_servir(db, usuario_a):
    service = AuthService(db)
    _access, refresh = service.emitir_tokens(usuario_a, None, None)
    _nuevo_access, usuario, nuevo = service.refrescar_access_token(refresh)
    assert usuario.id == usuario_a.id
    assert nuevo != refresh
    try:
        service.refrescar_access_token(refresh)
        raise AssertionError("el token viejo debía dejar de servir")
    except UnauthorizedError:
        pass


def test_google_correo_no_verificado(db, usuario_a):
    service = AuthService(db)
    claims = _claims()
    claims["email_verified"] = False
    with patch("app.services.auth_service.verificar_id_token_google", return_value=claims):
        try:
            service.autenticar_con_google("token-falso")
            raise AssertionError("debía fallar")
        except UnauthorizedError:
            pass
