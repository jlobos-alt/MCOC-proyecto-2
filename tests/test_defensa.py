"""Defensa (18/19-nov): S25 a 25 mm, colocacion progresiva, curvas medidas y problema de decision."""
from pathlib import Path

import numpy as np
import pytest

from mcplan.curvas import cargar_curvas, curva_provisoria_c1, desde_tabla
from mcplan.decision import Evaluacion, PlanVertidas, cronograma, duracion_D, mas_rapido_factible
from mcplan.plan import plan_from_dict
from mcplan.thermal import build_model, solve

RHO_CP = 2400.0 * 970.0
VOL = [147.6, 147.6, 214.2, 88.9, 38.5]


def _losa(fronteras, z=1.0, n=20, vertidas=None, hid=0.0):
    return plan_from_dict({
        "geometria": {"x": [0, 0.2], "y": [0, 0.2], "z": [0, z], "dx": 0.2, "dz": z / n},
        "materiales": {"M1": {"k": 2.0, "cp": 1000.0, "rho": 2000.0}},
        "vertidas": vertidas or [{"id": 1, "inicio_h": 0.0, "z_min": 0, "z_max": z, "material": "M1",
                                  "temperatura_colocacion_C": 40.0}],
        "hidratacion": {"elevacion_adibatica_C": hid, "tau_h": 30.0},
        "fronteras": fronteras,
    })


def test_s25_reproduce_el_perfil_permanente_exacto():
    # Base a 40 C, techo con Robin h = 10 hacia el aire (15 C por defecto), lados adiabaticos:
    # perfil lineal exacto. Celdas de 10 cm: 25 mm no coincide con el centro (50 mm).
    fr = [{"name": "lados", "direccion": "perimetro", "tipo": "adiabatica"},
          {"name": "techo", "direccion": "superficie", "tipo": "convectiva", "h": 10.0},
          {"name": "base", "direccion": "base", "tipo": "dirichlet", "valor_dirichlet_C": 40.0}]
    q = (40.0 - 15.0) / (1.0 / 2.0 + 1.0 / 10.0)             # W/m2, L = 1 m, k = 2
    T_sup = 15.0 + q / 10.0
    r = solve(build_model(_losa(fr, n=10)), duracion_h=2000.0, intervalo_salida_h=50.0)
    assert r.T_min_s25[-1] == pytest.approx(T_sup + q * 0.025 / 2.0, abs=1e-6)
    centro = solve(build_model(_losa(fr, n=10)), duracion_h=2000.0, intervalo_salida_h=50.0, profundidad_s25_m=0.05)
    assert centro.T_min_s25[-1] == pytest.approx(T_sup + q * 0.05 / 2.0, abs=1e-6)
    assert r.delta_T_s25[-1] == pytest.approx(r.T_max_global[-1] - r.T_min_s25[-1])


def test_s25_cuenta_el_techo_temporal_mientras_existe():
    fr = [{"name": "lados", "direccion": "perimetro", "tipo": "adiabatica"},
          {"name": "techo", "direccion": "superficie", "tipo": "convectiva", "h": 10.0},
          {"name": "base", "direccion": "base", "tipo": "adiabatica"}]
    vertidas = [{"id": 1, "inicio_h": 0.0, "z_min": 0, "z_max": 0.5, "material": "M1", "temperatura_colocacion_C": 40.0},
                {"id": 2, "inicio_h": 24.0, "z_min": 0.5, "z_max": 1.0, "material": "M1", "temperatura_colocacion_C": 40.0}]
    r = solve(build_model(_losa(fr, vertidas=vertidas)), duracion_h=30.0, intervalo_salida_h=1.0)
    # Hasta las 24 h el techo de la vertida 1 es superficie y se enfria; al llegar la vertida 2
    # deja de serlo y la nueva superficie parte a 40 C: S25 salta hacia arriba
    assert r.T_min_s25[23] < 35.0
    assert r.T_min_s25[25] > r.T_min_s25[23] + 3.0


def test_s25_no_mira_la_base_contra_el_suelo():
    fr = [{"name": "lados", "direccion": "perimetro", "tipo": "adiabatica"},
          {"name": "techo", "direccion": "superficie", "tipo": "adiabatica"},
          {"name": "base", "direccion": "base", "tipo": "convectiva", "h": 50.0}]
    m = build_model(_losa(fr, n=10))
    r = solve(m, duracion_h=48.0, intervalo_salida_h=1.0)
    # Solo los lados (adiabaticos) son superficie: S25 = el centro de celda mas frio, no la base extrapolada
    assert r.T_min_s25[-1] == pytest.approx(np.nanmin(r.T_final), abs=1e-9)


def test_colocacion_progresiva_activa_por_capas():
    plan = _losa([{"name": "a", "direccion": "perimetro", "tipo": "adiabatica"}],
                 vertidas=[{"id": 1, "inicio_h": 0.0, "z_min": 0, "z_max": 1.0, "material": "M1",
                            "temperatura_colocacion_C": 20.0, "duracion_h": 10.0}])
    m = build_model(plan)
    t = m.place_time.reshape(m.grid.shape)[0, 0, :]
    assert np.all(np.diff(t) > 0)                       # abajo primero
    assert t[0] == pytest.approx(0.25) and t[-1] == pytest.approx(9.75)


def test_cronograma_y_duracion():
    assert cronograma(PlanVertidas("5", 6.0, "ninguna"), [40.0, 80.0], 40.0) == [(0.0, 1.0), (7.0, 2.0)]
    assert duracion_D(PlanVertidas("unica", 0.0, "ninguna"), VOL, 40.0) == pytest.approx(sum(VOL) / 40.0)
    assert duracion_D(PlanVertidas("5", 0.0, "ninguna"), VOL, 40.0) == pytest.approx(sum(VOL) / 40.0)
    assert duracion_D(PlanVertidas("5", 24.0, "ninguna"), VOL, 40.0) == pytest.approx(sum(VOL) / 40.0 + 96.0)


def test_probabilidad_por_enumeracion_y_eleccion():
    def ev(D, fallas):
        e = Evaluacion(PlanVertidas("5", D, "ninguna"), D)
        e.corridas = [{"peso": 1 / 24, "MT": 75.0 if i < fallas else 60.0, "MDelta": 10.0} for i in range(24)]
        return e
    rapido_malo, rapido_bueno, lento = ev(10.0, 2), ev(12.0, 1), ev(50.0, 0)
    assert rapido_malo.P_f == pytest.approx(2 / 24) and not rapido_malo.cumple   # 8,33 % > 5 %
    assert rapido_bueno.P_f == pytest.approx(1 / 24) and rapido_bueno.cumple     # 4,17 %
    assert mas_rapido_factible([lento, rapido_malo, rapido_bueno]) is rapido_bueno
    assert mas_rapido_factible([rapido_malo]) is None


def test_curva_por_masa_se_convierte_y_conserva_el_calor():
    edad = np.array([0, 12, 24, 48, 96, 168.0])
    H = np.array([0, 100, 200, 280, 320, 330.0])            # J/g de cementante
    c = desde_tabla("M", edad, H, "Q_kg", RHO_CP, unidad_valor="J/g", cementante_kg_m3=400.0)
    assert c.theta_final_C == pytest.approx(330e3 * 400 / RHO_CP)
    # integral de q en el tiempo = calor total por m3
    a = np.linspace(0, 168, 20001)
    q = c.heat_rate(a, volumetric_heat_capacity=RHO_CP)
    assert np.trapezoid(q, a * 3600) == pytest.approx(330e3 * 400, rel=1e-3)


def test_curva_rechaza_temperatura_no_adiabatica_y_recorta_ruido():
    with pytest.raises(ValueError):
        desde_tabla("T", [0, 1], [20, 30], "T_ensayo", RHO_CP)
    c = desde_tabla("R", [0, 10, 20, 30], [0, 10, 9.5, 12], "dT_ad", RHO_CP)
    assert np.all(np.diff(c.theta_C) >= 0) and c.avisos


def test_cargar_curvas_desde_carpeta(tmp_path: Path):
    (tmp_path / "a.csv").write_text("edad_h,dT_C\n0,0\n24,20\n72,40\n", encoding="utf-8")
    (tmp_path / "curvas.yaml").write_text("curvas:\n  - {nombre: A, archivo: a.csv, tipo: dT_ad, unidad_edad: h}\n",
                                          encoding="utf-8")
    curvas = cargar_curvas(tmp_path, RHO_CP)
    assert [c.nombre for c in curvas] == ["A"] and curvas[0].theta(48.0) == pytest.approx(30.0)
    assert cargar_curvas(tmp_path / "no_existe", RHO_CP) == []


def test_curva_provisoria_es_c1():
    c = curva_provisoria_c1(RHO_CP)
    assert c.theta(30.0) == pytest.approx(45 * (1 - np.exp(-1)), abs=0.01)
    assert "PROVISORIA" in c.avisos[0]
