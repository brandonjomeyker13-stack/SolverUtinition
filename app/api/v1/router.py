from fastapi import APIRouter

from app.api.v1.endpoints import auth, chesscom, partidas, ranking

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chesscom.router)
api_router.include_router(partidas.router)
api_router.include_router(ranking.router)
