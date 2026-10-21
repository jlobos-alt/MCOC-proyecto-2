"""Analisis de confiabilidad por simulacion Monte Carlo.

Se muestrea la incertidumbre de los parametros de entrada, se resuelve el caso
para cada muestra y se estiman las probabilidades de excedencia de los
criterios:

    P(T_max > 70 C)
    P(delta_T_max > 20 C)

El muestreo es reproducible: la misma semilla produce exactamente los mismos
resultados.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .criteria import evaluar_criterios
from .plan import Plan, apply_overrides
from .thermal import build_model, solve


@dataclass(frozen=True)
class Incertidumbre:
    """Parametro incierto: distribucion y recorrido de la variable de entrada."""

    ruta: str
    tipo: str = "normal"
    media: float = 0.0
    desviacion: float = 1.0
    minimo: float = -np.inf
    maximo: float = np.inf
    multiplicativo: bool = False

    def muestrear(self, rng: np.random.Generator) -> float:
        if self.tipo == "uniforme":
            valor = rng.uniform(self.minimo, self.maximo)
        else:
            valor = rng.normal(self.media, self.desviacion)
        if self.multiplicativo:
            valor = self.media * valor
        return float(np.clip(valor, self.minimo, self.maximo))

    @property
    def ruta_override(self) -> str:
        """Ruta a usar en `apply_overrides` (con * si el valor es un factor)."""
        return f"{self.ruta}*" if self.multiplicativo else self.ruta


INCERTIDUMBREZES_FUNDACION: list[Incertidumbre] = [
    Incertidumbre(
        ruta="vertidas.temperatura_colocacion_C",
        media=18.0,
        desviacion=2.0,
        minimo=5.0,
        maximo=35.0,
    ),
    Incertidumbre(
        ruta="ambiente.media_C",
        media=15.0,
        desviacion=3.0,
        minimo=0.0,
        maximo=30.0,
    ),
    Incertidumbre(
        ruta="hidratacion.elevacion_adibatica_C",
        media=45.0,
        desviacion=5.0,
        minimo=25.0,
        maximo=65.0,
    ),
    Incertidumbre(
        ruta="hidratacion.tau_h",
        media=30.0,
        desviacion=3.0,
        minimo=15.0,
        maximo=60.0,
    ),
    Incertidumbre(
        ruta="materiales.M1.k",
        tipo="normal",
        media=1.0,
        desviacion=0.1,
        minimo=0.7,
        maximo=1.4,
        multiplicativo=True,
    ),
    Incertidumbre(
        ruta="materiales.M1.cp",
        media=1.0,
        desviacion=0.05,
        minimo=0.85,
        maximo=1.2,
        multiplicativo=True,
    ),
    Incertidumbre(
        ruta="materiales.M1.rho",
        media=1.0,
        desviacion=0.05,
        minimo=0.9,
        maximo=1.1,
        multiplicativo=True,
    ),
]


@dataclass
class MuestraConfiabilidad:
    """Resultados del muestreo Monte Carlo."""

    n_muestras: int
    semilla: int
    T_max: np.ndarray
    delta_T_max: np.ndarray
    lim_T_max_C: float
    lim_delta_T_C: float
    duracion_s: float
    metadata: dict = field(default_factory=dict)

    @property
    def prob_T_max(self) -> float:
        """Probabilidad de exceder el limite de temperatura maxima."""
        if self.n_muestras == 0:
            return float("nan")
        return float(np.mean(self.T_max > self.lim_T_max_C))

    @property
    def prob_delta_T(self) -> float:
        """Probabilidad de exceder el limite de diferencial termico."""
        if self.n_muestras == 0:
            return float("nan")
        return float(np.mean(self.delta_T_max > self.lim_delta_T_C))

    @property
    def prob_falla(self) -> float:
        """Probabilidad de que al menos un criterio falle."""
        if self.n_muestras == 0:
            return float("nan")
        return float(
            np.mean((self.T_max > self.lim_T_max_C) | (self.delta_T_max > self.lim_delta_T_C))
        )

    def cuantiles(self, niveles=(0.5, 0.9, 0.95)) -> dict:
        salida: dict = {}
        for nivel in niveles:
            salida[f"T_max_P{int(nivel * 100)}"] = float(
                np.quantile(self.T_max, nivel)
            )
            salida[f"dT_max_P{int(nivel * 100)}"] = float(
                np.quantile(self.delta_T_max, nivel)
            )
        return salida

    def to_dict(self) -> dict:
        return {
            "n_muestras": self.n_muestras,
            "semilla": self.semilla,
            "P_T_max_supera": self.prob_T_max,
            "P_delta_T_supera": self.prob_delta_T,
            "P_falla_alguna": self.prob_falla,
            "limite_T_max_C": self.lim_T_max_C,
            "limite_delta_T_C": self.lim_delta_T_C,
            "T_max_min": float(np.min(self.T_max)),
            "T_max_max": float(np.max(self.T_max)),
            "T_max_media": float(np.mean(self.T_max)),
            "delta_T_min": float(np.min(self.delta_T_max)),
            "delta_T_max": float(np.max(self.delta_T_max)),
            "delta_T_media": float(np.mean(self.delta_T_max)),
            "duracion_s": self.duracion_s,
            **self.cuantiles(),
            **self.metadata,
        }


def ejecutar_montecarlo(
    plan: Plan,
    n_muestras: int = 200,
    semilla: int = 20240915,
    incertidumbres: list[Incertidumbre] | None = None,
    duracion_h: float | None = None,
    intervalo_salida_h: float | None = None,
    verbose: bool = False,
) -> MuestraConfiabilidad:
    """Ejecuta el Monte Carlo y devuelve las probabilidades de excedencia."""
    if incertidumbres is None:
        incertidumbres = INCERTIDUMBREZES_FUNDACION

    rng = np.random.default_rng(semilla)
    duracion = duracion_h if duracion_h is not None else plan.simulacion.duracion_h
    intervalo = intervalo_salida_h if intervalo_salida_h is not None else plan.simulacion.intervalo_salida_h

    T_max = np.zeros(n_muestras)
    delta_T_max = np.zeros(n_muestras)
    inicio = time.perf_counter()

    for indice in range(n_muestras):
        valores = {inc.ruta_override: inc.muestrear(rng) for inc in incertidumbres}
        caso = apply_overrides(plan, valores)
        model = build_model(caso)
        result = solve(
            model,
            duracion_h=duracion,
            intervalo_salida_h=intervalo,
            factor_estabilidad=caso.simulacion.factor_estabilidad,
        )
        veredicto = evaluar_criterios(result, caso.criterios)
        T_max[indice] = veredicto.criterios[0].valor
        delta_T_max[indice] = veredicto.criterios[1].valor
        if verbose and (indice + 1) % 25 == 0:
            print(
                f"  muestra {indice + 1}/{n_muestras}: "
                f"T_max={T_max[indice]:.1f} C  dT_max={delta_T_max[indice]:.1f} C"
            )

    return MuestraConfiabilidad(
        n_muestras=n_muestras,
        semilla=semilla,
        T_max=T_max,
        delta_T_max=delta_T_max,
        lim_T_max_C=plan.criterios.T_max_C,
        lim_delta_T_C=plan.criterios.delta_T_max_C,
        duracion_s=time.perf_counter() - inicio,
        metadata={
            "dx_m": plan.geometria.dx,
            "duracion_h": duracion,
            "incertidumbres": [inc.ruta for inc in incertidumbres],
        },
    )
