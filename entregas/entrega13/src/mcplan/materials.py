"""Propiedades termicas de materiales, en unidades SI.

    k    [W/(m K)]    conductividad termica
    cp   [J/(kg K)]   calor especifico
    rho  [kg/m^3]     densidad

Los valores por defecto de hormigon y suelo corresponden a los publicados por
Ju y Lei (2019) y se usan como sanity check, no como mezcla definitiva del
proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """Material homogeneo con propiedades termicas constantes."""

    name: str
    k: float
    cp: float
    rho: float

    @property
    def alpha(self) -> float:
        """Difusividad termica [m^2/s]."""
        return self.k / (self.rho * self.cp)

    @property
    def volumetric_heat_capacity(self) -> float:
        """Capacidad calorifica volumetrica [J/(m^3 K)]."""
        return self.rho * self.cp


CONCRETE_M1 = Material("M1", k=2.222, cp=970.0, rho=2400.0)
CONCRETE_M2 = Material("M2", k=2.222, cp=970.0, rho=2400.0)
SOIL = Material("suelo", k=1.389, cp=1273.0, rho=1800.0)
TIMBER = Material("moldaje_madera", k=0.17, cp=1700.0, rho=600.0)
EPS = Material("aislacion_eps", k=0.037, cp=1300.0, rho=30.0)

DEFAULT_MATERIALS: dict[str, Material] = {
    "M1": CONCRETE_M1,
    "M2": CONCRETE_M2,
    "suelo": SOIL,
    "moldaje_madera": TIMBER,
    "aislacion_eps": EPS,
}
