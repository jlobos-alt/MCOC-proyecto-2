"""Cliente y loader meteorologico para el sitio del caso (Open-Meteo).

No usa pandas ni requests: solo `urllib` y `json`, para que el repo siga
funcionando con la instalacion base. El cliente devuelve un `MeteoFrame`
normalizado y guarda el JSON crudo, de modo que cada corrida sea trazable.

Fuentes:
- forecast: https://api.open-meteo.com/v1/forecast  (hasta 16 dias)
- archive:  https://archive-api.open-meteo.com/v1/archive (reanalysis ERA5)

Forecast, reanalysis y observacion NO son lo mismo:
- forecast: prediccion emitida en un instante, cambia con cada corrida;
- reanalysis: serie historica consistente, pero no es lo que se sabia ese dia;
- observacion: medida en terreno, la unica que valida el modelo.

Por eso cada descarga se guarda como snapshot inmutable con su fecha de
emision y su hash: un forecast viejo no se pisa nunca.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

VARIABLES = {
    "temperature_2m": ("temperature_C", "degC"),
    "relative_humidity_2m": ("humidity_pct", "%"),
    "wind_speed_10m": ("wind_ms", "m/s"),
    "shortwave_radiation": ("solar_W_m2", "W/m2"),
    "cloud_cover": ("cloud_pct", "%"),
    "precipitation": ("precip_mm", "mm"),
}


@dataclass(frozen=True)
class Site:
    name: str
    latitude: float
    longitude: float
    timezone: str = "America/Santiago"


SITIO_PAHUIL = Site(
    name="Pahuil / Chanco, Maule",
    latitude=-35.644721,
    longitude=-72.568332,
    timezone="America/Santiago",
)


@dataclass
class MeteoFrame:
    """Serie horaria normalizada, con su procedencia."""

    source: str
    issued_at: str
    fetched_at: str
    latitude: float
    longitude: float
    timezone: str
    model: str
    times: list[str]
    temperature_C: list[float]
    humidity_pct: list[float]
    wind_ms: list[float]
    solar_W_m2: list[float]
    cloud_pct: list[float]
    precip_mm: list[float]
    units: dict[str, str] = field(default_factory=dict)
    endpoint: str = ""
    raw: bytes = b""
    notes: str = ""

    def __len__(self) -> int:
        return len(self.times)

    def rows(self) -> list[dict[str, object]]:
        filas = []
        for i, t in enumerate(self.times):
            filas.append(
                {
                    "time": t,
                    "temperature_2m": self.temperature_C[i],
                    "relative_humidity_2m": self.humidity_pct[i],
                    "wind_speed_10m": self.wind_ms[i],
                    "shortwave_radiation": self.solar_W_m2[i],
                    "cloud_cover": self.cloud_pct[i],
                    "precipitation": self.precip_mm[i],
                }
            )
        return filas


def _finito(valor) -> float:
    if valor is None:
        return float("nan")
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float("nan")


def normalize_payload(
    payload: dict,
    source: str,
    issued_at: str | None = None,
    endpoint: str = "",
    model: str = "best_match",
    raw: bytes = b"",
    notes: str = "",
) -> MeteoFrame:
    """Convierte el JSON de Open-Meteo en un `MeteoFrame`."""
    hourly = payload.get("hourly") or {}
    times = [str(t) for t in hourly.get("time", [])]
    if not times:
        raise ValueError("La respuesta no trae serie horaria ('hourly').")

    columnas: dict[str, list[float]] = {}
    for var, (campo, _) in VARIABLES.items():
        valores = hourly.get(var)
        columnas[campo] = [_finito(v) for v in valores] if valores else [float("nan")] * len(times)

    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return MeteoFrame(
        source=source,
        issued_at=issued_at or ahora,
        fetched_at=ahora,
        latitude=float(payload.get("latitude", float("nan"))),
        longitude=float(payload.get("longitude", float("nan"))),
        timezone=str(payload.get("timezone", "America/Santiago")),
        model=model,
        times=times,
        temperature_C=columnas["temperature_C"],
        humidity_pct=columnas["humidity_pct"],
        wind_ms=columnas["wind_ms"],
        solar_W_m2=columnas["solar_W_m2"],
        cloud_pct=columnas["cloud_pct"],
        precip_mm=columnas["precip_mm"],
        units={campo: unidad for _, (campo, unidad) in VARIABLES.items()},
        endpoint=endpoint,
        raw=raw,
        notes=notes,
    )


class OpenMeteoClient:
    """Cliente minimo para forecast y reanalysis de Open-Meteo."""

    FORECAST = "https://api.open-meteo.com/v1/forecast"
    ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, timeout_s: float = 40.0, user_agent: str = "mcplan-e10/1.0"):
        self.timeout_s = timeout_s
        self.user_agent = user_agent

    def _get(self, url: str, params: dict[str, object]) -> tuple[dict, bytes]:
        consulta = url + "?" + urllib.parse.urlencode(params, doseq=True)
        pedido = urllib.request.Request(consulta, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(pedido, timeout=self.timeout_s) as respuesta:
            crudo = respuesta.read()
        return json.loads(crudo.decode("utf-8")), crudo

    def forecast(
        self,
        site: Site = SITIO_PAHUIL,
        days: int = 14,
        model: str = "best_match",
    ) -> MeteoFrame:
        params = {
            "latitude": site.latitude,
            "longitude": site.longitude,
            "hourly": ",".join(VARIABLES),
            "forecast_days": int(days),
            "timezone": site.timezone,
            "wind_speed_unit": "ms",
            "models": model,
        }
        payload, crudo = self._get(self.FORECAST, params)
        return normalize_payload(
            payload,
            source="open-meteo-forecast",
            endpoint=self.FORECAST,
            model=model,
            raw=crudo,
        )

    def archive(
        self,
        site: Site,
        start_date: str,
        end_date: str,
        model: str = "best_match",
    ) -> MeteoFrame:
        params = {
            "latitude": site.latitude,
            "longitude": site.longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(VARIABLES),
            "timezone": site.timezone,
            "wind_speed_unit": "ms",
            "models": model,
        }
        payload, crudo = self._get(self.ARCHIVE, params)
        return normalize_payload(
            payload,
            source="open-meteo-archive",
            endpoint=self.ARCHIVE,
            model=model,
            raw=crudo,
            notes="Reanalysis historico: se usa como climatologia de relleno.",
        )


# ---------------------------------------------------------------------------
# Ensamblado forecast + climatologia
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherPoint:
    t_h: float
    time_local: str
    temperature_C: float
    wind_ms: float
    solar_W_m2: float
    cloud_pct: float
    humidity_pct: float
    precip_mm: float
    source: str


@dataclass
class WeatherTimeline:
    """Clima del sitio en el eje t=0 de la simulacion (h)."""

    start_local: str
    points: list[WeatherPoint]

    def __len__(self) -> int:
        return len(self.points)

    @property
    def sources(self) -> dict[str, int]:
        cuenta: dict[str, int] = {}
        for p in self.points:
            cuenta[p.source] = cuenta.get(p.source, 0) + 1
        return cuenta

    def at(self, t_h: float) -> WeatherPoint:
        if not self.points:
            raise ValueError("Timeline vacio.")
        if t_h <= self.points[0].t_h:
            return self.points[0]
        if t_h >= self.points[-1].t_h:
            return self.points[-1]
        from bisect import bisect_right

        idx = bisect_right([p.t_h for p in self.points], t_h)
        a = self.points[idx - 1]
        b = self.points[idx]
        w = 0.0 if b.t_h == a.t_h else (t_h - a.t_h) / (b.t_h - a.t_h)
        return WeatherPoint(
            t_h=t_h,
            time_local=a.time_local,
            temperature_C=a.temperature_C + w * (b.temperature_C - a.temperature_C),
            wind_ms=a.wind_ms + w * (b.wind_ms - a.wind_ms),
            solar_W_m2=a.solar_W_m2 + w * (b.solar_W_m2 - a.solar_W_m2),
            cloud_pct=a.cloud_pct + w * (b.cloud_pct - a.cloud_pct),
            humidity_pct=a.humidity_pct + w * (b.humidity_pct - a.humidity_pct),
            precip_mm=a.precip_mm + w * (b.precip_mm - a.precip_mm),
            source=a.source if a.source == b.source else f"{a.source}+{b.source}",
        )


def _parse_local(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=None)


def _shift_year(dt: datetime, year: int) -> datetime:
    try:
        return dt.replace(year=year)
    except ValueError:  # 29 de febrero
        return dt.replace(year=year, day=28)


def _muestras(frame: MeteoFrame) -> list[tuple[datetime, list[float]]]:
    salida = []
    for i, t in enumerate(frame.times):
        valores = [
            frame.temperature_C[i],
            frame.wind_ms[i],
            frame.solar_W_m2[i],
            frame.cloud_pct[i],
            frame.humidity_pct[i],
            frame.precip_mm[i],
        ]
        salida.append((_parse_local(t), valores))
    return salida


def _interp(muestras: list[tuple[datetime, list[float]]], objetivo: datetime) -> tuple[list[float], bool]:
    """Interpola linealmente; devuelve (valores, dentro_del_rango)."""
    if not muestras:
        return [float("nan")] * 6, False
    tiempos = [m[0] for m in muestras]
    if objetivo < tiempos[0] or objetivo > tiempos[-1]:
        return [float("nan")] * 6, False
    idx = int(np.searchsorted(np.array(tiempos, dtype="datetime64[s]"), np.datetime64(objetivo, "s")))
    if idx == 0:
        return list(muestras[0][1]), True
    if idx >= len(muestras):
        return list(muestras[-1][1]), True
    t0, v0 = muestras[idx - 1]
    t1, v1 = muestras[idx]
    if t1 == t0:
        return list(v1), True
    w = (objetivo - t0).total_seconds() / (t1 - t0).total_seconds()
    return [a + w * (b - a) for a, b in zip(v0, v1)], True


def assemble_timeline(
    start_local: str,
    hours: list[float],
    forecast: MeteoFrame,
    climatology: MeteoFrame | None = None,
) -> WeatherTimeline:
    """Arma el clima hora a hora, marcando la fuente de cada tramo.

    Usa el forecast mientras cubre el instante pedido. Si no lo cubre, rellena
    con la climatologia (reanalysis desplazado al mismo dia/mes del anio del
    caso) y deja `source="climatology"`. Asi el tramo sin forecast no se
    inventa: queda identificado y se puede reemplazar cuando llegue el forecast.
    """
    inicio = _parse_local(start_local)
    muestras_forecast = _muestras(forecast)
    muestras_clima = _muestras(climatology) if climatology is not None else []

    puntos: list[WeatherPoint] = []
    for t_h in hours:
        objetivo = inicio + timedelta(hours=float(t_h))
        valores, dentro = _interp(muestras_forecast, objetivo)
        fuente = "forecast"
        if not dentro or not math.isfinite(valores[0]):
            fuente = "climatology"
            if muestras_clima:
                clima = [(_shift_year(dt, objetivo.year), v) for dt, v in muestras_clima]
                valores, dentro = _interp(clima, objetivo)
                if not dentro:
                    fuente = "missing"
            else:
                fuente = "missing"
        puntos.append(
            WeatherPoint(
                t_h=float(t_h),
                time_local=objetivo.isoformat(timespec="minutes"),
                temperature_C=valores[0],
                wind_ms=valores[1],
                solar_W_m2=valores[2],
                cloud_pct=valores[3],
                humidity_pct=valores[4],
                precip_mm=valores[5],
                source=fuente,
            )
        )
    return WeatherTimeline(start_local=inicio.isoformat(timespec="minutes"), points=puntos)
