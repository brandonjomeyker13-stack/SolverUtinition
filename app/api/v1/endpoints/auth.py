from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RefreshRequest, RegistroRequest, TokenResponse
from app.schemas.usuario import PerfilOut
from app.services.auth_service import AuthService
from app.core.deps import get_current_usuario


router = APIRouter(prefix="/auth", tags=["auth"])


def _cliente(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else None
    if not ip and request.client:
        ip = request.client.host
    agente = request.headers.get("user-agent")
    return (ip[:45] if ip else None), (agente[:255] if agente else None)


def _emitir(service: AuthService, usuario: Usuario, request: Request) -> TokenResponse:
    ip, agente = _cliente(request)
    access, refresh = service.emitir_tokens(usuario, ip, agente)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        usuario=service.perfil(usuario),
    )


@router.post("/registro", response_model=TokenResponse)
def registro(data: RegistroRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    usuario = service.registrar(data)
    return _emitir(service, usuario, request)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    usuario = service.autenticar(data)
    return _emitir(service, usuario, request)


@router.post("/google", response_model=TokenResponse)
def google(data: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    usuario = service.autenticar_con_google(data.id_token)
    return _emitir(service, usuario, request)


@router.post("/google/registro", response_model=TokenResponse)
def google_registro(
    data: GoogleAuthRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    service = AuthService(db)
    usuario = service.registrar_con_google(data.id_token)
    return _emitir(service, usuario, request)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    access, usuario, nuevo = service.refrescar_access_token(data.refresh_token or "")
    return TokenResponse(
        access_token=access,
        refresh_token=nuevo,
        usuario=service.perfil(usuario),
    )


@router.post("/logout", status_code=204)
def logout(data: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    if data.refresh_token:
        AuthService(db).cerrar_sesion(data.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=PerfilOut)
def me(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)) -> PerfilOut:
    return AuthService(db).perfil(usuario)
