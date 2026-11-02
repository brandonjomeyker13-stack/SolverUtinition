from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.chesscom import generar_pkce
from app.clients.lichess import LichessClient
from app.core.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.security import firmar_oauth_state, leer_oauth_state
from app.models.cuenta_lichess import CuentaLichess
from app.models.usuario import Usuario
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.cuenta_lichess_repository import CuentaLichessRepository
from app.services.auth_service import AuthService


def identidad_lichess(perfil: dict[str, Any]) -> tuple[str, str]:
    lichess_id = str(perfil.get("id") or perfil.get("username") or "").strip().lower()
    visible = str(perfil.get("username") or perfil.get("id") or lichess_id).strip()
    if not lichess_id:
        raise ValidationError("Lichess no envió el usuario")
    return lichess_id, visible or lichess_id


def normalizar_usuario_lichess(raw: str) -> str:
    texto = raw.strip()
    for prefijo in (
        "https://lichess.org/@/",
        "http://lichess.org/@/",
        "https://lichess.org/",
        "http://lichess.org/",
    ):
        if texto.lower().startswith(prefijo):
            texto = texto[len(prefijo) :]
            break
    return texto.lstrip("@").strip()


class LichessOAuthService:
    def __init__(self, db: Session, cliente: LichessClient | None = None):
        self.db = db
        self.cuentas = CuentaLichessRepository(db)
        self.chesscom = CuentaChesscomRepository(db)
        self.auth = AuthService(db)
        self.cliente = cliente or LichessClient()

    def url_de_conexion(self, usuario: Usuario) -> str:
        if not settings.lichess_oauth_listo:
            raise ValidationError(
                "Falta LICHESS_CLIENT_ID. Elige un identificador único y ponlo en el entorno."
            )
        self._exigir_puede_vincular(usuario.id)
        verifier, challenge = generar_pkce()
        state = firmar_oauth_state(
            {"uid": usuario.id, "cv": verifier, "p": "lichess"},
            minutos=60,
        )
        return self.cliente.url_autorizacion(state, challenge)

    def completar(self, code: str, state: str) -> CuentaLichess:
        claims = leer_oauth_state(state)
        if claims.get("p") != "lichess":
            raise ValidationError("La autorización no corresponde a Lichess")
        try:
            usuario_id = int(claims["uid"])
            verifier = str(claims["cv"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("La autorización de Lichess no es válida") from exc

        self._exigir_puede_vincular(usuario_id)

        tokens = self.cliente.intercambiar_codigo(code, verifier)
        access = tokens.get("access_token")
        if not access:
            raise ValidationError("Lichess no devolvió un token")

        try:
            perfil = self.cliente.cuenta(str(access))
        finally:
            self.cliente.revocar(str(access))

        lichess_id, visible = identidad_lichess(perfil)
        return self._guardar(usuario_id, lichess_id, visible)

    def vincular_por_username(self, usuario: Usuario, username: str) -> CuentaLichess:
        """Si el OAuth falla (modo infantil, app del móvil), se vincula con el usuario público."""
        self._exigir_puede_vincular(usuario.id)
        limpio = normalizar_usuario_lichess(username)
        if not limpio:
            raise ValidationError("Escribe el usuario de Lichess")
        perfil = self.cliente.perfil_publico(limpio)
        lichess_id, visible = identidad_lichess(perfil)
        return self._guardar(usuario.id, lichess_id, visible)

    def _guardar(self, usuario_id: int, lichess_id: str, visible: str) -> CuentaLichess:
        ocupada = self.cuentas.get_by_username(lichess_id)
        if ocupada is not None:
            raise ConflictError("Esa cuenta de Lichess ya está vinculada a otro usuario")
        try:
            cuenta = self.cuentas.create(
                CuentaLichess(
                    usuario_id=usuario_id,
                    username=lichess_id,
                    username_visible=visible,
                    vinculada_en=datetime.now(timezone.utc),
                )
            )
            self.auth._asegurar_ratings(usuario_id)
            self.db.commit()
            self.db.refresh(cuenta)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Esa cuenta de Lichess ya está vinculada a otro usuario") from exc
        return cuenta

    def desvincular(self, usuario: Usuario) -> None:
        cuenta = self.cuentas.get_by_usuario_id(usuario.id)
        if cuenta is None:
            raise ValidationError("No hay una cuenta de Lichess vinculada")
        self.cuentas.delete(cuenta)
        self.db.commit()

    def _exigir_puede_vincular(self, usuario_id: int) -> None:
        if self.cuentas.get_by_usuario_id(usuario_id) is not None:
            raise ConflictError("Esta cuenta ya está vinculada a Lichess")
        if self.chesscom.get_by_usuario_id(usuario_id) is not None:
            raise ConflictError(
                "Esta cuenta ya está vinculada a Chess.com. Un jugador usa una sola plataforma."
            )
