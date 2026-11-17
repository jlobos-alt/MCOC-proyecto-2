"""Verificacion numerica del solver termico.

Casos:
    1. Convergencia 1D contra la solucion analitica de un perfil sinusoidal.
    2. Convergencia 2D contra la solucion analitica de una placa.
    3. Conservacion de la energia en un dominio adiabatico.
    4. Fuente de calor uniforme en dominio adiabatico.
    5. Frontera de Robin (conveccion) contra el modelo de capacidad agrupada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcplan.plan import plan_from_dict  # noqa: E402
from mcplan.thermal import build_model, solve  # noqa: E402


def barra_1d(nx: int, L: float = 1.0, k: float = 1.0, rho: float = 1.0, cp: float = 1.0) -> dict:
    dx = L / nx
    return {
        "caso": "barra1d",
        "geometria": {"x": [0.0, L], "y": [0.0, dx], "z": [0.0, dx], "dx": dx},
        "materiales": {"M1": {"k": k, "cp": cp, "rho": rho}},
        "vertidas": [
            {
                "id": 1,
                "inicio_h": 0.0,
                "z_min": 0.0,
                "z_max": dx,
                "material": "M1",
                "temperatura_colocacion_C": 20.0,
            }
        ],
        "hidratacion": {"elevacion_adibatica_C": 0.0, "tau_h": 1.0},
        "fronteras": [],
        "criterios": {"core_erosion": 0},
    }


def placa_2d(nx: int, ny: int, L: float = 1.0, k: float = 1.0, rho: float = 1.0, cp: float = 1.0) -> dict:
    dx = L / nx
    dy = L / ny
    return {
        "caso": "placa2d",
        "geometria": {"x": [0.0, L], "y": [0.0, L], "z": [0.0, dx], "dx": dx},
        "materiales": {"M1": {"k": k, "cp": cp, "rho": rho}},
        "vertidas": [
            {
                "id": 1,
                "inicio_h": 0.0,
                "z_min": 0.0,
                "z_max": dx,
                "material": "M1",
                "temperatura_colocacion_C": 20.0,
            }
        ],
        "hidratacion": {"elevacion_adibatica_C": 0.0, "tau_h": 1.0},
        "fronteras": [],
        "criterios": {"core_erosion": 0},
    }


def perfil_sinoidal(nx: int, ny: int, L: float, T0: float, A: float) -> np.ndarray:
    x = (np.arange(nx) + 0.5) * (L / nx)
    y = (np.arange(ny) + 0.5) * (L / ny)
    X, Y = np.meshgrid(x, y, indexing="ij")
    return T0 + A * np.sin(np.pi * X / L) * np.sin(np.pi * Y / L)


def test_1d_converge_a_solucion_analitica():
    L, T0, A = 1.0, 20.0, 10.0
    alpha = 1.0
    t_final_s = 0.05
    t_final_h = t_final_s / 3600.0
    errores = []

    for nx in (20, 40, 80):
        data = barra_1d(nx, L)
        data["fronteras"] = [
            {
                "name": "extremos",
                "direccion": "ejes",
                "ejes": [0],
                "signo": "ambos",
                "tipo": "dirichlet",
                "valor_dirichlet_C": T0,
            }
        ]
        model = build_model(plan_from_dict(data))
        x = (np.arange(nx) + 0.5) * (L / nx)
        inicial = T0 + A * np.sin(np.pi * x / L)
        result = solve(
            model,
            duracion_h=t_final_h,
            intervalo_salida_h=t_final_h,
            temperatura_inicial=np.broadcast_to(inicial[:, None, None], (nx, 1, 1)).ravel(),
        )
        exacto = T0 + A * np.sin(np.pi * x / L) * np.exp(-alpha * (np.pi / L) ** 2 * t_final_s)
        errores.append(float(np.max(np.abs(result.T_final[:, 0, 0] - exacto))))

    assert errores[-1] < 1e-2
    assert errores[0] > errores[-1]
    pendientes = np.log(np.array(errores[:-1]) / np.array(errores[1:])) / np.log(2.0)
    assert pendientes[-1] > 1.7


def test_2d_converge_a_solucion_analitica():
    L, T0, A = 1.0, 20.0, 10.0
    alpha = 1.0
    t_final_s = 0.05
    t_final_h = t_final_s / 3600.0

    data = placa_2d(40, 40, L)
    data["fronteras"] = [
        {
            "name": "bordes",
            "direccion": "ejes",
            "ejes": [0, 1],
            "signo": "ambos",
            "tipo": "dirichlet",
            "valor_dirichlet_C": T0,
        }
    ]
    model = build_model(plan_from_dict(data))
    inicial = perfil_sinoidal(40, 40, L, T0, A)
    result = solve(
        model,
        duracion_h=t_final_h,
        intervalo_salida_h=t_final_h,
        temperatura_inicial=inicial.ravel(),
    )
    x = (np.arange(40) + 0.5) * (L / 40)
    y = (np.arange(40) + 0.5) * (L / 40)
    X, Y = np.meshgrid(x, y, indexing="ij")
    exacto = T0 + A * np.sin(np.pi * X / L) * np.sin(np.pi * Y / L) * np.exp(
        -2.0 * alpha * (np.pi / L) ** 2 * t_final_s
    )
    error = float(np.max(np.abs(result.T_final[:, :, 0] - exacto)))
    assert error < 5e-2


def test_energia_se_conserva_en_dominio_adiabatico():
    data = barra_1d(20)
    model = build_model(plan_from_dict(data))
    result = solve(model, duracion_h=1e-4, intervalo_salida_h=1e-4)
    capacidad = model.rho_cp_flat * model.grid.cell_volume
    energia = float(np.nansum(capacidad * result.T_final.ravel()))
    inicial = float(np.nansum(capacidad * model.placement_T))
    assert abs(energia - inicial) / abs(inicial) < 1e-10


def test_fuente_uniforme_adiabatica():
    theta_inf, tau = 40.0, 1e-4
    duracion = 5e-5
    data = barra_1d(20)
    data["hidratacion"] = {"elevacion_adibatica_C": theta_inf, "tau_h": tau}
    model = build_model(plan_from_dict(data))
    result = solve(model, duracion_h=duracion, intervalo_salida_h=duracion)
    theta = theta_inf * (1.0 - np.exp(-duracion / tau))
    assert abs(result.T_mean[-1] - (20.0 + theta)) < 0.05


def test_frontera_de_robin_capacidad_agrupada():
    L, h, T0, Tinf = 0.01, 1.0, 30.0, 20.0
    rho_cp = 1.0
    data = barra_1d(4, L, k=1.0, rho=1.0, cp=1.0)
    data["fronteras"] = [
        {
            "name": "extremos",
            "direccion": "ejes",
            "ejes": [0],
            "signo": "ambos",
            "tipo": "convectiva",
            "h": h,
        }
    ]
    data["ambiente"] = {"media_C": Tinf}
    model = build_model(plan_from_dict(data))
    t_final_h = 0.02 / 3600.0
    result = solve(
        model,
        duracion_h=t_final_h,
        intervalo_salida_h=t_final_h,
        temperatura_inicial=np.full(model.grid.n_cells, T0),
    )
    tau_lumped_h = (rho_cp * L / (2.0 * h)) / 3600.0
    esperado = Tinf + (T0 - Tinf) * np.exp(-t_final_h / tau_lumped_h)
    assert abs(result.T_mean[-1] - esperado) < 0.1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
