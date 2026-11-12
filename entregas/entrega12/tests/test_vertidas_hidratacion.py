"""E07: activacion de vertidas, caras hacia celdas vacias e hidratacion con madurez."""
import math
from pathlib import Path

import numpy as np
import pytest

from mcplan.bim import SolidoVertida
from mcplan.hydration import HydrationModel
from mcplan.plan import load_plan, plan_desde_solidos, plan_from_dict
from mcplan.thermal import build_model, solve
from mcplan.voxel import voxelizar

ROOT = Path(__file__).resolve().parents[1]
RHO_CP = 2400.0 * 970.0


def _caja(x0, x1, y0, y1, z0, z1, vertida_id=1, inicio_h=0.0, t_col=18.0):
    verts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return SolidoVertida(
        vertida_id=vertida_id, nombre=f"V{vertida_id}", guid="g",
        verts=np.array(verts, dtype=float), faces=np.array(faces),
        inicio_h=inicio_h, temperatura_colocacion_C=t_col, tipo_hormigon="M1",
        moldaje="-", aislacion="-", retiro_moldaje_h=72.0,
    )


def _plantilla(tipo="adiabatica", theta=0.0, madurez=False, h=10.0, T_aire=10.0):
    return plan_from_dict({
        "materiales": {"M1": {"k": 2.22, "cp": 970.0, "rho": 2400.0}},
        "hidratacion": {"elevacion_adibatica_C": theta, "tau_h": 30.0, "madurez": madurez},
        "ambiente": {"media_C": T_aire},
        "suelo": {"media_C": T_aire},
        "fronteras": [{"name": n, "direccion": n, "tipo": tipo, "h": h}
                      for n in ("perimetro", "superficie", "base")],
        "criterios": {"core_erosion": 0},
    })


def _modelo(plantilla, solidos, dx=0.5):
    return build_model(plan_desde_solidos(plantilla, solidos, dx), voxeles=voxelizar(solidos, dx=dx))


# -------------------------------------------------------- caras hacia celdas vacias
def test_celda_vacia_al_lado_es_frontera_no_aislacion():
    # Misma caja de 2 m: con la grilla justa y con la grilla el doble de ancha
    # (celdas vacias alrededor) la solucion debe ser identica.
    plantilla = _plantilla("convectiva")
    caja = _caja(0, 2, 0, 2, 0, 2, t_col=50.0)
    relleno = _caja(-1, -0.5, 0, 2, 0, 2, vertida_id=2, inicio_h=1e6, t_col=50.0)
    justa = solve(_modelo(plantilla, [caja]), duracion_h=48.0, intervalo_salida_h=48.0, dt_s=600.0)

    # La vertida 2 agranda la grilla y nunca se activa dentro de las 48 h
    voxeles = voxelizar([caja, relleno], dx=0.5)
    voxeles.vertida_id[voxeles.vertida_id == 2] = -1
    plan = plan_desde_solidos(plantilla, [caja], 0.5)
    ancha = solve(build_model(plan, voxeles=voxeles), duracion_h=48.0, intervalo_salida_h=48.0, dt_s=600.0)

    assert voxeles.grid.nx > 4
    assert ancha.T_mean[-1] == pytest.approx(justa.T_mean[-1], abs=1e-9)


def test_forma_en_l_intercambia_calor_por_toda_su_superficie():
    # L en planta con h bajo (Bi << 1): la temperatura es casi uniforme y vale la
    # capacidad agrupada, T - T_inf = (T0 - T_inf) exp(-h_ef A t / (rho cp V)).
    # A = 14 m2 solo se obtiene si tambien cuentan las caras hacia las celdas vacias.
    plantilla = _plantilla("convectiva", h=0.1, T_aire=50.0)
    a = _caja(0, 2, 0, 1, 0, 1, vertida_id=1)
    b = _caja(0, 1, 1, 2, 0, 1, vertida_id=2)
    r = solve(_modelo(plantilla, [a, b]), duracion_h=1000.0, intervalo_salida_h=1000.0, dt_s=1800.0)
    area, volumen = 14.0, 3.0
    h_ef = 1.0 / (1.0 / 0.1 + 0.25 / 2.22)          # conveccion + media celda en serie
    exacta = 50.0 + (18.0 - 50.0) * math.exp(-h_ef * area * 1000.0 * 3600.0 / (RHO_CP * volumen))
    assert r.T_mean[-1] == pytest.approx(exacta, abs=0.2)


# -------------------------------------------------------- activacion temporal
def _dos_vertidas(t1=10.0, t2=30.0, inicio2=5.0):
    return [_caja(0, 1, 0, 1, 0, 1, 1, 0.0, t1), _caja(0, 1, 0, 1, 1, 2, 2, inicio2, t2)]


def test_vertida_futura_no_existe_para_el_solver():
    r = solve(_modelo(_plantilla(), _dos_vertidas()), duracion_h=2.0, intervalo_salida_h=1.0, dt_s=300.0)
    # Antes de las 5 h solo esta la primera, a 10 C: nada aporta los 30 C de la segunda
    assert r.T_max_global[-1] == pytest.approx(10.0)
    assert not r.active_final[:, :, 2:].any()
    assert np.isnan(r.T_final[:, :, 2:]).all()


def test_vertida_nueva_entra_a_su_temperatura_de_colocacion():
    r = solve(_modelo(_plantilla(), _dos_vertidas()), duracion_h=5.0, intervalo_salida_h=1.0, dt_s=300.0)
    assert r.T_max_global[-1] == pytest.approx(30.0)     # recien colocada, aun sin mezclarse
    assert r.active_final.all()


def test_interfaz_conduce_y_la_energia_se_conserva():
    # Adiabatico sin hidratacion: tras mezclarse, promedio de las dos vertidas iguales.
    r = solve(_modelo(_plantilla(), _dos_vertidas()), duracion_h=2000.0, intervalo_salida_h=500.0, dt_s=1800.0)
    assert np.nanmean(r.T_final) == pytest.approx(20.0, abs=1e-9)
    assert np.nanmax(r.T_final) - np.nanmin(r.T_final) < 0.01


def test_cara_superior_expuesta_mientras_espera_la_siguiente():
    # Con conveccion, la vertida 1 pierde mas calor si la siguiente tarda en llegar.
    plantilla = _plantilla("convectiva", T_aire=10.0)
    tarde = solve(_modelo(plantilla, _dos_vertidas(t1=40.0, t2=40.0, inicio2=20.0)),
                  duracion_h=20.0, intervalo_salida_h=20.0, dt_s=300.0)
    pronto = solve(_modelo(plantilla, _dos_vertidas(t1=40.0, t2=40.0, inicio2=0.0)),
                   duracion_h=20.0, intervalo_salida_h=20.0, dt_s=300.0)
    assert np.nanmean(tarde.T_final[:, :, :2]) < np.nanmean(pronto.T_final[:, :, :2])


def test_cada_vertida_hidrata_desde_su_propia_hora():
    plantilla = _plantilla(theta=45.0)
    r = solve(_modelo(plantilla, _dos_vertidas(t1=18.0, t2=18.0, inicio2=30.0)),
              duracion_h=30.0, intervalo_salida_h=30.0, dt_s=120.0)
    # A las 30 h la vertida 2 parte de cero; la 1 ya subio 45*(1 - e^-1) antes
    assert np.nanmax(r.T_final) == pytest.approx(18.0 + 45.0 * (1.0 - math.exp(-1.0)), abs=0.2)
    assert np.nanmin(r.T_final) == pytest.approx(18.0, abs=0.3)


# -------------------------------------------------------- hidratacion
def test_unidades_de_qdot_y_relacion_con_la_curva_adiabatica():
    m = HydrationModel(theta_inf_1_C=45.0, tau_1_h=30.0)
    # En t = 0: qdot = rho*cp*(theta_inf/tau) = 2.328e6 J/(m3 K) * 1.5 K / 3600 s = 970 W/m3
    assert float(m.heat_rate(0.0, volumetric_heat_capacity=RHO_CP)) == pytest.approx(970.0)
    # Integrar qdot/(rho cp) en el tiempo recupera la curva adiabatica
    t = np.linspace(0.0, 72.0, 7201)
    q = m.heat_rate(t, volumetric_heat_capacity=RHO_CP)
    integral = np.sum(0.5 * (q[1:] + q[:-1]) * np.diff(t * 3600.0)) / RHO_CP
    assert integral == pytest.approx(float(m.theta(72.0)), rel=1e-5)


def test_factor_de_arrhenius():
    m = HydrationModel(activation_temperature_K=4000.0)
    assert float(m.maturity_factor(20.0)) == pytest.approx(1.0)
    assert float(m.maturity_factor(50.0)) == pytest.approx(math.exp(4000.0 * (1 / 293.15 - 1 / 323.15)))
    assert float(m.maturity_factor(5.0)) < 1.0


@pytest.mark.parametrize("madurez", [False, True])
def test_calor_total_no_depende_de_la_madurez(madurez):
    # Caja adiabatica a tiempo largo: la subida total es theta_inf, con o sin madurez.
    r = solve(_modelo(_plantilla(theta=45.0, madurez=madurez), [_caja(0, 1, 0, 1, 0, 1)]),
              duracion_h=800.0, intervalo_salida_h=100.0, dt_s=600.0)
    assert r.T_mean[-1] - 18.0 == pytest.approx(45.0, abs=1e-6)


@pytest.mark.parametrize("madurez", [False, True])
@pytest.mark.parametrize("dt_s", [1200.0, 3600.0, 21600.0])
def test_calor_total_no_depende_de_dt(madurez, dt_s):
    # dt grande frente a tau es estable en difusion, pero no debe inventar calor.
    r = solve(_modelo(_plantilla(theta=45.0, madurez=madurez), [_caja(0, 1, 0, 1, 0, 1)]),
              duracion_h=1200.0, intervalo_salida_h=1200.0, dt_s=dt_s)
    assert r.T_mean[-1] - 18.0 == pytest.approx(45.0, abs=1e-6)


def test_sin_madurez_la_subida_sigue_la_curva_adiabatica_exacta():
    r = solve(_modelo(_plantilla(theta=45.0), [_caja(0, 1, 0, 1, 0, 1)]),
              duracion_h=48.0, intervalo_salida_h=48.0, dt_s=7200.0)
    assert r.T_mean[-1] - 18.0 == pytest.approx(45.0 * (1.0 - math.exp(-48.0 / 30.0)), abs=1e-9)


def test_con_madurez_el_hormigon_caliente_libera_el_calor_antes():
    def subida(t_col, madurez=True):
        r = solve(_modelo(_plantilla(theta=45.0, madurez=madurez), [_caja(0, 1, 0, 1, 0, 1, t_col=t_col)]),
                  duracion_h=12.0, intervalo_salida_h=12.0, dt_s=120.0)
        return r.T_mean[-1] - t_col
    assert subida(40.0) > subida(10.0)
    assert subida(40.0, madurez=False) == pytest.approx(subida(10.0, madurez=False), abs=1e-9)


# -------------------------------------------------------- fundacion real
def test_plantilla_y_fundacion_real_se_arman_y_corren():
    pytest.importorskip("ifcopenshell")
    from mcplan.bim import extraer_solidos
    solidos = extraer_solidos(ROOT / "geometry" / "foundation.ifc")
    plantilla = load_plan(str(ROOT / "datos" / "fundacion_ifc.yaml"))
    vox = voxelizar(solidos, dx=0.5)
    modelo = build_model(plan_desde_solidos(plantilla, solidos, 0.5), voxeles=vox)
    r = solve(modelo, duracion_h=120.0, intervalo_salida_h=24.0, dt_s=3600.0)
    fino = solve(modelo, duracion_h=120.0, intervalo_salida_h=24.0, dt_s=600.0)
    # En cada corte diario entra una vertida mas; a las 120 h estan todas
    assert r.active_final.sum() == vox.mask.sum()
    assert np.isfinite(r.T_max_global).all()
    # Las caras hacia el vacio de la planta octagonal deben estar expuestas
    assert modelo.is_surface.sum() > 0
    # El peak debe ser fisico y no depender de dt. T_col + theta_inf = 63 C es solo una
    # referencia: una vertida joven puede superarla por poco con calor de la de abajo.
    assert np.nanmax(r.T_max_global) == pytest.approx(np.nanmax(fino.T_max_global), abs=0.5)
    assert 40.0 < np.nanmax(fino.T_max_global) < 66.0
