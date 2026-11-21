"""E13: muestreo reproducible, dependencias, estados limite y estimador Monte Carlo."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from mcplan.incertidumbre import (
    EPISTEMICA,
    POR_NOMBRE,
    REPETICIONES,
    VARIABLES,
    cota_cero_fallas,
    estados_limite,
    estimar,
    muestra_nominal,
    muestrear,
    n_requerido,
    spearman,
    wilson,
)

ROOT = Path(__file__).resolve().parents[1]


def test_la_misma_muestra_sale_igual_en_cualquier_orden():
    # Necesario para repartir el Monte Carlo en un arreglo de Slurm
    adelante = [muestrear(i, 7) for i in range(5)]
    atras = [muestrear(i, 7) for i in reversed(range(5))][::-1]
    assert adelante == atras
    assert muestrear(3, 7) != muestrear(4, 7)
    assert muestrear(3, 7) != muestrear(3, 8)


def test_conjunto_a_deja_las_epistemicas_en_el_nominal():
    for i in range(20):
        m = muestrear(i, 1, epistemicas=False)
        for v in VARIABLES:
            if v.naturaleza == EPISTEMICA:
                assert m[v.nombre] == v.nominal


def test_marginales_respetan_sus_rangos_y_su_centro():
    muestras = [muestrear(i, 11) for i in range(3000)]
    for v in VARIABLES:
        valores = np.array([x for m in muestras for x in (m[v.nombre] if v.nombre in REPETICIONES else [m[v.nombre]])])
        if v.distribucion == "uniforme":
            assert valores.min() >= v.a and valores.max() <= v.b
            assert valores.mean() == pytest.approx((v.a + v.b) / 2, abs=0.03 * (v.b - v.a))
        elif v.distribucion == "normal_trunc":
            assert valores.min() >= v.minimo and valores.max() <= v.maximo
            assert valores.mean() == pytest.approx(v.a, abs=0.1 * v.b)
        else:
            assert np.median(valores) == pytest.approx(v.a, rel=0.05)
            assert valores.min() > 0


def test_las_dependencias_se_reproducen():
    muestras = [muestrear(i, 3) for i in range(4000)]
    x = [m["dT_aire"] for m in muestras]
    # rho gaussiano 0,6 -> Spearman 6/pi asin(0,3) = 0,58
    assert spearman(x, [m["dT_colocacion"] for m in muestras]) == pytest.approx(6 / math.pi * math.asin(0.3), abs=0.05)
    assert abs(spearman(x, [m["theta_inf_C"] for m in muestras])) < 0.05


def test_la_muestra_nominal_es_el_caso_de_e12():
    m = muestra_nominal()
    for v in VARIABLES:
        esperado = [v.nominal] * REPETICIONES[v.nombre] if v.nombre in REPETICIONES else v.nominal
        assert m[v.nombre] == esperado
    assert POR_NOMBRE["theta_inf_C"].nominal == 45.0


def test_estados_limite_y_sistema_en_serie():
    g = estados_limite(np.array([60.0, 75.0, 65.0]), np.array([25.0, 10.0, 15.0]))
    assert g["g_T"].tolist() == [10.0, -5.0, 5.0]
    assert g["g_dT"].tolist() == [-5.0, 10.0, 5.0]
    assert g["g_sistema"].tolist() == [-5.0, -5.0, 5.0]


def test_estimador_y_su_intervalo():
    e = estimar(np.array([-1.0] * 10 + [1.0] * 90))
    assert e["p_hat"] == 0.1
    assert e["error_estandar"] == pytest.approx(math.sqrt(0.1 * 0.9 / 100))
    lo, hi = e["IC95_wilson"]
    assert lo < 0.1 < hi
    assert e["n_para_cov_10pct"] == pytest.approx(900.0)


def test_cero_fallas_no_demuestra_una_probabilidad_chica():
    e = estimar(np.ones(1000))
    assert e["p_hat"] == 0.0
    assert e["cota_superior_cero_fallas"] == pytest.approx(1 - 0.05 ** (1 / 1000))
    assert e["cota_superior_cero_fallas"] == pytest.approx(3 / 1000, rel=0.01)   # regla del 3
    assert wilson(0, 40)[1] == pytest.approx(0.0876, abs=1e-3)
    # Para demostrar p <= 1e-4 con 0 fallas hacen falta ~30 000 muestras
    assert cota_cero_fallas(30_000) < 1e-4 < cota_cero_fallas(29_000)
    assert n_requerido(1e-3, 0.1) == pytest.approx(99_900)


def _script():
    pytest.importorskip("ifcopenshell")
    spec = importlib.util.spec_from_file_location("e13", ROOT / "scripts" / "e13_incertidumbre.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_monte_carlo_envuelve_el_caso_de_e12():
    e13 = _script()
    ctx = e13.preparar(0.5)
    r = e13.evaluar(muestra_nominal(), ctx)
    assert r["T_max"] == pytest.approx(e13.E12_T_MAX, abs=0.01)
    assert r["dT_max"] == pytest.approx(e13.E12_DT_MAX, abs=0.01)


def test_mas_calor_de_hidratacion_sube_t_max():
    e13 = _script()
    ctx = e13.preparar(1.0)
    m = muestra_nominal()
    base = e13.evaluar(m, ctx)["T_max"]
    m["theta_inf_C"] = 50.0
    assert e13.evaluar(m, ctx)["T_max"] > base + 3.0


def test_el_atraso_de_las_vertidas_se_acumula():
    e13 = _script()
    ctx = e13.preparar(1.0)
    m = muestra_nominal()
    m["retraso_vertida_h"] = [1.0, 2.0, 0.0, 3.0]
    inicios = sorted(v.inicio_h for v in e13.caso(m, ctx).vertidas)
    assert inicios == [0.0, 7.0, 15.0, 21.0, 30.0]
