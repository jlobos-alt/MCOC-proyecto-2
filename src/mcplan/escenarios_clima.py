"""Pocas historias meteorologicas completas a partir de un ensemble (guia del 18-nov, 4.2).

Un ensemble trae N miembros: cada uno es una trayectoria completa y coherente del clima
(ciclo diario, persistencia y relacion entre variables). En vez de sortear horas sueltas o
sumar un desfase inventado, se eligen pocas trayectorias completas:

1. Se ordenan los miembros por su temperatura media en la ventana de la obra.
2. Se dividen en k grupos de tamano parecido (terciles si k = 3).
3. De cada grupo se toma el miembro mas cercano a la mediana del grupo (el que mejor lo
   representa) y recibe un peso igual a la fraccion de miembros del grupo.

Se pierden los extremos de cada grupo: el miembro mas frio y el mas calido no se simulan.
Por eso el criterio de orden (T media) y los pesos son hipotesis del modelo, se declaran y
se someten a sensibilidad. El frio puede aumentar el diferencial: no es favorable por si
mismo.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from .meteo import VARIABLES, MeteoFrame, Site, normalize_payload

ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"


def descargar_ensemble(site: Site, model: str = "gfs_seamless", days: int = 16,
                       timeout_s: float = 90.0) -> tuple[dict, bytes]:
    """JSON crudo del ensemble de Open-Meteo para el sitio (todas las variables del proyecto)."""
    params = {
        "latitude": site.latitude,
        "longitude": site.longitude,
        "hourly": ",".join(VARIABLES),
        "models": model,
        "forecast_days": int(days),
        "timezone": site.timezone,
        "wind_speed_unit": "ms",
    }
    url = ENSEMBLE + "?" + urllib.parse.urlencode(params)
    pedido = urllib.request.Request(url, headers={"User-Agent": "mcplan-defensa/1.0"})
    with urllib.request.urlopen(pedido, timeout=timeout_s) as respuesta:
        crudo = respuesta.read()
    return json.loads(crudo.decode("utf-8")), crudo


def nombres_miembros(payload: dict) -> list[str]:
    """'control' para la serie sin sufijo y 'member01'... para el resto."""
    claves = (payload.get("hourly") or {}).keys()
    sufijos = sorted({k.split("_member")[1] for k in claves if "_member" in k})
    return ["control"] + [f"member{s}" for s in sufijos]


def miembro(payload: dict, nombre: str, model: str, fetched_at: str, raw: bytes = b"") -> MeteoFrame:
    """Serie de un miembro como `MeteoFrame` normal (mismas columnas que un forecast)."""
    hourly = payload["hourly"]
    sufijo = "" if nombre == "control" else f"_{nombre}"
    propio = {"time": hourly["time"]}
    for var in VARIABLES:
        clave = var + sufijo
        if clave in hourly:
            propio[var] = hourly[clave]
    frame = normalize_payload(
        {**{k: v for k, v in payload.items() if k != "hourly"}, "hourly": propio},
        source=f"open-meteo-ensemble-{model}",
        issued_at=fetched_at,
        endpoint=ENSEMBLE,
        model=f"{model}:{nombre}",
        raw=raw,
    )
    frame.fetched_at = fetched_at
    return frame


@dataclass
class Representativo:
    nombre: str
    frame: MeteoFrame
    peso: float
    representa: list[str]
    T_media_C: float
    rango_grupo_C: tuple[float, float]


def representativos(frames: dict[str, MeteoFrame], desde_local: str, hasta_local: str,
                    k: int = 3) -> list[Representativo]:
    """Elige k miembros por grupos de temperatura media en [desde, hasta]; peso = fraccion del grupo."""
    t0 = datetime.fromisoformat(desde_local).replace(tzinfo=None)
    t1 = datetime.fromisoformat(hasta_local).replace(tzinfo=None)
    medias = {}
    for nombre, f in frames.items():
        valores = [T for t, T in zip(f.times, f.temperature_C)
                   if t0 <= datetime.fromisoformat(t) <= t1 and np.isfinite(T)]
        medias[nombre] = float(np.mean(valores))
    orden = sorted(medias, key=lambda n: medias[n])
    grupos = np.array_split(np.array(orden, dtype=object), k)
    salida = []
    for g in grupos:
        g = list(g)
        mediana = float(np.median([medias[n] for n in g]))
        elegido = min(g, key=lambda n: (abs(medias[n] - mediana), n))
        salida.append(Representativo(
            nombre=elegido, frame=frames[elegido], peso=len(g) / len(orden), representa=g,
            T_media_C=medias[elegido], rango_grupo_C=(min(medias[n] for n in g), max(medias[n] for n in g)),
        ))
    return salida


def ahora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
