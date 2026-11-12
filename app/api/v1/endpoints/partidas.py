from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_usuario, require_cron_secret
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.partida_repository import PartidaRepository
from app.schemas.partida import PartidaOut, SincronizacionOut
from app.services.elo_real_service import EloRealService
from app.services.sincronizacion_lichess_service import SincronizacionLichessService
from app.services.sincronizacion_service import SincronizacionService

router = APIRouter(prefix="/partidas", tags=["partidas"])


def _correr(db: Session) -> SincronizacionOut:
    lichess = SincronizacionLichessService(db).sincronizar()
    chesscom = SincronizacionService(db).sincronizar()
    EloRealService(db).actualizar_todos()
    return SincronizacionOut(
        revisadas=lichess["revisadas"] + chesscom["revisadas"],
        aplicadas=lichess["aplicadas"] + chesscom["aplicadas"],
        omitidas=lichess["omitidas"] + chesscom["omitidas"],
    )


@router.get("/mias", response_model=list[PartidaOut])
def mias(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> list[PartidaOut]:
    return PartidaRepository(db).listar_de_usuario(usuario.id, limit=100)


@router.post("/sincronizar-ahora", response_model=SincronizacionOut)
def sincronizar_ahora(
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
) -> SincronizacionOut:
    total = {"revisadas": 0, "aplicadas": 0, "omitidas": 0}
    resultados = []
    if usuario.cuenta_lichess is not None:
        resultados.append(SincronizacionLichessService(db).sincronizar_usuario(usuario.id))
    if usuario.cuenta_chesscom is not None:
        resultados.append(SincronizacionService(db).sincronizar_usuario(usuario.id))
    for r in resultados:
        for k in total:
            total[k] += r[k]
    EloRealService(db).actualizar_usuario(usuario.id)
    return SincronizacionOut(**total)


@router.post("/sincronizar", response_model=SincronizacionOut)
def sincronizar_cron(
    _: None = Depends(require_cron_secret),
    db: Session = Depends(get_db),
) -> SincronizacionOut:
    return _correr(db)
