"""Criterios de aceptacion del hormigon masivo.

Criterios (ICH Chile 2019, Anexo 4):

    T_max     <= 70 C      temperatura maxima en el hormigon
    delta_T   <= 20 C      diferencial termico maximo

El diferencial operacional evaluado en este proyecto es

    delta_T(t) = T_max,Omega(t) - T_min,S25(t)

donde Omega es el conjunto de celdas del nucleo (erosion de la mascara) y S25 es
el conjunto de celdas de superficie, siguiendo la denominacion de la guia del
proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .plan import CriteriaSpec
from .thermal import Result


@dataclass
class Criterio:
    """Un criterio de aceptacion y su estado."""

    nombre: str
    limite: float
    valor: float
    cumple: bool
    instante_h: float | None = None
    unidad: str = "C"

    def __str__(self) -> str:
        estado = "OK" if self.cumple else "NO CUMPLE"
        instante = "" if self.instante_h is None else f" (h={self.instante_h:.1f} h)"
        return f"{self.nombre}: {self.valor:.2f} {self.unidad} vs {self.limite:.1f} {self.unidad} -> {estado}{instante}"


@dataclass
class Veredicto:
    """Resultado de evaluar todos los criterios sobre una simulacion."""

    criterios: list[Criterio] = field(default_factory=list)

    @property
    def cumple(self) -> bool:
        return all(c.cumple for c in self.criterios)

    def resumen(self) -> str:
        lineas = [str(c) for c in self.criterios]
        lineas.append(f"VEREDICTO GLOBAL: {'CUMPLE' if self.cumple else 'NO CUMPLE'}")
        return "\n".join(lineas)

    def to_dict(self) -> dict:
        return {
            "cumple": self.cumple,
            "criterios": [
                {
                    "nombre": c.nombre,
                    "limite": c.limite,
                    "valor": c.valor,
                    "cumple": c.cumple,
                    "instante_h": c.instante_h,
                    "unidad": c.unidad,
                }
                for c in self.criterios
            ],
        }


def evaluar_criterios(result: Result, criterios: CriteriaSpec) -> Veredicto:
    """Evalua los criterios de temperatura sobre el resultado de una simulacion."""
    lista: list[Criterio] = []

    T_max = float(np.nanmax(result.T_max_global)) if result.time_h.size else float("nan")
    lista.append(
        Criterio(
            nombre="T_maxima",
            limite=criterios.T_max_C,
            valor=T_max,
            cumple=bool(T_max <= criterios.T_max_C),
            instante_h=result.time_of(result.T_max_global, T_max),
        )
    )

    if np.all(np.isnan(result.delta_T)):
        delta_max = float("nan")
        instante = None
    else:
        delta_max = float(np.nanmax(result.delta_T))
        instante = result.time_of(result.delta_T, delta_max)
    lista.append(
        Criterio(
            nombre="diferencial_termico",
            limite=criterios.delta_T_max_C,
            valor=delta_max,
            cumple=bool(delta_max <= criterios.delta_T_max_C),
            instante_h=instante,
        )
    )

    return Veredicto(criterios=lista)
