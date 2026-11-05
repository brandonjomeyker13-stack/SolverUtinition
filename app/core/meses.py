from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import ValidationError


def zona_ranking() -> timezone:
    return timezone(timedelta(hours=settings.RANKING_UTC_OFFSET_HORAS))


def rango_mes(mes: str | None, ahora: datetime | None = None) -> tuple[str, datetime, datetime]:
    """("2026-11", inicio, inicio del mes siguiente). Sin `mes`, el mes en curso."""
    zona = zona_ranking()
    if mes is None:
        local = (ahora or datetime.now(timezone.utc)).astimezone(zona)
        anio, numero = local.year, local.month
    else:
        try:
            anio_txt, numero_txt = mes.split("-")
            anio, numero = int(anio_txt), int(numero_txt)
        except ValueError as exc:
            raise ValidationError("El mes va como AAAA-MM") from exc
        if not 1 <= numero <= 12 or not 2000 <= anio <= 2100:
            raise ValidationError("El mes va como AAAA-MM")

    desde = datetime(anio, numero, 1, tzinfo=zona)
    siguiente = datetime(anio + numero // 12, numero % 12 + 1, 1, tzinfo=zona)
    return f"{anio:04d}-{numero:02d}", desde, siguiente
