from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_usuario, require_cron_secret
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.partida_repository import PartidaRepository
from app.schemas.partida import PartidaOut, SincronizacionOut
from app.services.sincronizacion_service import SincronizacionService

router = APIRouter(prefix="/partidas", tags=["partidas"])


@router.get("/mias", response_model=list[PartidaOut])
def mias(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    return PartidaRepository(db).listar_de_usuario(usuario.id)


@router.post("/sincronizar", response_model=SincronizacionOut)
def sincronizar_cron(
    _: None = Depends(require_cron_secret),
    db: Session = Depends(get_db),
):
    return SincronizacionService(db).sincronizar()


@router.post("/sincronizar-ahora", response_model=SincronizacionOut)
def sincronizar_ahora(
    _usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    return SincronizacionService(db).sincronizar()
