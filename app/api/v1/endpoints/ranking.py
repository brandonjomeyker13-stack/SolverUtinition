from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import Ritmo
from app.schemas.ranking import RankingFilaOut
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("", response_model=list[RankingFilaOut])
def listar(
    ritmo: Ritmo = Query(default=Ritmo.RAPID),
    db: Session = Depends(get_db),
):
    return RankingService(db).listar(ritmo)
