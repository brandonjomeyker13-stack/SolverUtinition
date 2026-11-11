import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.chesscom import ChesscomClient, generar_pkce, username_desde_tokens
from app.core.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.security import firmar_oauth_state, leer_oauth_state
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.usuario import Usuario
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.repositories.cuenta_lichess_repository import CuentaLichessRepository
from app.services.auth_service import AuthService

MINUTOS_VERIFICACION = 60
_PROPOSITO_UBICACION = "chesscom-ubicacion"
# Sin 0/O ni 1/I/L: el código se copia a mano en el móvil.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_USERNAME_CHESSCOM = re.compile(r"[A-Za-z0-9_-]{3,25}")


@dataclass(frozen=True)
class VerificacionChesscom:
    username_visible: str
    codigo: str
    token: str
    expira_en: datetime


def normalizar_usuario_chesscom(raw: str) -> str:
    texto = raw.strip()
    for prefijo in (
        "https://www.chess.com/member/",
        "https://chess.com/member/",
        "http://www.chess.com/member/",
        "www.chess.com/member/",
        "chess.com/member/",
    ):
        if texto.lower().startswith(prefijo):
            texto = texto[len(prefijo) :]
            break
    return texto.strip("/").lstrip("@").strip()


def _identidad(perfil: dict[str, Any], respaldo: str) -> tuple[str, str, str | None]:
    estado = str(perfil.get("status") or "")
    if estado.startswith("closed"):
        raise ValidationError("Esa cuenta de Chess.com está cerrada")
    clave = str(perfil.get("username") or respaldo).strip().lower()
    # `username` llega en minúsculas; la URL del perfil conserva las mayúsculas.
    de_url = str(perfil.get("url") or "").rstrip("/").rsplit("/", 1)[-1]
    visible = de_url if de_url.lower() == clave else clave
    uuid = perfil.get("player_id") or perfil.get("uuid")
    return visible, clave, str(uuid) if uuid else None


class ChesscomOAuthService:
    def __init__(self, db: Session, cliente: ChesscomClient | None = None):
        self.db = db
        self.cuentas = CuentaChesscomRepository(db)
        self.lichess = CuentaLichessRepository(db)
        self.auth = AuthService(db)
        self.cliente = cliente or ChesscomClient()

    def url_de_conexion(self, usuario: Usuario) -> str:
        if not settings.chesscom_oauth_listo:
            raise ValidationError(
                "Falta CHESSCOM_CLIENT_ID o CHESSCOM_CLIENT_SECRET en el entorno"
            )
        self._exigir_puede_vincular(usuario.id)

        verifier, challenge = generar_pkce()
        state = firmar_oauth_state({"uid": usuario.id, "cv": verifier})
        return self.cliente.url_autorizacion(state, challenge)

    def completar(self, code: str, state: str) -> CuentaChesscom:
        claims = leer_oauth_state(state)
        usuario_id = int(claims["uid"])
        verifier = claims["cv"]

        self._exigir_puede_vincular(usuario_id)

        tokens = self.cliente.intercambiar_codigo(code, verifier)
        username_visible, uuid = username_desde_tokens(tokens, self.cliente)
        username = username_visible.lower()

        ocupada = self.cuentas.get_by_username(username)
        if ocupada is not None:
            raise ConflictError("Esa cuenta de Chess.com ya está vinculada a otro usuario")

        cuenta = self.cuentas.create(
            CuentaChesscom(
                usuario_id=usuario_id,
                username=username,
                username_visible=username_visible,
                chesscom_uuid=str(uuid) if uuid is not None else None,
                vinculada_en=datetime.now(timezone.utc),
            )
        )
        self.auth._asegurar_ratings(usuario_id)
        self.db.commit()
        self.db.refresh(cuenta)
        return cuenta

    def iniciar_verificacion(self, usuario: Usuario, username: str) -> VerificacionChesscom:
        """Mientras Chess.com no aprueba el OAuth: el jugador prueba que es suyo
        poniendo un código en la ubicación de su perfil público."""
        self._exigir_puede_vincular(usuario.id)
        limpio = normalizar_usuario_chesscom(username)
        if not _USERNAME_CHESSCOM.fullmatch(limpio):
            raise ValidationError("Escribe tu usuario de Chess.com tal como aparece en tu perfil")

        visible, clave, uuid = _identidad(self.cliente.perfil(limpio), limpio)
        self._exigir_libre(clave, uuid)

        codigo = "SU-" + "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(6))
        token = firmar_oauth_state(
            {"p": _PROPOSITO_UBICACION, "uid": usuario.id, "u": clave, "pid": uuid, "c": codigo},
            minutos=MINUTOS_VERIFICACION,
        )
        return VerificacionChesscom(
            username_visible=visible,
            codigo=codigo,
            token=token,
            expira_en=datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_VERIFICACION),
        )

    def confirmar_verificacion(self, usuario: Usuario, token: str) -> CuentaChesscom:
        try:
            claims = leer_oauth_state(token)
        except ExpiredSignatureError as exc:
            raise ValidationError("El código venció. Pide uno nuevo.") from exc
        except JWTError as exc:
            raise ValidationError("La verificación no es válida. Pide un código nuevo.") from exc
        if claims.get("p") != _PROPOSITO_UBICACION or claims.get("uid") != usuario.id:
            raise ValidationError("La verificación no es válida. Pide un código nuevo.")

        self._exigir_puede_vincular(usuario.id)
        username = str(claims.get("u") or "")
        codigo = str(claims.get("c") or "")
        perfil = self.cliente.perfil(username, fresco=True)
        visible, clave, uuid = _identidad(perfil, username)

        esperado = claims.get("pid")
        if esperado and uuid and str(esperado) != uuid:
            raise ValidationError("Esa cuenta de Chess.com cambió. Pide un código nuevo.")

        ubicacion = str(perfil.get("location") or "")
        if not codigo or codigo.upper() not in ubicacion.upper():
            raise ValidationError(
                f"Todavía no vemos {codigo} en la ubicación de tu perfil de Chess.com. "
                "Revisa que lo guardaste. Chess.com puede tardar un par de minutos en mostrarlo."
            )

        self._exigir_libre(clave, uuid)
        try:
            cuenta = self.cuentas.create(
                CuentaChesscom(
                    usuario_id=usuario.id,
                    username=clave,
                    username_visible=visible,
                    chesscom_uuid=uuid,
                    vinculada_en=datetime.now(timezone.utc),
                )
            )
            self.auth._asegurar_ratings(usuario.id)
            self.db.commit()
            self.db.refresh(cuenta)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Esa cuenta de Chess.com ya está vinculada a otro usuario") from exc
        return cuenta

    def _exigir_libre(self, clave: str, uuid: str | None) -> None:
        if self.cuentas.get_by_username(clave) is not None or (
            uuid and self.cuentas.get_by_uuid(uuid) is not None
        ):
            raise ConflictError("Esa cuenta de Chess.com ya está vinculada a otro usuario")

    def _exigir_puede_vincular(self, usuario_id: int) -> None:
        if self.cuentas.get_by_usuario_id(usuario_id) is not None:
            raise ConflictError("Esta cuenta ya está vinculada a Chess.com")
        if self.lichess.get_by_usuario_id(usuario_id) is not None:
            raise ConflictError(
                "Esta cuenta ya está vinculada a Lichess. Un jugador usa una sola plataforma."
            )

    def desvincular(self, usuario: Usuario) -> None:
        cuenta = self.cuentas.get_by_usuario_id(usuario.id)
        if cuenta is None:
            raise ValidationError("No hay una cuenta de Chess.com vinculada")
        self.cuentas.delete(cuenta)
        self.db.commit()
