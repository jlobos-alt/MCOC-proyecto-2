"""Series temporales de temperatura ambiente y de suelo.

    kind = "constante"   T = media
    kind = "diurna"      T = media + amplitud * sin(2*pi*(t - desfase)/periodo)
    kind = "datos"       interpolacion lineal de una serie (t_h, T_C)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TemperatureSeries:
    """Serie de temperatura [C] evaluable en cualquier instante [h]."""

    media_C: float = 15.0
    amplitud_C: float = 0.0
    periodo_h: float = 24.0
    desfase_h: float = 0.0
    datos: list[tuple[float, float]] = field(default_factory=list)

    def __call__(self, t_h: float | np.ndarray) -> float | np.ndarray:
        if self.datos:
            times = np.array([t for t, _ in self.datos], dtype=float)
            values = np.array([v for _, v in self.datos], dtype=float)
            return np.interp(t_h, times, values)
        if self.amplitud_C == 0.0:
            return self.media_C
        phase = 2.0 * np.pi * (np.asarray(t_h, dtype=float) - self.desfase_h) / self.periodo_h
        return self.media_C + self.amplitud_C * np.sin(phase)

    @classmethod
    def from_spec(cls, spec: dict | None) -> "TemperatureSeries":
        spec = spec or {}
        return cls(
            media_C=float(spec.get("media_C", 15.0)),
            amplitud_C=float(spec.get("amplitud_C", 0.0)),
            periodo_h=float(spec.get("periodo_h", 24.0)),
            desfase_h=float(spec.get("desfase_h", 0.0)),
            datos=[(float(t), float(v)) for t, v in spec.get("datos", [])],
        )
