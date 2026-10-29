import hashlib
import secrets
from base64 import urlsafe_b64encode
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import jwt as jose_jwt

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.enums import ResultadoPartida, Ritmo

RESULTADOS_TABLAS = frozenset(
    {
        "stalemate",
        "agreed",
        "repetition",
        "insufficient",
        "50move",
        "timevsinsufficient",
    }
)


def generar_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def resultado_desde_api(white_result: str, black_result: str) -> ResultadoPartida | None:
    if white_result == "win":
        return ResultadoPartida.BLANCA
    if black_result == "win":
        return ResultadoPartida.NEGRA
    if white_result in RESULTADOS_TABLAS or black_result in RESULTADOS_TABLAS:
        return ResultadoPartida.TABLAS
    return None


def score_blanca(resultado: ResultadoPartida) -> float:
    if resultado == ResultadoPartida.BLANCA:
        return 1.0
    if resultado == ResultadoPartida.NEGRA:
        return 0.0
    return 0.5


def ritmo_desde_api(time_class: str) -> Ritmo | None:
    try:
        return Ritmo(time_class)
    except ValueError:
        return None


class ChesscomClient:
    def __init__(self, timeout: float = 20.0):
        headers = {"Accept": "application/json"}
        if settings.CHESSCOM_USER_AGENT:
            headers["User-Agent"] = settings.CHESSCOM_USER_AGENT
        self._http = httpx.Client(timeout=timeout, headers=headers)

    def url_autorizacion(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": settings.CHESSCOM_CLIENT_ID,
            "redirect_uri": settings.CHESSCOM_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{settings.CHESSCOM_AUTH_URL}?{urlencode(params)}"

    def intercambiar_codigo(self, code: str, code_verifier: str) -> dict[str, Any]:
        respuesta = self._http.post(
            settings.CHESSCOM_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.CHESSCOM_REDIRECT_URI,
                "client_id": settings.CHESSCOM_CLIENT_ID,
                "client_secret": settings.CHESSCOM_CLIENT_SECRET,
                "code_verifier": code_verifier,
            },
        )
        if respuesta.status_code >= 400:
            raise ValidationError("Chess.com rechazó el intercambio de código")
        return respuesta.json()

    def perfil(self, username: str) -> dict[str, Any]:
        url = f"{settings.CHESSCOM_PUBAPI_URL}/player/{username}"
        respuesta = self._http.get(url)
        if respuesta.status_code == 404:
            raise ValidationError("No existe esa cuenta de Chess.com")
        if respuesta.status_code >= 400:
            raise ValidationError("Chess.com no respondió el perfil")
        return respuesta.json()

    def partidas_mes(self, username: str, year: int, month: int) -> list[dict[str, Any]]:
        url = f"{settings.CHESSCOM_PUBAPI_URL}/player/{username}/games/{year}/{month:02d}"
        respuesta = self._http.get(url)
        if respuesta.status_code == 404:
            return []
        if respuesta.status_code >= 400:
            raise ValidationError(f"No se pudieron leer las partidas de {username}")
        return list(respuesta.json().get("games") or [])

    def close(self) -> None:
        self._http.close()


def username_desde_tokens(tokens: dict[str, Any], cliente: ChesscomClient) -> tuple[str, str | None]:
    """Chess.com no tiene UserInfo: el username viaja en el id_token."""
    id_token = tokens.get("id_token")
    if not id_token:
        raise ValidationError("Chess.com no devolvió id_token")

    claims = jose_jwt.get_unverified_claims(id_token)
    username = claims.get("username") or claims.get("preferred_username")
    uuid = claims.get("uuid") or claims.get("sub")
    if not username:
        raise ValidationError("Chess.com no envió el username en el id_token")

    perfil = cliente.perfil(username)
    visible = perfil.get("username") or username
    uuid = perfil.get("player_id") or perfil.get("uuid") or uuid
    return str(visible), str(uuid) if uuid is not None else None


def instante_fin(game: dict[str, Any]) -> datetime | None:
    raw = game.get("end_time")
    if raw is None:
        return None
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)
