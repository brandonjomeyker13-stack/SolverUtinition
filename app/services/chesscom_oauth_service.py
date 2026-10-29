from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.clients.chesscom import ChesscomClient, generar_pkce, username_desde_tokens
from app.core.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.core.security import firmar_oauth_state, leer_oauth_state
from app.models.cuenta_chesscom import CuentaChesscom
from app.models.usuario import Usuario
from app.repositories.cuenta_chesscom_repository import CuentaChesscomRepository
from app.services.auth_service import AuthService


class ChesscomOAuthService:
    def __init__(self, db: Session, cliente: ChesscomClient | None = None):
        self.db = db
        self.cuentas = CuentaChesscomRepository(db)
        self.auth = AuthService(db)
        self.cliente = cliente or ChesscomClient()

    def url_de_conexion(self, usuario: Usuario) -> str:
        if not settings.chesscom_oauth_listo:
            raise ValidationError(
                "Falta CHESSCOM_CLIENT_ID o CHESSCOM_CLIENT_SECRET en el entorno"
            )
        if self.cuentas.get_by_usuario_id(usuario.id) is not None:
            raise ConflictError("Esta cuenta ya está vinculada a Chess.com")

        verifier, challenge = generar_pkce()
        state = firmar_oauth_state({"uid": usuario.id, "cv": verifier})
        return self.cliente.url_autorizacion(state, challenge)

    def completar(self, code: str, state: str) -> CuentaChesscom:
        claims = leer_oauth_state(state)
        usuario_id = int(claims["uid"])
        verifier = claims["cv"]

        if self.cuentas.get_by_usuario_id(usuario_id) is not None:
            raise ConflictError("Esta cuenta ya está vinculada a Chess.com")

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

    def desvincular(self, usuario: Usuario) -> None:
        cuenta = self.cuentas.get_by_usuario_id(usuario.id)
        if cuenta is None:
            raise ValidationError("No hay una cuenta de Chess.com vinculada")
        self.cuentas.delete(cuenta)
        self.db.commit()
