"""Fronteras termicas como redes de resistencias en serie.

El camino termico desde el centro de una celda hasta el medio ambiente es:

    R_total = (d/2)/k_celda + R_capas + R_ambiente

con

    R_capas = suma de las capas activas (moldaje, aislacion, contacto con suelo)
    R_ambiente = 1/h  (conveccion) o 0 (contacto con suelo)

Una vez conocido R_total, la conductancia de la cara es G = A / R_total y el
intercambio con el medio se escribe como:

    Q = G * (T_infinito - T_celda)

Una frontera Neumann no tiene resistencia: impone directamente el flujo
q_n [W/m^2] (n hacia afuera, q_n > 0 sale calor), Q = -q_n * A. Adiabatica es
el caso q_n = 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class ConductionLayer:
    """Capa conductiva de espesor y conductividad dados."""

    thickness: float
    conductivity: float
    name: str = "capa"

    @property
    def resistance(self) -> float:
        """Resistencia por unidad de area [m^2 K/W]."""
        if self.conductivity <= 0.0:
            return float("inf")
        return self.thickness / self.conductivity


@dataclass(frozen=True)
class ConvectionLayer:
    """Capa convectiva con coeficiente h [W/(m^2 K)]."""

    h: float
    name: str = "conveccion"

    @property
    def resistance(self) -> float:
        if self.h <= 0.0:
            return float("inf")
        return 1.0 / self.h


@dataclass(frozen=True)
class ScheduledLayer:
    """Capa presente solo en un intervalo de tiempo [desde_h, hasta_h)."""

    layer: ConductionLayer | ConvectionLayer
    desde_h: float = 0.0
    hasta_h: float = float("inf")

    def active_at(self, t_h: float) -> bool:
        return self.desde_h <= t_h < self.hasta_h


@dataclass
class BoundaryGroup:
    """Conjunto de caras de frontera que comparten la misma fisica."""

    name: str
    tipo: str = "convectiva"
    h: float = 12.0
    capas: list[ScheduledLayer] = field(default_factory=list)
    far_field: Callable[[float], float] = lambda t: 15.0
    valor_dirichlet_C: float | None = None
    flujo_W_m2: float = 0.0
    # Conveccion variable en el tiempo: h(t) [W/(m2 K)]. Si es None se usa `h`.
    h_series: Callable[[float], float] | None = None
    # Cota superior de h en el horizonte, para dimensionar el paso estable.
    h_max: float | None = None

    def capas_resistance(self, t_h: float) -> float:
        """Resistencia por unidad de area de las capas activas [m^2 K/W]."""
        total = 0.0
        for scheduled in self.capas:
            if scheduled.active_at(t_h):
                total += scheduled.layer.resistance
        return total

    def convective_resistance(self, t_h: float = 0.0) -> float:
        if self.tipo == "convectiva":
            h = self.h_series(t_h) if self.h_series is not None else self.h
            return 1.0 / h if h > 0.0 else float("inf")
        return 0.0

    def resistance(self, t_h: float) -> float:
        """Resistencia total por unidad de area de la frontera [m^2 K/W]."""
        if self.tipo in ("adiabatica", "neumann"):
            return float("inf")
        return self.capas_resistance(t_h) + self.convective_resistance(t_h)

    def minimum_resistance(self, breakpoints: list[float]) -> float:
        """Menor resistencia del grupo en el horizonte [m^2 K/W]."""
        candidates = [0.0] + [b for b in breakpoints if b >= 0.0]
        capas = min(self.capas_resistance(t) for t in candidates)
        if self.h_series is not None:
            h_max = self.h_max
            if h_max is None:
                h_max = max(self.h_series(t) for t in candidates)
            r_conv = 1.0 / h_max if h_max > 0.0 else float("inf")
        else:
            r_conv = self.convective_resistance(0.0)
        return capas + r_conv

    def far_field_at(self, t_h: float) -> float:
        if self.tipo == "dirichlet" and self.valor_dirichlet_C is not None:
            return float(self.valor_dirichlet_C)
        return float(self.far_field(t_h))
