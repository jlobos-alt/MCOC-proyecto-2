"""Suelo como medio semi-infinito: onda anual amortiguada y resistencia de capa.

El caso del curso apoya la fundacion en el suelo. El solver no malla el suelo:
usa una condicion de Robin en la base con

    R_suelo = e_suelo / k_suelo          (capa de suelo bajo la losa)
    T_inf   = T_suelo(t)                 (temperatura no perturbada a la profundidad e)

La temperatura no perturbada se toma de una onda anual:

    T(z,t) = T_media + A exp(-z/d) cos(2 pi (t - fase)/P - z/d)
    d = sqrt(alpha P / pi),   alpha = k / (rho cp)

donde `d` es la profundidad de penetracion. A 1 m en suelo humedo la amplitud
ya bajo ~20-30 % y la fase va atrasada algunas semanas. Esto es una
aproximacion 1D: no resuelve la geometria 3D del suelo ni el flujo horizontal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .weather import TemperatureSeries


@dataclass
class SoilSpec:
    """Propiedades termicas y onda anual del suelo."""

    k: float = 1.389          # W/(m K)
    rho: float = 1600.0       # kg/m3
    cp: float = 1200.0        # J/(kg K)
    mean_C: float = 15.0
    amplitude_C: float = 4.0
    period_h: float = 8760.0
    phase_h: float = 0.0      # instante de maxima temperatura en superficie [h]
    depth_m: float = 1.0      # espesor de suelo bajo la losa

    @classmethod
    def from_dict(cls, data: dict | None) -> "SoilSpec":
        """Acepta nombres en espanol e ingles para el YAML."""
        data = data or {}
        return cls(
            k=float(data.get("k", 1.389)),
            rho=float(data.get("rho", 1600.0)),
            cp=float(data.get("cp", 1200.0)),
            mean_C=float(data.get("media_C", data.get("mean_C", 15.0))),
            amplitude_C=float(data.get("amplitud_C", data.get("amplitude_C", 0.0))),
            period_h=float(data.get("periodo_h", data.get("period_h", 8760.0))),
            phase_h=float(data.get("fase_h", data.get("phase_h", 0.0))),
            depth_m=float(data.get("profundidad_m", data.get("depth_m", 1.0))),
        )

    @property
    def alpha(self) -> float:
        """Difusividad termica [m2/s]."""
        return self.k / (self.rho * self.cp)

    @property
    def penetration_depth(self) -> float:
        """d = sqrt(alpha P / pi) [m]."""
        return math.sqrt(self.alpha * self.period_h * 3600.0 / math.pi)

    @property
    def damping(self) -> float:
        """Factor exp(-z/d) de la amplitud a la profundidad z."""
        return math.exp(-self.depth_m / self.penetration_depth)

    @property
    def phase_lag_h(self) -> float:
        """Atraso de fase a la profundidad z [h]."""
        return (self.depth_m / self.penetration_depth) / (2.0 * math.pi) * self.period_h

    @property
    def resistance(self) -> float:
        """Resistencia de la capa de suelo [m2 K/W]."""
        return self.depth_m / self.k

    def temperature(self, t_h: float) -> float:
        """T no perturbada a la profundidad `depth_m` [C]."""
        fase = self.phase_h + self.phase_lag_h
        theta = 2.0 * math.pi * (float(t_h) - fase) / self.period_h
        return self.mean_C + self.amplitude_C * self.damping * math.cos(theta)

    def series(self) -> TemperatureSeries:
        """Serie equivalente para `TemperatureSeries` (seno, no coseno)."""
        desfase = self.phase_h + self.phase_lag_h - self.period_h / 4.0
        return TemperatureSeries(
            media_C=self.mean_C,
            amplitud_C=self.amplitude_C * self.damping,
            periodo_h=self.period_h,
            desfase_h=desfase,
        )


def phase_para_maximo(dia_del_anio: int, horas_por_dia: float = 24.0) -> float:
    """Fase [h] para que la superficie del suelo tenga su maximo ese dia."""
    return float(dia_del_anio) * horas_por_dia
