import json
import logging
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class LichessClient:
    """OAuth para saber quién es el jugador, y la API pública para sus partidas.

    El token solo se usa para leer /api/account y después se revoca: las
    partidas que nos importan son públicas y no hace falta guardarlo.
    """

    def __init__(self, timeout: float = 30.0):
        self._http = httpx.Client(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": settings.lichess_user_agent,
            },
        )

    def url_autorizacion(self, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.LICHESS_CLIENT_ID,
            "redirect_uri": settings.LICHESS_REDIRECT_URI,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
        }
        return f"{settings.LICHESS_AUTH_URL}?{urlencode(params)}"

    def intercambiar_codigo(self, code: str, code_verifier: str) -> dict[str, Any]:
        try:
            respuesta = self._http.post(
                settings.LICHESS_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": settings.LICHESS_REDIRECT_URI,
                    "client_id": settings.LICHESS_CLIENT_ID,
                },
            )
        except httpx.HTTPError as exc:
            raise ValidationError("Lichess no respondió") from exc
        if respuesta.status_code >= 400:
            raise ValidationError("Lichess rechazó el inicio de sesión")
        return respuesta.json()

    def cuenta(self, access_token: str) -> dict[str, Any]:
        try:
            respuesta = self._http.get(
                f"{settings.LICHESS_API_URL}/api/account",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise ValidationError("Lichess no respondió la cuenta") from exc
        if respuesta.status_code >= 400:
            raise ValidationError("Lichess no devolvió la cuenta")
        return respuesta.json()

    def revocar(self, access_token: str) -> None:
        try:
            self._http.delete(
                f"{settings.LICHESS_API_URL}/api/token",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError:
            logger.warning("No se pudo revocar el token de Lichess")

    def partidas(self, username: str, since_ms: int) -> list[dict[str, Any]]:
        """Partidas terminadas desde `since_ms`, de más nuevas a más viejas."""
        vistos: set[str] = set()
        juegos: list[dict[str, Any]] = []
        until: int | None = None
        for _ in range(5):
            params: dict[str, Any] = {
                "since": since_ms,
                "max": 200,
                "perfType": "bullet,blitz,rapid",
                "moves": "false",
                "pgnInJson": "false",
                "clocks": "false",
                "evals": "false",
                "opening": "false",
            }
            if until is not None:
                params["until"] = until
            lote = self._ndjson(username, params)
            if not lote:
                break
            nuevos = 0
            oldest: int | None = None
            for game in lote:
                gid = str(game.get("id") or "")
                if gid and gid not in vistos:
                    vistos.add(gid)
                    juegos.append(game)
                    nuevos += 1
                marca = game.get("lastMoveAt")
                if isinstance(marca, int) and (oldest is None or marca < oldest):
                    oldest = marca
            if nuevos == 0 or len(lote) < 200 or oldest is None:
                break
            siguiente = oldest - 1
            if until is not None and siguiente >= until:
                break
            until = siguiente
        return juegos

    def _ndjson(self, username: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{settings.LICHESS_API_URL}/api/games/user/{quote(username, safe='')}"
        try:
            respuesta = self._http.get(
                url,
                params=params,
                headers={"Accept": "application/x-ndjson"},
            )
        except httpx.HTTPError as exc:
            raise ValidationError("Lichess no respondió las partidas") from exc
        if respuesta.status_code == 404:
            return []
        if respuesta.status_code >= 400:
            raise ValidationError("No se pudieron leer las partidas de Lichess")
        juegos: list[dict[str, Any]] = []
        for linea in respuesta.text.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                juegos.append(json.loads(linea))
            except json.JSONDecodeError as exc:
                raise ValidationError("Lichess devolvió una partida ilegible") from exc
        return juegos

    def close(self) -> None:
        self._http.close()
