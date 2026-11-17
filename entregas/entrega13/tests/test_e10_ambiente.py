"""Tests E10: ambiente real, suelo, moldaje por vertida y snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from mcplan import (
    MeteoFrame,
    SoilSpec,
    aplicar_ambiente,
    assemble_timeline,
    build_model,
    condiciones_de_timeline,
    formwork_resistance,
    normalize_payload,
    plan_from_dict,
    save_snapshot,
    load_snapshot,
    latest_snapshot,
    verify,
    wind_convection_coefficient,
    sol_air_temperature,
    surface_heat_fluxes,
)
from mcplan.plan import load_plan


ROOT = Path(__file__).resolve().parents[1]


def _frame(times, temps, fuente="test", crudo=b'{"hourly":{}}', viento=1.0, solar=0.0):
    n = len(times)
    return MeteoFrame(
        source=fuente,
        issued_at="2026-11-11T12:00:00+00:00",
        fetched_at="2026-11-11T12:00:00+00:00",
        latitude=-35.6,
        longitude=-72.5,
        timezone="America/Santiago",
        model="test",
        times=list(times),
        temperature_C=list(temps),
        humidity_pct=[80.0] * n,
        wind_ms=[viento] * n,
        solar_W_m2=[solar] * n,
        cloud_pct=[50.0] * n,
        precip_mm=[0.0] * n,
        raw=crudo,
    )


# ---------------------------------------------------------------------------
# Ambiente: viento, sol-aire y doble conteo
# ---------------------------------------------------------------------------


def test_viento_aumenta_el_coeficiente_convectivo():
    assert wind_convection_coefficient(0.0) == pytest.approx(5.7)
    assert wind_convection_coefficient(10.0) > wind_convection_coefficient(2.0)


def test_sol_aire_suma_radiacion_sin_tocar_la_aire():
    sin_sol = sol_air_temperature(15.0, 0.0, 20.0, absorptivity=0.6)
    con_sol = sol_air_temperature(15.0, 800.0, 20.0, absorptivity=0.6)
    assert sin_sol == pytest.approx(15.0)
    assert con_sol == pytest.approx(15.0 + 0.6 * 800.0 / 20.0)


def test_balance_de_flujos_es_consistente():
    flujos = surface_heat_fluxes(30.0, 20.0, 600.0, 4.0, cloud_cover=0.3)
    assert flujos["q_neto"] == pytest.approx(
        flujos["q_conv"] + flujos["q_solar"] + flujos["q_lw"]
    )
    assert flujos["q_solar"] > 0.0
    assert flujos["q_conv"] < 0.0  # superficie mas caliente que el aire: pierde calor


def test_formwork_resistance_es_espesor_sobre_k():
    assert formwork_resistance(0.019, 0.12) == pytest.approx(0.019 / 0.12)
    with pytest.raises(ValueError):
        formwork_resistance(0.02, 0.0)


# ---------------------------------------------------------------------------
# Suelo
# ---------------------------------------------------------------------------


def test_suelo_onda_anual_amortiguada_y_coherente():
    suelo = SoilSpec(depth_m=1.0)
    assert suelo.penetration_depth > 1.0
    assert 0.0 < suelo.damping < 1.0
    assert suelo.phase_lag_h > 0.0
    assert suelo.resistance == pytest.approx(1.0 / 1.389)
    for t in (0.0, 100.0, 2000.0, 5000.0):
        assert suelo.temperature(t) == pytest.approx(suelo.series()(t), abs=1e-9)


def test_yaml_e10_declara_catalogos_y_suelo():
    plan = load_plan(str(ROOT / "datos" / "fundacion_e10.yaml"))
    assert plan.moldajes["Madera"].resistencia == pytest.approx(0.019 / 0.12)
    assert plan.aislaciones["EPS_50mm"].resistencia == pytest.approx(0.05 / 0.035)
    assert plan.suelo.amplitude_C > 0.0
    assert plan.suelo.penetration_depth > 1.0


# ---------------------------------------------------------------------------
# Snapshots inmutables
# ---------------------------------------------------------------------------


def test_snapshot_roundtrip_hash_e_inmutabilidad(tmp_path):
    tiempos = ["2026-11-11T00:00", "2026-11-11T01:00", "2026-11-11T02:00"]
    frame = _frame(tiempos, [10.0, 11.0, 12.0], crudo=b'{"ok":true}')
    meta = save_snapshot(frame, tmp_path, snapshot_id="prueba")
    assert meta.n_hours == 3
    assert verify(tmp_path) == ["prueba"]

    releido, meta2 = load_snapshot(tmp_path, "prueba")
    assert meta2.sha256_raw == meta.sha256_raw
    assert releido.temperature_C == pytest.approx([10.0, 11.0, 12.0])
    assert latest_snapshot(tmp_path).snapshot_id == "prueba"

    # Mismo contenido: idempotente, no crea otro snapshot.
    assert save_snapshot(frame, tmp_path, snapshot_id="prueba").sha256_csv == meta.sha256_csv
    with pytest.raises(FileExistsError):
        save_snapshot(_frame(tiempos, [99.0, 99.0, 99.0]), tmp_path, snapshot_id="prueba")


def test_verify_detecta_un_snapshot_alterado(tmp_path):
    frame = _frame(["2026-11-11T00:00", "2026-11-11T01:00"], [10.0, 11.0])
    save_snapshot(frame, tmp_path, snapshot_id="alterado")
    ruta = tmp_path / "alterado" / "normalizado.csv"
    ruta.write_text(ruta.read_text(encoding="utf-8") + "2026-11-11T02:00,99\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash distinto"):
        verify(tmp_path)


# ---------------------------------------------------------------------------
# Loader meteorologico y ensamblado forecast/climatologia
# ---------------------------------------------------------------------------


def _payload(inicio: str, horas: int, temperatura: float, viento: float = 2.0):
    base = datetime.fromisoformat(inicio)
    tiempos = [(base + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(horas)]
    relleno = [temperatura] * horas
    return {
        "latitude": -35.6,
        "longitude": -72.5,
        "timezone": "America/Santiago",
        "hourly": {
            "time": tiempos,
            "temperature_2m": relleno,
            "relative_humidity_2m": [80.0] * horas,
            "wind_speed_10m": [viento] * horas,
            "shortwave_radiation": [500.0] * horas,
            "cloud_cover": [20.0] * horas,
            "precipitation": [0.0] * horas,
        },
    }


def test_normalize_payload_arma_columnas_normalizadas():
    frame = normalize_payload(_payload("2026-11-11T00:00", 5, 12.0), source="test")
    assert len(frame) == 5
    assert frame.temperature_C == pytest.approx([12.0] * 5)
    assert frame.units["wind_ms"] == "m/s"
    assert set(frame.rows()[0]) >= {"time", "temperature_2m", "wind_speed_10m"}


def test_timeline_usa_forecast_y_luego_climatologia():
    forecast = _frame(
        [(datetime(2025, 11, 12) + timedelta(hours=i)).isoformat() for i in range(48)],
        [10.0] * 48,
        fuente="forecast",
    )
    clima = _frame(
        [(datetime(2025, 11, 12) + timedelta(hours=i)).isoformat() for i in range(28 * 24)],
        [20.0] * (28 * 24),
        fuente="climatology",
    )
    timeline = assemble_timeline("2025-11-12T00:00:00", [0, 24, 40, 72, 200], forecast, clima)
    fuentes = [p.source for p in timeline.points]
    assert fuentes[:3] == ["forecast", "forecast", "forecast"]
    assert fuentes[3:] == ["climatology", "climatology"]
    assert timeline.points[0].temperature_C == pytest.approx(10.0)
    assert timeline.points[-1].temperature_C == pytest.approx(20.0)
    assert timeline.sources == {"forecast": 3, "climatology": 2}


def test_timeline_marca_missing_si_no_hay_cobertura():
    forecast = _frame(["2026-11-11T00:00", "2026-11-11T01:00"], [10.0, 10.0])
    timeline = assemble_timeline("2026-11-27T04:00:00", [0, 24], forecast, None)
    assert timeline.sources == {"missing": 2}


def test_condiciones_de_timeline_entrega_h_y_t_sol_aire():
    forecast = _frame(
        ["2026-11-27T04:00", "2026-11-27T05:00"],
        [15.0, 15.0],
        viento=5.0,
        solar=700.0,
    )
    timeline = assemble_timeline("2026-11-27T04:00:00", [0, 1], forecast, None)
    h_fn, t_fn = condiciones_de_timeline(timeline)
    assert h_fn(0.0) > wind_convection_coefficient(5.0)  # incluye la parte radiativa
    assert t_fn(0.0) > 15.0


# ---------------------------------------------------------------------------
# Fronteras: h(t) y moldaje por vertida
# ---------------------------------------------------------------------------


def _plan_minimo(moldaje="Madera", retiro=2.0, aislacion="Ninguna"):
    return plan_from_dict(
        {
            "caso": "mini",
            "geometria": {"x": (0.0, 4.0), "y": (0.0, 4.0), "z": (0.0, 2.0), "dx": 1.0},
            "materiales": {"M1": {"k": 2.22, "cp": 970.0, "rho": 2400.0}},
            "moldajes": {"Madera": {"espesor_m": 0.019, "k": 0.12},
                         "Ninguno": {"espesor_m": 0.0, "k": 1.0}},
            "aislaciones": {"Ninguna": {"espesor_m": 0.0, "k": 1.0},
                            "EPS_50mm": {"espesor_m": 0.05, "k": 0.035}},
            "vertidas": [
                {
                    "id": 1,
                    "inicio_h": 0.0,
                    "z_min": 0.0,
                    "z_max": 1.0,
                    "material": "M1",
                    "temperatura_colocacion_C": 20.0,
                    "moldaje": moldaje,
                    "aislacion": aislacion,
                    "retiro_moldaje_h": retiro,
                }
            ],
            "hidratacion": {"elevacion_adibatica_C": 0.0, "tau_h": 30.0, "madurez": False},
            "ambiente": {"media_C": 0.0, "amplitud_C": 0.0},
            "suelo": {"media_C": 0.0, "amplitud_C": 0.0},
            "fronteras": [
                {"name": "perimetro", "direccion": "perimetro", "tipo": "convectiva", "h": 12.0},
                {"name": "superficie", "direccion": "superficie", "tipo": "convectiva", "h": 12.0},
                {
                    "name": "base",
                    "direccion": "base",
                    "tipo": "convectiva",
                    "h": 1000.0,
                    "capas": [{"nombre": "suelo", "espesor_m": 1.0, "k": 1.389}],
                },
            ],
            "criterios": {"T_max_C": 70.0, "delta_T_max_C": 20.0},
            "simulacion": {"duracion_h": 10.0, "intervalo_salida_h": 1.0},
        }
    )


def test_modelo_guarda_moldaje_y_retiro_por_vertida():
    plan = _plan_minimo()
    modelo = build_model(plan)
    assert modelo.r_moldaje_flat.max() == pytest.approx(0.019 / 0.12)
    activos = modelo.formwork_end_flat[modelo.mask]
    assert np.allclose(activos, 2.0)


def test_h_series_y_far_field_se_inyectan_en_el_grupo():
    plan = _plan_minimo()
    plan.fronteras[0].h_series = lambda t: 5.0 + 2.0 * t
    plan.fronteras[0].far_field_series = lambda t: 20.0 + t
    modelo = build_model(plan)
    grupo = modelo.groups["perimetro"]
    assert grupo.convective_resistance(5.0) == pytest.approx(1.0 / 15.0)
    assert grupo.far_field_at(3.0) == pytest.approx(23.0)


def test_aplicar_ambiente_no_toca_la_base():
    plan = _plan_minimo()
    frame = _frame(
        ["2026-11-27T04:00", "2026-11-27T05:00"],
        [15.0, 16.0],
        viento=3.0,
        solar=400.0,
    )
    timeline = assemble_timeline("2026-11-27T04:00:00", [0, 1], frame, None)
    aplicar_ambiente(plan, timeline)
    perimetro = next(f for f in plan.fronteras if f.direccion == "perimetro")
    base = next(f for f in plan.fronteras if f.direccion == "base")
    assert perimetro.h_series is not None
    assert perimetro.far_field_series is not None
    assert base.h_series is None
    assert len(plan.ambiente.datos) == 2


def _temperatura_final(plan) -> float:
    modelo = build_model(plan)
    resultado = solve_corto(modelo)
    return float(resultado.T_mean[-1])


def solve_corto(modelo):
    from mcplan import solve

    return solve(modelo, duracion_h=24.0, intervalo_salida_h=24.0, dt_s=600.0, guardar_campo=False)


def test_el_moldaje_reduce_la_perdida_de_calor():
    con_moldaje = _temperatura_final(_plan_minimo(moldaje="Madera", retiro=None))
    sin_moldaje = _temperatura_final(_plan_minimo(moldaje="Ninguno", retiro=None))
    assert con_moldaje > sin_moldaje + 0.5


def test_al_desmoldar_vuelve_la_perdida_sin_moldaje():
    desmoldado = _temperatura_final(_plan_minimo(moldaje="Madera", retiro=0.0))
    sin_moldaje = _temperatura_final(_plan_minimo(moldaje="Ninguno", retiro=None))
    assert desmoldado == pytest.approx(sin_moldaje, abs=1e-6)


def test_aislacion_suma_resistencia_al_moldaje():
    con_aislacion = _temperatura_final(_plan_minimo(moldaje="Madera", retiro=None, aislacion="EPS_50mm"))
    solo_madera = _temperatura_final(_plan_minimo(moldaje="Madera", retiro=None))
    assert con_aislacion > solo_madera
