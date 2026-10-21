"""Calor de hidratacion a partir de la elevacion adiabatica.

La elevacion adiabatica acumulada theta_ad(age) se modela con una suma de
exponenciales:

    theta_ad(age) = sum_i theta_inf_i * (1 - exp(-age / tau_i))

y el calor volumetrico equivalente se obtiene de:

    qdot = rho * cp * d(theta_ad)/d(age)

El factor de madurez de Arrhenius escala la velocidad de hidratacion segun la
temperatura real de la celda:

    m(T) = exp(-Ea/R * (1/T - 1/T_ref))

La edad equivalente de cada celda es:

    age_eq(t) = integral_0^t m(T(tau)) dtau
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

R_GAS = 8.314462618  # J/(mol K)

DEFAULT_ACTIVATION_TEMPERATURE = 4000.0  # K
DEFAULT_REFERENCE_TEMPERATURE = 293.15  # K (20 C)


@dataclass(frozen=True)
class HydrationModel:
    """Elevacion adiabatica de dos terminos con correccion opcional de madurez."""

    theta_inf_1_C: float = 45.0
    tau_1_h: float = 30.0
    theta_inf_2_C: float = 0.0
    tau_2_h: float = 0.0
    activation_temperature_K: float = 0.0
    reference_temperature_K: float = DEFAULT_REFERENCE_TEMPERATURE

    @property
    def uses_maturity(self) -> bool:
        return self.activation_temperature_K > 0.0

    def theta(self, age_h: np.ndarray | float) -> np.ndarray:
        """Elevacion adiabatica acumulada [C] para la edad dada [h]."""
        age = np.asarray(age_h, dtype=float)
        theta = self.theta_inf_1_C * (1.0 - np.exp(-age / self.tau_1_h))
        if self.theta_inf_2_C:
            theta = theta + self.theta_inf_2_C * (1.0 - np.exp(-age / self.tau_2_h))
        return theta

    def dtheta_dage(self, age_h: np.ndarray | float) -> np.ndarray:
        """Derivada de la elevacion adiabatica [C/h]."""
        age = np.asarray(age_h, dtype=float)
        rate = (self.theta_inf_1_C / self.tau_1_h) * np.exp(-age / self.tau_1_h)
        if self.theta_inf_2_C:
            rate = rate + (self.theta_inf_2_C / self.tau_2_h) * np.exp(-age / self.tau_2_h)
        return rate

    def maturity_factor(self, temperature_C: np.ndarray | float) -> np.ndarray:
        """Factor de madurez de Arrhenius (1.0 si el modelo no usa madurez)."""
        if not self.uses_maturity:
            return np.ones_like(np.asarray(temperature_C, dtype=float))
        temperature_K = np.asarray(temperature_C, dtype=float) + 273.15
        temperature_K = np.maximum(temperature_K, 1.0)
        exponent = -self.activation_temperature_K / R_GAS * (
            1.0 / temperature_K - 1.0 / self.reference_temperature_K
        )
        return np.exp(np.clip(exponent, -50.0, 50.0))

    def heat_rate(
        self,
        age_h: np.ndarray | float,
        temperature_C: np.ndarray | float = None,
        volumetric_heat_capacity: float = 2.328e6,
        aplicar_madurez: bool = True,
    ) -> np.ndarray:
        """Calor volumetrico de hidratacion [W/m^3]."""
        age = np.asarray(age_h, dtype=float)
        rate = self.dtheta_dage(age) / 3600.0
        if temperature_C is not None and self.uses_maturity and aplicar_madurez:
            rate = rate * self.maturity_factor(temperature_C)
        return volumetric_heat_capacity * rate
