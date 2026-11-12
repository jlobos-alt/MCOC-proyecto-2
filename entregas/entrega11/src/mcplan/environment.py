"""Ambiente real en la frontera: viento, radiacion y temperatura sol-aire.

El solver resuelve un Robin con `h` y `T_inf`:

    -k dT/dn = h (T - T_inf)

Este modulo traduce clima a esos dos parametros. La regla para no doble contar
radiacion es elegir **una** de las dos vias:

1. Via sol-aire (la que usa el demo): se juntan conveccion y radiacion en un
   unico `h_total` y una unica `T_sol_aire`. El solver ve un solo Robin.
2. Via flujos separados: `h` solo convectivo y la radiacion entra como flujo
   `q_rad` (Neumann) o como `far_field = T_cielo` con `h_rad` aparte.

Nunca se suman las dos vias: o la radiacion esta dentro de `T_sol_aire`, o esta
como flujo, pero no ambas.

Convenciones: T [C], G [W/m2], v [m/s], h [W/(m2 K)].
"""

from __future__ import annotations

import math

SIGMA = 5.670374419e-8  # Stefan-Boltzmann [W/(m2 K^4)]


def wind_convection_coefficient(v_ms: float, a: float = 5.7, b: float = 3.8) -> float:
    """h convectivo forzado sobre pared plana (ASHRAE): h = a + b v.

    `a` incluye la conveccion natural; `b` el efecto del viento. Para v = 0
    queda h = 5.7 W/(m2 K), un valor usual para aire en calma.
    """
    return a + b * max(float(v_ms), 0.0)


def radiative_coefficient(T_surface_C: float, emissivity: float = 0.9) -> float:
    """Coeficiente linealizado de radiacion de onda larga [W/(m2 K)].

    h_r = 4 eps sigma T^3. Se usa para pasar radiacion a un Robin equivalente.
    """
    T_k = float(T_surface_C) + 273.15
    return 4.0 * emissivity * SIGMA * T_k**3


def sky_temperature(T_air_C: float, cloud_cover: float = 0.0) -> float:
    """T de cielo aproximada (Berdahl-Martin simplificada).

    Cielo claro: hasta ~12 K bajo el aire; nublado: casi igual al aire.
    Es una aproximacion para el curso, no un modelo de radiacion de onda larga.
    """
    cloud = min(max(float(cloud_cover), 0.0), 1.0)
    return float(T_air_C) - 12.0 * (1.0 - 0.75 * cloud**3.4)


def sol_air_temperature(
    T_air_C: float,
    solar_W_m2: float,
    h_total_W_m2K: float,
    absorptivity: float = 0.6,
    T_sky_C: float | None = None,
    emissivity: float = 0.9,
) -> float:
    """T sol-aire: temperatura ficticia que entrega el mismo flujo que sol+cielo.

        T_sa = T_aire + [alpha G + eps sigma (T_cielo^4 - T_aire^4)] / h_total

    Con `T_sky_C=None` no se agrega onda larga (el `h_total` debe incluirla).
    """
    if h_total_W_m2K <= 0.0:
        return float(T_air_C)
    q_solar = absorptivity * max(float(solar_W_m2), 0.0)
    q_lw = 0.0
    if T_sky_C is not None:
        T_air_k = float(T_air_C) + 273.15
        T_sky_k = float(T_sky_C) + 273.15
        q_lw = emissivity * SIGMA * (T_sky_k**4 - T_air_k**4)
    return float(T_air_C) + (q_solar + q_lw) / h_total_W_m2K


def surface_heat_fluxes(
    T_surface_C: float,
    T_air_C: float,
    solar_W_m2: float,
    wind_ms: float,
    absorptivity: float = 0.6,
    emissivity: float = 0.9,
    cloud_cover: float = 0.0,
) -> dict[str, float]:
    """Flujos por unidad de area con signo positivo **hacia** el hormigon.

    Sirve para explicar el balance en la defensa:
        q_conv + q_solar + q_lw = q_neto
    y para comprobar que no se cuenta dos veces la radiacion.
    """
    h_conv = wind_convection_coefficient(wind_ms)
    h_rad = radiative_coefficient(T_surface_C, emissivity)
    T_sky = sky_temperature(T_air_C, cloud_cover)
    q_conv = h_conv * (T_air_C - T_surface_C)
    q_solar = absorptivity * max(float(solar_W_m2), 0.0)
    q_lw = h_rad * (T_sky - T_surface_C)
    return {
        "h_conv": h_conv,
        "h_rad": h_rad,
        "q_conv": q_conv,
        "q_solar": q_solar,
        "q_lw": q_lw,
        "q_neto": q_conv + q_solar + q_lw,
    }


def formwork_resistance(thickness_m: float, conductivity_W_mK: float) -> float:
    """Resistencia termica de moldaje o aislacion [m2 K/W]: R = e / k."""
    if conductivity_W_mK <= 0.0:
        raise ValueError("La conductividad del moldaje debe ser > 0.")
    return float(thickness_m) / float(conductivity_W_mK)


def effective_h(h_convective: float, r_layers: float) -> float:
    """h equivalente de una pared con capas: 1/h_eff = R_capas + 1/h."""
    if h_convective <= 0.0:
        return 0.0
    return 1.0 / (r_layers + 1.0 / h_convective)


def air_density(T_air_C: float, pressure_Pa: float = 101325.0) -> float:
    """Densidad del aire [kg/m3] (gas ideal, aire seco)."""
    return pressure_Pa / (287.05 * (float(T_air_C) + 273.15))


def wind_pressure(v_ms: float, rho_kg_m3: float = 1.2, cp: float = 0.6) -> float:
    """Presion dinamica de viento [Pa]: q = 0.5 rho v^2 (referencia para cargas)."""
    return 0.5 * rho_kg_m3 * cp * float(v_ms) ** 2


def dew_point(T_air_C: float, relative_humidity_pct: float) -> float:
    """Punto de rocio [C] con la aproximacion de Magnus."""
    rh = min(max(float(relative_humidity_pct), 1.0), 100.0)
    a, b = 17.62, 243.12
    gamma = math.log(rh / 100.0) + a * float(T_air_C) / (b + float(T_air_C))
    return b * gamma / (a - gamma)


# ---------------------------------------------------------------------------
# Puente clima -> frontera del solver
# ---------------------------------------------------------------------------


def condiciones_de_timeline(
    timeline,
    con_viento: bool = True,
    con_radiacion: bool = True,
    absorptivity: float = 0.6,
    emissivity: float = 0.9,
) -> tuple[object, object]:
    """Devuelve `h(t)` y `T_sol_aire(t)` listos para un Robin.

    La radiacion entra **solo** por `T_sol_aire`: el flujo solar y el intercambio
    de onda larga se dividen por `h_total`. El `h_total` incluye la parte
    radiativa linealizada, de modo que el Robin
    `-k dT/dn = h_total (T - T_sol_aire)` reproduce el balance completo sin
    sumar dos veces la radiacion.
    """

    def h_fn(t_h: float) -> float:
        punto = timeline.at(float(t_h))
        h_conv = wind_convection_coefficient(punto.wind_ms) if con_viento else wind_convection_coefficient(0.0)
        if not con_radiacion:
            return h_conv
        return h_conv + radiative_coefficient(punto.temperature_C, emissivity)

    def t_fn(t_h: float) -> float:
        punto = timeline.at(float(t_h))
        if not con_radiacion:
            return float(punto.temperature_C)
        cielo = sky_temperature(punto.temperature_C, punto.cloud_pct / 100.0)
        return sol_air_temperature(
            punto.temperature_C,
            punto.solar_W_m2,
            h_fn(t_h),
            absorptivity=absorptivity,
            T_sky_C=cielo,
            emissivity=emissivity,
        )

    return h_fn, t_fn


def aplicar_ambiente(
    plan,
    timeline,
    con_viento: bool = True,
    con_radiacion: bool = True,
    absorptivity: float = 0.6,
    emissivity: float = 0.9,
):
    """Inyecta el clima real en las fronteras del plan (no toca la base).

    La base sigue gobernada por el suelo: su `far_field` es la temperatura del
    suelo a la profundidad de la capa y su resistencia viene de `plan.suelo`.
    """
    h_fn, t_fn = condiciones_de_timeline(
        timeline,
        con_viento=con_viento,
        con_radiacion=con_radiacion,
        absorptivity=absorptivity,
        emissivity=emissivity,
    )
    for frontera in plan.fronteras:
        if frontera.direccion == "base":
            continue
        frontera.h_series = h_fn
        frontera.far_field_series = t_fn
    plan.ambiente.datos = [(p.t_h, t_fn(p.t_h)) for p in timeline.points]
    return plan
