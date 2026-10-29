from app.core.exceptions import ConflictError, UnauthorizedError
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
