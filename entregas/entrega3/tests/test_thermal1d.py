"""Tests de verificación del solver 1D (corren con pytest o con unittest)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mcplan.thermal1d import BC, Material, energy, solve_1d, stable_dt_1d  # noqa: E402

# Hormigón típico
CONC = Material(k=2.5, rho=2400.0, cp=950.0)
DIFF = Material(k=1.0, rho=1.0, cp=1.0e4)       # alpha = 1e-4 m^2/s (guía)


class TestSolver1D(unittest.TestCase):

    # 1) Dirichlet: modo sinusoidal transiente contra solución exacta
    def _err_sine(self, nx):
        L, A, T0 = 1.0, 10.0, 20.0
        t_end = 1500.0
        res = solve_1d(L, nx, DIFF, lambda x: T0 + A * np.sin(np.pi * x / L),
                       t_end, BC.dirichlet(T0), BC.dirichlet(T0), dt=None, safety=0.4)
        exact = T0 + A * np.sin(np.pi * res.x / L) * np.exp(-DIFF.alpha * (np.pi / L) ** 2 * t_end)
        return np.max(np.abs(res.T_final - exact))

    def test_dirichlet_sine_exact(self):
        self.assertLess(self._err_sine(41), 5e-3)

    def test_dirichlet_convergence_order_2(self):
        e1, e2 = self._err_sine(21), self._err_sine(41)
        order = np.log2(e1 / e2)
        self.assertGreater(order, 1.8)   # FTCS con Fo fijo: O(dx^2)

    # 2) Condición inicial respetada
    def test_initial_condition(self):
        res = solve_1d(1.0, 11, CONC, 18.0, 3600.0, BC.adiabatic(), BC.adiabatic())
        np.testing.assert_allclose(res.T[0], 18.0)

    # 3) Adiabático sin fuente: conservación de energía
    def test_energy_conservation_adiabatic(self):
        nx = 51
        res = solve_1d(1.0, nx, CONC, lambda x: 20 + 30 * (x > 0.5), 48 * 3600.0,
                       BC.adiabatic(), BC.adiabatic())
        dx = res.info["dx"]
        E0, E1 = energy(res.T[0], CONC, dx), energy(res.T_final, CONC, dx)
        self.assertAlmostEqual(E1 / E0, 1.0, places=12)
        # y tiende a la temperatura media (35 °C ponderada por volumen)
        self.assertLess(np.ptp(solve_1d(1.0, nx, CONC, lambda x: 20 + 30 * (x > 0.5),
                                        200 * 24 * 3600.0, BC.adiabatic(), BC.adiabatic()).T_final), 1e-3)

    # 4) Fuente uniforme adiabática: aumento lineal dT/dt = Q/(rho cp)
    def test_uniform_source_adiabatic_linear_rise(self):
        Q, t_end = 500.0, 24 * 3600.0
        res = solve_1d(2.0, 21, CONC, 15.0, t_end, BC.adiabatic(), BC.adiabatic(), Q=Q)
        expected = 15.0 + Q * t_end / (CONC.rho * CONC.cp)
        np.testing.assert_allclose(res.T_final, expected, rtol=1e-12)

    # 5) Neumann con flujo: la energía cambia exactamente q*t
    def test_neumann_flux_energy(self):
        q_out, t_end = 100.0, 12 * 3600.0   # 100 W/m^2 saliendo por la izquierda
        res = solve_1d(1.0, 41, CONC, 20.0, t_end, BC.neumann(q_out), BC.adiabatic())
        dx = res.info["dx"]
        dE = energy(res.T_final, CONC, dx) - energy(res.T[0], CONC, dx)
        self.assertAlmostEqual(dE / (-q_out * t_end), 1.0, places=10)

    # 6) Robin: estado estacionario contra solución analítica
    def test_robin_steady_state(self):
        L, h, Tinf, Tb = 0.5, 10.0, 40.0, 10.0
        res = solve_1d(L, 26, CONC, 10.0, 30 * 24 * 3600.0,
                       BC.robin(h, Tinf), BC.dirichlet(Tb))
        q = (Tinf - Tb) / (1 / h + L / CONC.k)          # flujo estacionario
        exact = (Tb + q * L / CONC.k) - q * res.x / CONC.k
        np.testing.assert_allclose(res.T_final, exact, atol=1e-6)

    def test_robin_large_h_tends_to_dirichlet(self):
        res = solve_1d(1.0, 21, CONC, 20.0, 10 * 24 * 3600.0,
                       BC.robin(1e4, 5.0), BC.adiabatic())
        self.assertLess(abs(res.T_final[0] - 5.0), 0.05)

    # 7) Estabilidad del esquema explícito
    def test_stability_limit_fo_half(self):
        dx = 0.01
        dt = stable_dt_1d(DIFF, dx, BC.dirichlet(0), BC.dirichlet(0))
        self.assertAlmostEqual(DIFF.alpha * dt / dx**2, 0.5)

    def test_robin_reduces_dt(self):
        dx = 0.05
        d1 = stable_dt_1d(CONC, dx, BC.adiabatic(), BC.adiabatic())
        d2 = stable_dt_1d(CONC, dx, BC.robin(500.0, 0), BC.adiabatic())
        self.assertLess(d2, d1)

    def test_rejects_unstable_dt(self):
        with self.assertRaises(ValueError):
            solve_1d(1.0, 101, DIFF, 0.0, 100.0, BC.dirichlet(0), BC.dirichlet(0), dt=1.0)

    def test_unstable_blows_up(self):
        nx, L = 51, 1.0
        dx = L / (nx - 1)
        dt = 0.6 * dx**2 / DIFF.alpha                    # Fo = 0.6 > 0.5
        rng = np.random.default_rng(0)
        res = solve_1d(L, nx, DIFF, 20 + 0.01 * rng.standard_normal(nx), 400 * dt,
                       BC.dirichlet(20), BC.dirichlet(20), dt=dt, allow_unstable=True)
        self.assertGreater(np.max(np.abs(res.T_final - 20)), 1e3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
