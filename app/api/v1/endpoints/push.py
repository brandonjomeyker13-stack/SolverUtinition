from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.core.exceptions import ValidationError
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.analisis import ClavePushOut, SuscripcionPushBorrar, SuscripcionPushIn
from app.services.push_service import PushService

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/clave", response_model=ClavePushOut)
def clave_publica() -> ClavePushOut:
    return ClavePushOut(clave=settings.VAPID_PUBLIC_KEY if settings.push_listo else None)


@router.post("/suscripcion", status_code=status.HTTP_204_NO_CONTENT)
def suscribir(
    datos: SuscripcionPushIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> None:
    PushService(db).suscribir(usuario.id, datos.endpoint, datos.p256dh, datos.auth)


@router.post("/suscripcion/borrar", status_code=status.HTTP_204_NO_CONTENT)
def borrar(
    datos: SuscripcionPushBorrar,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> None:
    PushService(db).borrar(usuario.id, datos.endpoint)


@router.post("/prueba", status_code=status.HTTP_204_NO_CONTENT)
def prueba(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> None:
    enviadas = PushService(db).enviar(
        usuario.id,
        "Notificaciones activas",
        "Así te llegará el resumen de tus partidas cada lunes.",
        "/resumen",
    )
    if enviadas == 0:
        raise ValidationError("No hay ningún dispositivo con notificaciones activas")
