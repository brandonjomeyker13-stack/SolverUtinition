import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import CUENTA_NO_REGISTRADA, ConflictError, NotFoundError, UnauthorizedError
from app.core.google_auth import verificar_id_token_google
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import Ritmo
from app.models.rating import Rating
from app.models.refresh_token import RefreshToken
from app.models.usuario import Usuario
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.rating_repository import RatingRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.auth import LoginRequest, RegistroRequest
from app.schemas.usuario import CuentaChesscomOut, PerfilOut, RatingOut


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.refresh = RefreshTokenRepository(db)
        self.cuentas = CuentaChesscomRepository(db)
        self.ratings = RatingRepository(db)

    def registrar(self, data: RegistroRequest) -> Usuario:
        email = data.email.lower()
        if self.usuarios.get_by_email(email) is not None:
            raise ConflictError("Ya existe un usuario con ese email")

        usuario = self.usuarios.create(
            Usuario(
                nombre=data.nombre.strip(),
                email=email,
                password_hash=hash_password(data.password),
            )
        )
        self._asegurar_ratings(usuario.id)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def autenticar(self, credentials: LoginRequest) -> Usuario:
        usuario = self.usuarios.get_by_email(credentials.email.lower())
        if usuario is None or not usuario.activo:
            raise UnauthorizedError("Credenciales inválidas")
        if not verify_password(credentials.password, usuario.password_hash):
            raise UnauthorizedError("Credenciales inválidas")
        return usuario

    def autenticar_con_google(self, id_token: str) -> Usuario:
        usuario, _, _, _ = self._usuario_desde_google(id_token)
        if usuario is None:
            raise NotFoundError(
                "No hay una cuenta registrada con ese correo de Google. "
                "Crea tu cuenta primero y después entra con Google.",
                codigo=CUENTA_NO_REGISTRADA,
            )
        return usuario

    def registrar_con_google(self, id_token: str) -> Usuario:
        usuario, email, sub, nombre = self._usuario_desde_google(id_token)
        if usuario is not None:
            return usuario

        usuario = self.usuarios.create(
            Usuario(
                nombre=nombre,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                google_sub=sub,
            )
        )
        self._asegurar_ratings(usuario.id)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def _usuario_desde_google(self, id_token: str) -> tuple[Usuario | None, str, str, str]:
        claims = verificar_id_token_google(id_token)
        email = (claims.get("email") or "").strip().lower()
        sub = claims.get("sub")
        if not email or not sub:
            raise UnauthorizedError("Google no envió el correo de la cuenta")
        if not claims.get("email_verified"):
            raise UnauthorizedError("El correo de Google no está verificado")

        nombre = (claims.get("name") or email.split("@")[0] or "Jugador").strip()
        if len(nombre) < 2:
            nombre = "Jugador"

        por_sub = self.usuarios.get_by_google_sub(sub)
        if por_sub is not None:
            if not por_sub.activo:
                raise UnauthorizedError("Usuario no válido")
            return por_sub, email, sub, nombre

        usuario = self.usuarios.get_by_email(email)
        if usuario is None:
            return None, email, sub, nombre
        if not usuario.activo:
            raise UnauthorizedError("Usuario no válido")
        if usuario.google_sub and usuario.google_sub != sub:
            raise UnauthorizedError("Ese correo ya está vinculado a otra cuenta de Google")

        usuario.google_sub = sub
        self.db.commit()
        self.db.refresh(usuario)
        return usuario, email, sub, nombre

    def emitir_tokens(self, usuario: Usuario, ip: str | None, user_agent: str | None) -> tuple[str, str]:
        access = create_access_token(subject=str(usuario.id))
        raw_refresh = generate_refresh_token()
        self.refresh.create(
            RefreshToken(
                usuario_id=usuario.id,
                token_hash=hash_token(raw_refresh),
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                ip_origen=ip,
                user_agent=user_agent,
            )
        )
        self.refresh.eliminar_vencidos()
        self.db.commit()
        return access, raw_refresh

    def refrescar_access_token(self, raw_refresh: str) -> tuple[str, Usuario, str]:
        token = self.refresh.get_by_hash(hash_token(raw_refresh))
        if token is None or not self.refresh.es_valido(token):
            raise UnauthorizedError("No hay sesión activa")

        usuario = self.usuarios.get_by_id(token.usuario_id)
        if usuario is None or not usuario.activo:
            raise UnauthorizedError("Usuario no válido")

        token.revoked = True
        access, nuevo_refresh = self.emitir_tokens(usuario, token.ip_origen, token.user_agent)
        return access, usuario, nuevo_refresh

    def cerrar_sesion(self, raw_refresh: str) -> None:
        self.refresh.revocar(hash_token(raw_refresh))
        self.db.commit()

    def perfil(self, usuario: Usuario) -> PerfilOut:
        cuenta = self.cuentas.get_by_usuario_id(usuario.id)
        ratings = self.ratings.listar_de_usuario(usuario.id)
        return PerfilOut(
            id=usuario.id,
            nombre=usuario.nombre,
            email=usuario.email,
            activo=usuario.activo,
            created_at=usuario.created_at,
            updated_at=usuario.updated_at,
            chesscom=CuentaChesscomOut.model_validate(cuenta) if cuenta else None,
            ratings=[RatingOut.model_validate(r) for r in ratings],
        )

    def _asegurar_ratings(self, usuario_id: int) -> None:
        existentes = {r.ritmo for r in self.ratings.listar_de_usuario(usuario_id)}
        for ritmo in Ritmo:
            if ritmo not in existentes:
                self.ratings.create(
                    Rating(
                        usuario_id=usuario_id,
                        ritmo=ritmo,
                        elo=settings.ELO_INICIAL,
                        partidas_jugadas=0,
                    )
                )
