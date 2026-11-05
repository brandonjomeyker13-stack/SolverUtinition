from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import Plataforma, Ritmo
from app.schemas.ranking import RankingFilaOut, RankingMensualOut
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("", response_model=list[RankingFilaOut])
def listar(
    ritmo: Ritmo = Query(default=Ritmo.RAPID),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[RankingFilaOut]:
    return RankingService(db).listar(ritmo, limit)


@router.get("/mes", response_model=RankingMensualOut)
def listar_mes(
    ritmo: Ritmo = Query(default=Ritmo.RAPID),
    mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    plataforma: Plataforma | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> RankingMensualOut:
    return RankingService(db).listar_mensual(ritmo, mes, plataforma, limit)
