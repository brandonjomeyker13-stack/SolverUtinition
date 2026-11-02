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
            "client_id": settings.lichess_client_id,
            "redirect_uri": settings.lichess_redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "scope": "preference:read",
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
                    "redirect_uri": settings.lichess_redirect_uri,
                    "client_id": settings.lichess_client_id,
                },
            )
        except httpx.HTTPError as exc:
            raise ValidationError("Lichess no respondió") from exc
        if respuesta.status_code >= 400:
            logger.warning(
                "Lichess rechazó el token (%s): %s",
                respuesta.status_code,
                _detalle_error(respuesta),
            )
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
            logger.warning(
                "Lichess no devolvió la cuenta (%s): %s",
                respuesta.status_code,
                _detalle_error(respuesta),
            )
            raise ValidationError("Lichess no devolvió la cuenta")
        return respuesta.json()

    def perfil_publico(self, username: str) -> dict[str, Any]:
        clave = quote(username.strip(), safe="")
        try:
            respuesta = self._http.get(f"{settings.LICHESS_API_URL}/api/user/{clave}")
        except httpx.HTTPError as exc:
            raise ValidationError("Lichess no respondió el perfil") from exc
        if respuesta.status_code == 404:
            raise ValidationError("No existe esa cuenta de Lichess")
        if respuesta.status_code >= 400:
            raise ValidationError("Lichess no respondió el perfil")
        perfil = respuesta.json()
        if perfil.get("disabled") or perfil.get("closed"):
            raise ValidationError("Esa cuenta de Lichess está cerrada")
        return perfil

    def revocar(self, access_token: str) -> None:
        try:
            self._http.delete(
                f"{settings.LICHESS_API_URL}/api/token",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError:
            logger.warning("No se pudo revocar el token de Lichess")

    def partidas(self, username: str, since_ms: int, limite: int = 50) -> list[dict[str, Any]]:
        """Las partidas más recientes desde `since_ms`. Una sola petición."""
        return self._ndjson(
            username,
            {
                "since": since_ms,
                "max": max(1, min(limite, 50)),
                "perfType": "bullet,blitz,rapid",
                "moves": "false",
                "pgnInJson": "false",
                "clocks": "false",
                "evals": "false",
                "opening": "false",
            },
        )

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


def _detalle_error(respuesta: httpx.Response) -> str:
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return (respuesta.text or "")[:200]
    if not isinstance(cuerpo, dict):
        return ""
    return str(cuerpo.get("error") or cuerpo.get("error_description") or "")[:200]
