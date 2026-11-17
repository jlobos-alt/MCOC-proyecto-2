"""Problema de decision de la defensa (guia del 18-nov): el plan mas rapido con P_f <= 5 %.

Un plan u fija: particion de vertidas, esperas, temperatura de colocacion y protecciones.
Con una capacidad de colocacion r [m3/h] declarada, cada vertida dura d_j = V_j / r y las
vertidas son sucesivas (una sola cuadrilla y bomba: no hay simultaneidad):

    inicio_1 = 0 (= t0),   fin_j = inicio_j + d_j,   inicio_{j+1} = fin_j + espera
    D(u) = max_j fin_j - t0                      [h]

En cada escenario s = (curva de hidratacion m, historia de clima k):

    MT(u,s) = max_t max_{x en Omega_c(t)} T(x,t)                  Omega_c: hormigon ya colocado
    MDelta(u,s) = max_t [ max_{Omega_c(t)} T - min_{S25(t)} T ]   S25: 25 mm bajo las caras
                                                                  exteriores existentes en t
    F(u,s) = {MT > 70} U {MDelta > 20}
    P_f(u) = sum_{m,k} w_mk 1{F(u,m,k)},  w_mk = p_m q_k            (material y clima independientes)

Es una enumeracion ponderada: calcula exactamente la probabilidad del modelo discreto, sin
error de muestreo. Su incertidumbre esta en la representatividad de curvas, historias y pesos.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np

from .plan import LayerSpec, LiftSpec, Plan

LIM_T, LIM_DT = 70.0, 20.0

# Protecciones disponibles (declaradas). Laterales: moldaje de madera hasta su retiro +
# aislacion permanente. Superior: manta sobre cada techo expuesto (tambien los temporales).
# Se mantienen durante toda la ventana evaluada: el retiro se reporta aparte.
PROTECCIONES = {
    "ninguna": {"lateral": None, "superior": None},
    "EPS50": {"lateral": ("EPS_50mm", 0.050, 0.035), "superior": ("manta_EPS_50mm", 0.050, 0.035)},
    "EPS100": {"lateral": ("EPS_100mm", 0.100, 0.035), "superior": ("manta_EPS_100mm", 0.100, 0.035)},
    "EPS150": {"lateral": ("EPS_150mm", 0.150, 0.035), "superior": ("manta_EPS_150mm", 0.150, 0.035)},
}


@dataclass(frozen=True)
class PlanVertidas:
    """Un plan constructivo de la familia evaluada."""

    particion: str            # "5" (las 5 vertidas del IFC) o "unica"
    espera_h: float           # espera entre el fin de una vertida y el inicio de la siguiente
    proteccion: str           # clave de PROTECCIONES
    t_col_C: float = 18.0     # temperatura de colocacion de todas las vertidas

    @property
    def nombre(self) -> str:
        base = "unica" if self.particion == "unica" else f"5v_espera{self.espera_h:g}h"
        return f"{base}_{self.proteccion}_Tcol{self.t_col_C:g}"


def cronograma(plan: PlanVertidas, volumenes_m3: list[float], tasa_m3_h: float) -> list[tuple[float, float]]:
    """(inicio, duracion) de cada vertida en horas desde t0."""
    if plan.particion == "unica":
        return [(0.0, sum(volumenes_m3) / tasa_m3_h)]
    salida, t = [], 0.0
    for v in volumenes_m3:
        d = v / tasa_m3_h
        salida.append((t, d))
        t += d + plan.espera_h
    return salida


def duracion_D(plan: PlanVertidas, volumenes_m3: list[float], tasa_m3_h: float) -> float:
    """D(u) = fin de la ultima vertida - t0 [h]."""
    inicio, d = cronograma(plan, volumenes_m3, tasa_m3_h)[-1]
    return inicio + d


def aplicar_plan(base: Plan, plan: PlanVertidas, volumenes_m3: list[float], tasa_m3_h: float) -> Plan:
    """Copia del plan del IFC con la particion, horarios, temperatura y protecciones de `plan`."""
    p = copy.deepcopy(base)
    crono = cronograma(plan, volumenes_m3, tasa_m3_h)
    vertidas = sorted(p.vertidas, key=lambda v: v.z_min)
    if plan.particion == "unica":
        primera = vertidas[0]
        vertidas = [LiftSpec(id=1, inicio_h=0.0, z_min=vertidas[0].z_min, z_max=vertidas[-1].z_max,
                             material=primera.material, temperatura_colocacion_C=primera.temperatura_colocacion_C,
                             retiro_moldaje_h=primera.retiro_moldaje_h, moldaje=primera.moldaje,
                             aislacion=primera.aislacion)]
    for v, (inicio, d) in zip(vertidas, crono):
        v.inicio_h, v.duracion_h, v.temperatura_colocacion_C = inicio, d, plan.t_col_C
    prot = PROTECCIONES[plan.proteccion]
    if prot["lateral"]:
        nombre, e, k = prot["lateral"]
        p.aislaciones[nombre] = LayerSpec(tipo="conductiva", nombre=nombre, espesor_m=e, k=k)
        for v in vertidas:
            v.aislacion = nombre
    else:
        for v in vertidas:
            v.aislacion = "Ninguna"
    if prot["superior"]:
        nombre, e, k = prot["superior"]
        for f in p.fronteras:
            if f.direccion == "superficie":
                f.capas = [*f.capas, LayerSpec(tipo="conductiva", nombre=nombre, espesor_m=e, k=k)]
    p.vertidas = vertidas
    return p


def metricas(result, horizonte_h: float = 336.0) -> dict:
    """MT y MDelta (definicion de la guia) en los 14 dias y en la ventana extendida."""
    t = np.asarray(result.time_h)
    T = np.asarray(result.T_max_global)
    d = np.asarray(result.delta_T_s25)
    en14 = t <= horizonte_h + 1e-9

    def _max(serie, sel):
        v = serie[sel]
        return (float(np.nanmax(v)), float(t[sel][int(np.nanargmax(v))])) if np.any(np.isfinite(v)) else (np.nan, np.nan)

    MT14, tMT14 = _max(T, en14)
    MD14, tMD14 = _max(d, en14)
    MT, tMT = _max(T, np.ones_like(en14))
    MD, tMD = _max(d, np.ones_like(en14))
    return {"MT_14d": MT14, "t_MT_14d": tMT14, "MDelta_14d": MD14, "t_MDelta_14d": tMD14,
            "MT": MT, "t_MT": tMT, "MDelta": MD, "t_MDelta": tMD,
            "T_final_creciente": bool(T[-1] > T[-25] + 0.05) if T.size > 25 else False}


@dataclass
class Evaluacion:
    plan: PlanVertidas
    D_h: float
    corridas: list[dict] = field(default_factory=list)   # una por escenario, con su peso

    def _prob(self, clave) -> float:
        return float(sum(c["peso"] for c in self.corridas if clave(c)))

    @property
    def P_f(self) -> float:
        return self._prob(lambda c: c["MT"] > LIM_T or c["MDelta"] > LIM_DT)

    @property
    def P_MT(self) -> float:
        return self._prob(lambda c: c["MT"] > LIM_T)

    @property
    def P_MDelta(self) -> float:
        return self._prob(lambda c: c["MDelta"] > LIM_DT)

    @property
    def cumple(self) -> bool:
        return self.P_f <= 0.05 + 1e-12


def mas_rapido_factible(evaluaciones: list[Evaluacion]) -> Evaluacion | None:
    """Menor D entre los planes evaluados con P_f <= 5 % (desempate: menor P_f)."""
    factibles = [e for e in evaluaciones if e.cumple]
    return min(factibles, key=lambda e: (round(e.D_h, 6), e.P_f)) if factibles else None
