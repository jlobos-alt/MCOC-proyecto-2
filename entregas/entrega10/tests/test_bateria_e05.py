"""Bateria de verificacion E05 sobre el solver 3D (src/mcplan/thermal.py).

Cada test usa un caso de `mcplan.verificacion`. Los parametrizados muestran que
los casos siguen pasando al cambiar L, n, material, q0, q_n, h, etc.

    python -m pytest tests/test_bateria_e05.py -v
    python -m pytest tests/test_bateria_e05.py -v -k neumann
"""

from __future__ import annotations

import pytest

from mcplan import verificacion as v

ACERO = {"k": 50.0, "rho": 7850.0, "cp": 490.0}
SUELO = {"k": 1.39, "rho": 1800.0, "cp": 1273.0}


# --- soluciones sinusoidales -------------------------------------------------

@pytest.mark.parametrize("L", [(1.0,), (2.0,), (0.5,)])
def test_sinusoidal_1d(L):
    caso = v.caso_sinusoidal(1, L=L + (1.0, 1.0), t_h=24.0)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("L", [(1.0, 1.0), (1.0, 0.6), (2.0, 1.5)])
def test_sinusoidal_2d(L):
    caso = v.caso_sinusoidal(2, L=L + (1.0,))[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("L", [(1.0, 1.0, 1.0), (1.2, 0.8, 0.5)])
def test_sinusoidal_3d(L):
    caso = v.caso_sinusoidal(3, L=L, n=16)[0]
    assert caso.ok, caso.linea()


def test_sinusoidal_otro_material():
    caso = v.caso_sinusoidal(2, L=(1.0, 1.0, 1.0), mat=SUELO, A=25.0, T0=10.0, t_h=48.0)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("dim,ns", [(1, (10, 20, 40)), (2, (10, 20, 40)), (3, (8, 16, 32))])
def test_convergencia_orden_2(dim, ns):
    caso = v.convergencia(dim, ns=ns)
    assert caso.ok, caso.linea()


# --- energia y fuente --------------------------------------------------------

@pytest.mark.parametrize("semilla", [0, 1])
def test_energia_se_conserva_adiabatico(semilla):
    caso = v.caso_energia_adiabatica(semilla=semilla)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("q0", [500.0, 2500.0])
def test_energia_con_fuente(q0):
    caso = v.caso_energia_adiabatica(q0=q0)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("q0,mat", [(1000.0, v.CONCRETO), (300.0, v.CONCRETO), (1000.0, ACERO)])
def test_fuente_uniforme_sube_lineal(q0, mat):
    caso = v.caso_fuente_uniforme(q0=q0, mat=mat)[0]
    assert caso.ok, caso.linea()


# --- condiciones de borde ----------------------------------------------------

@pytest.mark.parametrize("q_n", [-100.0, 250.0])
def test_neumann_balance(q_n):
    caso = v.caso_neumann_balance(q_n=q_n)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("q_n,L", [(-50.0, 1.0), (30.0, 0.5)])
def test_neumann_permanente(q_n, L):
    caso = v.caso_neumann_permanente(q_n=q_n, L=L)[0]
    assert caso.ok, caso.linea()


@pytest.mark.parametrize("h", [2.0, 10.0, 100.0])
def test_robin_permanente(h):
    caso = v.caso_robin_permanente(h=h)[0]
    assert caso.ok, caso.linea()


def test_robin_h_grande_tiende_a_dirichlet():
    caso, model, result = v.caso_robin_permanente(h=1e6, T_D=60.0, T_inf=20.0)
    # con h -> inf la superficie queda a T_inf: perfil lineal 60 -> 20 entre dos Dirichlet.
    # La ultima celda (centro a dx/2 = 0.025 m del borde) queda en 20 + 40*0.025 = 21 C
    assert caso.ok, caso.linea()
    assert abs(caso.datos["numerico"][-1] - 21.0) < 1e-3


def test_robin_capacidad_agrupada():
    caso = v.caso_robin_transitorio()[0]
    assert caso.ok, caso.linea()


def test_dt_inestable_diverge():
    """Con dt sobre el limite C/(sum G) el esquema explicito explota."""
    from mcplan.thermal import estimate_timestep, solve
    caso, model, result, _ = v.caso_sinusoidal(2, n=10, t_h=1.0)
    dt_lim = estimate_timestep(model, safety=1.0)
    malo = solve(model, duracion_h=200 * 3 * dt_lim / 3600, intervalo_salida_h=3 * dt_lim / 3600,
                 dt_s=3 * dt_lim, temperatura_inicial=result.T_final.ravel())
    assert abs(malo.T_final).max() > 1e3
