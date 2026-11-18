import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.analisis import SuscripcionPush

logger = logging.getLogger(__name__)


class PushService:
    def __init__(self, db: Session):
        self.db = db

    def suscribir(self, usuario_id: int, endpoint: str, p256dh: str, auth: str) -> None:
        fila = self.db.scalar(select(SuscripcionPush).where(SuscripcionPush.endpoint == endpoint))
        if fila is None:
            fila = SuscripcionPush(endpoint=endpoint)
            self.db.add(fila)
        fila.usuario_id = usuario_id
        fila.p256dh = p256dh
        fila.auth = auth
        self.db.commit()

    def borrar(self, usuario_id: int, endpoint: str) -> None:
        self.db.execute(
            delete(SuscripcionPush).where(
                SuscripcionPush.usuario_id == usuario_id, SuscripcionPush.endpoint == endpoint
            )
        )
        self.db.commit()

    def tiene(self, usuario_id: int) -> bool:
        return self.db.scalar(
            select(SuscripcionPush.id).where(SuscripcionPush.usuario_id == usuario_id).limit(1)
        ) is not None

    def enviar(self, usuario_id: int, titulo: str, cuerpo: str, url: str = "/") -> int:
        """Devuelve a cuántos dispositivos llegó. Las suscripciones vencidas se borran."""
        if not settings.push_listo:
            raise ValidationError("Las notificaciones no están configuradas en el servidor")
        datos = json.dumps({"title": titulo, "body": cuerpo[:240], "url": url})
        enviadas = 0
        for fila in self.db.scalars(
            select(SuscripcionPush).where(SuscripcionPush.usuario_id == usuario_id)
        ).all():
            try:
                webpush(
                    subscription_info={"endpoint": fila.endpoint, "keys": {"p256dh": fila.p256dh, "auth": fila.auth}},
                    data=datos,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.vapid_contacto},
                    ttl=60 * 60 * 24 * 3,
                )
                enviadas += 1
            except WebPushException as exc:
                estado = exc.response.status_code if exc.response is not None else None
                if estado in (404, 410):
                    self.db.delete(fila)
                else:
                    logger.warning("No se pudo enviar una notificación (%s)", estado)
        self.db.commit()
        return enviadas
