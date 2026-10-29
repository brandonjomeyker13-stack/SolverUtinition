from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        self.db.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.execute(stmt).scalar_one_or_none()

    def revocar(self, token_hash: str) -> bool:
        token = self.get_by_hash(token_hash)
        if token is None:
            return False
        token.revoked = True
        self.db.flush()
        return True

    def es_valido(self, token: RefreshToken) -> bool:
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return not token.revoked and expires_at > datetime.now(timezone.utc)

    def eliminar_vencidos(self, dias_gracia: int = 30) -> int:
        limite = datetime.now(timezone.utc) - timedelta(days=dias_gracia)
        stmt = (
            delete(RefreshToken)
            .where(
                or_(RefreshToken.expires_at < limite, RefreshToken.revoked.is_(True)),
                RefreshToken.updated_at < limite,
            )
            .execution_options(synchronize_session=False)
        )
        return self.db.execute(stmt).rowcount
