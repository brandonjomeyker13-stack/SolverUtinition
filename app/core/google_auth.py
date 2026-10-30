from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

_request = google_requests.Request()


def verificar_id_token_google(token: str) -> dict:
    """Verifica firma, expiración y audience del id_token de Google Identity Services."""
    if not settings.GOOGLE_CLIENT_ID:
        raise UnauthorizedError("Google Sign-In no está configurado en el servidor")
    try:
        return google_id_token.verify_oauth2_token(token, _request, settings.GOOGLE_CLIENT_ID)
    except ValueError as exc:
        raise UnauthorizedError("Token de Google inválido o expirado") from exc
