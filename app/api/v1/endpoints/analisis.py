from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_usuario
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.analisis import ResumenSemanal
from app.models.enums import Plataforma
from app.models.usuario import Usuario
from app.schemas.analisis import AnalisisIn, AnalisisOut, PartidaGeneralOut, ResumenOut
from app.services.analisis_service import AnalisisService
from app.services.partidas_generales_service import PartidasGeneralesService

router = APIRouter(prefix="/analisis", tags=["analisis"])


@router.get("/partidas", response_model=list[PartidaGeneralOut])
def partidas_generales(
    plataforma: Plataforma = Query(...),
    limit: int = Query(default=30, ge=1, le=60),
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> list[PartidaGeneralOut]:
    partidas = PartidasGeneralesService(db).listar(usuario, plataforma, limit)
    precisiones = AnalisisService(db).precisiones(usuario.id, plataforma, (p.id for p in partidas))
    salida: list[PartidaGeneralOut] = []
    for p in partidas:
        fila = PartidaGeneralOut.model_validate(p, from_attributes=True)
        fila.analizada = p.id in precisiones
        fila.precision = precisiones.get(p.id)
        salida.append(fila)
    return salida


@router.get("/resumen", response_model=ResumenOut | None)
def ultimo_resumen(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> ResumenSemanal | None:
    return db.scalar(
        select(ResumenSemanal)
        .where(ResumenSemanal.usuario_id == usuario.id)
        .order_by(ResumenSemanal.semana.desc())
        .limit(1)
    )


@router.get("/{plataforma}/{partida_id}", response_model=AnalisisOut)
def obtener(
    plataforma: Plataforma,
    partida_id: str,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    fila = AnalisisService(db).obtener(usuario.id, plataforma, partida_id)
    if fila is None:
        raise NotFoundError("Esa partida todavía no tiene análisis")
    return fila


@router.post("", response_model=AnalisisOut, status_code=status.HTTP_201_CREATED)
def guardar(
    datos: AnalisisIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    return AnalisisService(db).guardar_del_navegador(usuario, datos)
