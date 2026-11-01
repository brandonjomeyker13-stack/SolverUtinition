from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central. Se carga una vez desde .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "SolverUnition API"
    API_V1_PREFIX: str = "/api/v1"

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    # El access vive en el navegador. 7 días para no pedir login al cerrar la pestaña.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    FRONTEND_URL: str = "https://solver-utinition-front.vercel.app"
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:3000,"
        "https://solucionador-de-uso-front.vercel.app,"
        "https://solucionador-utinicion-front-2ftujmjqc-orderscode.vercel.app,"
        "https://solucionador-utinición-front-2ftujmjqc-orderscode.vercel.app"
    )
    CORS_ORIGIN_REGEX: str | None = r"https://.*\.vercel\.app"

    ELO_INICIAL: int = 1000
    ELO_K: int = 20

    CHESSCOM_CLIENT_ID: str | None = None
    CHESSCOM_CLIENT_SECRET: str | None = None
    CHESSCOM_REDIRECT_URI: str = "http://localhost:8000/api/v1/chesscom/callback"
    CHESSCOM_USER_AGENT: str | None = None
    CHESSCOM_AUTH_URL: str = "https://oauth.chess.com/authorize"
    CHESSCOM_TOKEN_URL: str = "https://oauth.chess.com/token"
    CHESSCOM_PUBAPI_URL: str = "https://api.chess.com/pub"

    # OAuth público de Lichess: no hay alta de app ni client secret.
    # El client id es un texto único que eliges tú. Sin él, "Conectar Lichess" responde 422.
    LICHESS_CLIENT_ID: str | None = None
    LICHESS_REDIRECT_URI: str = "http://localhost:8000/api/v1/lichess/callback"
    LICHESS_USER_AGENT: str | None = None
    LICHESS_AUTH_URL: str = "https://lichess.org/oauth"
    LICHESS_TOKEN_URL: str = "https://lichess.org/api/token"
    LICHESS_API_URL: str = "https://lichess.org"

    CRON_SECRET: str | None = None

    # Client ID de Google Identity Services (el del front). Sin esto,
    # POST /auth/google rechaza todo.
    GOOGLE_CLIENT_ID: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        origenes = [origen.strip() for origen in self.CORS_ORIGINS.split(",") if origen.strip()]
        for extra in (
            "http://localhost:5173",
            "http://localhost:3000",
            "https://solucionador-de-uso-front.vercel.app",
            "https://solucionador-utinicion-front-2ftujmjqc-orderscode.vercel.app",
            "https://solucionador-utinición-front-2ftujmjqc-orderscode.vercel.app",
        ):
            if extra not in origenes:
                origenes.append(extra)
        return origenes

    @property
    def cors_origin_regex(self) -> str | None:
        raw = (self.CORS_ORIGIN_REGEX or "").strip()
        return raw or r"https://.*\.vercel\.app"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            return "postgresql://" + url[len("postgres://") :]
        return url

    @property
    def usa_pooler_transaccional(self) -> bool:
        """PgBouncer en modo transaction (Supabase :6543) no soporta el pool de SQLAlchemy."""
        return ":6543" in self.DATABASE_URL

    @property
    def chesscom_oauth_listo(self) -> bool:
        return bool(self.CHESSCOM_CLIENT_ID and self.CHESSCOM_CLIENT_SECRET)

    @property
    def lichess_oauth_listo(self) -> bool:
        return bool(self.lichess_client_id)

    @property
    def lichess_client_id(self) -> str:
        return (self.LICHESS_CLIENT_ID or "").strip()

    @property
    def lichess_redirect_uri(self) -> str:
        return (self.LICHESS_REDIRECT_URI or "").strip()

    @property
    def lichess_user_agent(self) -> str:
        bruto = self.LICHESS_USER_AGENT or self.CHESSCOM_USER_AGENT or "SolverUnition (community ranking)"
        # Render a veces guarda la variable con un salto de línea. Un header no lo admite.
        limpio = " ".join(bruto.split())
        return limpio or "SolverUnition (community ranking)"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
