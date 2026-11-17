"""Tests E12: caso determinista de 14 dias con una sola curva de hidratacion.

Los tests caros (336 h) no se repiten: se verifica la fisica en una corrida corta
y se contrastan los resultados publicados en `results/e12/` con sus metadatos.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from mcplan import (
    assemble_timeline,
    build_model,
    dz_que_calza,
    extraer_solidos,
    latest_snapshot,
    load_plan,
    load_snapshot,
    plan_desde_solidos,
    solve,
    verify,
    voxelizar,
)
from mcplan.hydration import HydrationModel

ROOT = Path(__file__).resolve().parents[1]
DATOS = ROOT / "datos"
FORECAST = DATOS / "forecast"
RESULTS = ROOT / "results" / "e12"
INICIO = "2026-11-27T04:00:00"


@pytest.fixture(scope="module")
def plantilla():
    return load_plan(str(DATOS / "fundacion_e12.yaml"))


@pytest.fixture(scope="module")
def resumen():
    return json.loads((RESULTS / "resumen_e12.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def filas():
    with open(RESULTS / "series_e12.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Curva de hidratacion: una sola, declarada
# ---------------------------------------------------------------------------


def test_una_sola_curva_de_hidratacion(plantilla):
    h = plantilla.hidratacion
    assert h.elevacion_adibatica_C == pytest.approx(45.0)
    assert h.tau_h == pytest.approx(30.0)
    assert h.elevacion_adibatica_2_C == pytest.approx(0.0)  # sin segunda rama
    assert h.madurez is True
    assert h.energia_activacion_K == pytest.approx(4000.0)


def test_la_curva_c1_coincide_con_la_formula(plantilla):
    h = HydrationModel(
        theta_inf_1_C=plantilla.hidratacion.elevacion_adibatica_C,
        tau_1_h=plantilla.hidratacion.tau_h,
        activation_temperature_K=plantilla.hidratacion.energia_activacion_K,
    )
    edad = np.array([24.0, 72.0, 168.0, 336.0])
    esperado = 45.0 * (1.0 - np.exp(-edad / 30.0))
    assert np.allclose(h.theta(edad), esperado)
    assert h.theta(24.0) == pytest.approx(24.78, abs=0.01)
    assert h.theta(168.0) == pytest.approx(44.83, abs=0.01)
    assert h.theta(1e6) == pytest.approx(45.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Clima: horizonte declarado y trazable
# ---------------------------------------------------------------------------


def test_el_clima_es_climatologia_y_cubre_las_336_h():
    assert len(verify(FORECAST)) == 2
    meta_f = latest_snapshot(FORECAST, "open-meteo-forecast")
    meta_a = latest_snapshot(FORECAST, "open-meteo-archive")
    forecast = load_snapshot(FORECAST, meta_f.snapshot_id)[0]
    archivo = load_snapshot(FORECAST, meta_a.snapshot_id)[0]
    timeline = assemble_timeline(
        INICIO, hours=np.arange(0.0, 336.0 + 1e-9, 1.0).tolist(),
        forecast=forecast, climatology=archivo,
    )
    assert len(timeline) == 337
    assert dict(timeline.sources) == {"climatology": 337}
    assert "missing" not in timeline.sources
    # El forecast no llega a la primera vertida: por eso no aporta horas.
    assert meta_f.last_time < INICIO[:10]
    assert all(np.isfinite(p.temperature_C) for p in timeline.points)


def test_el_plan_de_vertidas_sale_del_ifc(plantilla):
    solidos = extraer_solidos(ROOT / "geometry" / "foundation.ifc")
    plan = plan_desde_solidos(plantilla, solidos, 0.5)
    assert [v.id for v in plan.vertidas] == [1, 2, 3, 4, 5]
    assert [v.inicio_h for v in plan.vertidas] == [0.0, 6.0, 12.0, 18.0, 24.0]
    assert all(v.temperatura_colocacion_C == pytest.approx(18.0) for v in plan.vertidas)
    assert all(v.retiro_moldaje_h == pytest.approx(72.0) for v in plan.vertidas)
    assert all(v.moldaje == "Madera" and v.aislacion == "Ninguna" for v in plan.vertidas)
    # V3 es la vertida gruesa (1,10 m) y la que alcanza la temperatura maxima.
    v3 = next(v for v in plan.vertidas if v.id == 3)
    assert v3.z_max - v3.z_min == pytest.approx(1.10, abs=1e-6)


# ---------------------------------------------------------------------------
# Resultados publicados: 70 C se cumple, 20 C no
# ---------------------------------------------------------------------------


def test_el_criterio_de_70_cumple_y_el_de_20_no(resumen):
    r = resumen["resultado"]
    assert r["T_max_C"] == pytest.approx(63.98, abs=0.05)
    assert r["T_max_h"] == pytest.approx(54.0)
    assert r["cumple_T_max"] is True
    assert r["delta_T_max_C"] == pytest.approx(42.06, abs=0.05)
    assert r["delta_T_h"] == pytest.approx(148.0)
    assert r["cumple_delta_T"] is False
    assert resumen["excedencia_delta_T"]["horas_sobre_20"] == 313


def test_los_maximos_tienen_instante_y_ubicacion(resumen):
    loc = resumen["localizacion"]
    x = loc["T_max"]
    d = loc["delta_T_max"]
    assert x["vertida"] == 3
    assert abs(x["x_m"]) < 1.0 and abs(x["y_m"]) < 1.0  # eje del pedestal
    assert 1.0 < x["z_m"] < 2.2  # dentro de V3
    assert d["nucleo"]["T_C"] - d["superficie"]["T_C"] == pytest.approx(d["delta_T_C"], abs=0.01)
    assert d["nucleo"]["T_C"] > d["superficie"]["T_C"]
    # La superficie mas fria esta en el perimetro, no en el eje.
    assert max(abs(d["superficie"]["x_m"]), abs(d["superficie"]["y_m"])) > 5.0
    assert d["time_local"] > x["time_local"]


def test_la_serie_csv_conserva_la_definicion_de_delta_T(filas):
    assert len(filas) == 337
    assert {f["source"] for f in filas} == {"climatology"}
    for f in filas:
        if f["delta_T_C"] not in ("", "nan"):
            esperado = float(f["T_max_nucleo_C"]) - float(f["T_min_superficie_C"])
            assert float(f["delta_T_C"]) == pytest.approx(esperado, abs=2e-3)
    assert float(filas[-1]["delta_T_C"]) < float(filas[148]["delta_T_C"])


def test_las_figuras_y_la_serie_3d_existen():
    for nombre in ("e12_clima.png", "e12_curva_c1.png", "e12_criterios.png",
                   "e12_nucleo_superficie.png", "e12_3d_tmax.png", "e12_3d_dtmax.png",
                   "e12_3d_zonas.png", "condiciones_borde.csv", "plan_vertidas.csv"):
        assert (RESULTS / nombre).stat().st_size > 100
    pvd = RESULTS / "vti" / "serie.pvd"
    if not pvd.exists():
        pytest.skip("los .vti no se versionan: correr scripts/e12_determinista.py")
    vti = sorted((RESULTS / "vti").glob("*.vti"))
    assert len(vti) >= 17
    assert all(a.name in pvd.read_text(encoding="utf-8") for a in vti)


# ---------------------------------------------------------------------------
# Reproducibilidad: misma entrada, misma salida (bit a bit)
# ---------------------------------------------------------------------------


def test_dos_corridas_del_mismo_caso_son_identicas(plantilla):
    solidos = extraer_solidos(ROOT / "geometry" / "foundation.ifc")
    dx = 1.0
    dz = dz_que_calza(solidos, dx)
    vox = voxelizar(solidos, dx=dx, dz=dz)
    plan = plan_desde_solidos(plantilla, solidos, dx)
    plan.simulacion.duracion_h = 24.0
    modelo = build_model(plan, voxeles=vox)
    a = solve(modelo, duracion_h=24.0, intervalo_salida_h=1.0, guardar_campo=False)
    b = solve(modelo, duracion_h=24.0, intervalo_salida_h=1.0, guardar_campo=False)
    assert np.array_equal(a.T_max_global, b.T_max_global)
    assert np.array_equal(a.T_final, b.T_final, equal_nan=True)
    assert a.dt_s == b.dt_s
