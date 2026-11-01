# SolverUnition API

Backend de la comunidad de ajedrez: cuenta propia y ranking interno por ritmo
(bullet, blitz, rapid). Cada jugador vincula **una** plataforma, Lichess o
Chess.com. Hoy la web conecta Lichess; Chess.com sigue en la API, oculto en
el front, hasta que aprueben su OAuth. Solo cuentan las partidas de **después**
de que ambos jugadores ya estén vinculados.

## Puesta en marcha

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
```

Rellena `.env` (qué va en cada variable está comentado ahí).
Para "Iniciar con Google" solo hace falta `GOOGLE_CLIENT_ID` (el mismo del front).
Para "Conectar Lichess" hace falta `LICHESS_CLIENT_ID`: se crea en un minuto en
https://lichess.org/account/oauth/app/create (no hay que esperar aprobación).
El redirect tiene que ser exactamente `LICHESS_REDIRECT_URI`.

Luego:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Docs en http://localhost:8000/docs (solo si `ENVIRONMENT=development`).

## Tests

```bash
pytest
```

Corren contra SQLite en memoria. No tocan Supabase.

## Capas

```
app/
  api/v1/endpoints/   HTTP: validar, delegar, devolver
  services/           Reglas de negocio
  repositories/       Acceso a datos
  models/             Tablas
  schemas/            Contratos Pydantic
  clients/            Chess.com y Lichess
  core/               Config, CORS, JWT, elo
```

## Deploy

- **Render**: servicio web con `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  Health check: `/health`. Release: `alembic upgrade head`.
- **Cron** (cada 10 min): `POST /api/v1/partidas/sincronizar` con header
  `X-Cron-Secret` igual a `CRON_SECRET`.
- **Vercel** (front, después): agrega su origen en `CORS_ORIGINS`.
