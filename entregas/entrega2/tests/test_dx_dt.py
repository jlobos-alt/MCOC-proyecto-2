"""Tests del efecto de Delta x y Delta t en el solver 1D (E02).

La actividad pide modificar Delta x o Delta t y explicar el efecto observado.
Aqui se comprueba numericamente:

  * refinar Delta x -> la solucion converge a la de referencia (error O(dx^2));
  * respetar el limite de estabilidad Delta t <= dx^2/(2 alpha);
  * superar ese limite -> el esquema explicito diverge.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.thermal1d import BC, Material, solve_1d, stable_dt_1d  # noqa: E402

DIFF = Material(k=1.0, rho=1.0, cp=1.0e4)     # alpha = 1e-4 m^2/s
CONC = Material(k=2.5, rho=2400.0, cp=950.0)


class TestEfectoDx(unittest.TestCase):
    def _err(self, nx):
        L, A, T0, t_end = 1.0, 10.0, 20.0, 1500.0
        res = solve_1d(L, nx, DIFF, lambda x: T0 + A * np.sin(np.pi * x / L),
                       t_end, BC.dirichlet(T0), BC.dirichlet(T0), safety=0.4)
        exact = T0 + A * np.sin(np.pi * res.x / L) * np.exp(-DIFF.alpha * np.pi**2 * t_end)
        return np.max(np.abs(res.T_final - exact))

    def test_refinar_dx_reduce_error(self):
        e_coarse, e_fine = self._err(21), self._err(81)
        self.assertLess(e_fine, e_coarse)
        self.assertGreater(np.log2(e_coarse / e_fine), 1.8)   # ~O(dx^2)


class TestEfectoDt(unittest.TestCase):
    def test_limite_estabilidad_fo_half(self):
        dx = 0.01
        dt = stable_dt_1d(DIFF, dx, BC.dirichlet(0), BC.dirichlet(0))
        self.assertAlmostEqual(DIFF.alpha * dt / dx**2, 0.5, places=6)

    def test_dt_pequeno_no_cambia_la_solucion(self):
        a = solve_1d(1.0, 41, CONC, 20.0, 6 * 3600.0, BC.neumann(80.0), BC.adiabatic())
        dt_max = stable_dt_1d(CONC, a.info["dx"], BC.neumann(80.0), BC.adiabatic())
        b = solve_1d(1.0, 41, CONC, 20.0, 6 * 3600.0, BC.neumann(80.0), BC.adiabatic(),
                     dt=0.25 * dt_max)
        np.testing.assert_allclose(a.T_final, b.T_final, atol=0.05)

    def test_dt_grande_es_rechazado(self):
        dx = 1.0 / 100
        dt_max = stable_dt_1d(DIFF, dx, BC.dirichlet(0), BC.dirichlet(0))
        with self.assertRaises(ValueError):
            solve_1d(1.0, 101, DIFF, 0.0, 100.0, BC.dirichlet(0), BC.dirichlet(0),
                     dt=1.5 * dt_max)

    def test_dt_inestable_diverge(self):
        nx, L = 51, 1.0
        dx = L / (nx - 1)
        dt = 0.6 * dx**2 / DIFF.alpha   # Fo = 0.6 > 0.5
        rng = np.random.default_rng(0)
        res = solve_1d(L, nx, DIFF, 20 + 0.01 * rng.standard_normal(nx), 400 * dt,
                       BC.dirichlet(20), BC.dirichlet(20), dt=dt, allow_unstable=True)
        self.assertGreater(np.max(np.abs(res.T_final - 20)), 1e3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
