"""E08: la secuencia esta en los inputs, los campos se exportan y las vertidas se ocultan."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mcplan.bim import SolidoVertida, aplicar_cambios, revisar_secuencia
from mcplan.plan import plan_desde_solidos, plan_from_dict
from mcplan.thermal import build_model, solve
from mcplan.voxel import voxelizar

ROOT = Path(__file__).resolve().parents[1]


def _caja(z0, z1, vertida_id, inicio_h=0.0, t_col=18.0):
    verts = [(x, y, z) for z in (z0, z1) for y in (0.0, 1.0) for x in (0.0, 1.0)]
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return SolidoVertida(
        vertida_id=vertida_id, nombre=f"V{vertida_id}", guid="g", verts=np.array(verts, dtype=float),
        faces=np.array(faces), inicio_h=inicio_h, temperatura_colocacion_C=t_col, tipo_hormigon="M1",
        moldaje="-", aislacion="-", retiro_moldaje_h=72.0,
    )


def _plantilla():
    return plan_from_dict({
        "materiales": {"M1": {"k": 2.22, "cp": 970.0, "rho": 2400.0}},
        "hidratacion": {"elevacion_adibatica_C": 45.0, "tau_h": 30.0},
        "ambiente": {"media_C": 15.0},
        "suelo": {"media_C": 12.0},
        "fronteras": [{"name": n, "direccion": n, "tipo": "convectiva", "h": 10.0}
                      for n in ("perimetro", "superficie", "base")],
        "criterios": {"core_erosion": 0},
    })


def _resolver(solidos, **kwargs):
    modelo = build_model(plan_desde_solidos(_plantilla(), solidos, 0.25), voxeles=voxelizar(solidos, dx=0.25))
    return solve(modelo, **kwargs)


def _dos():
    return [_caja(0, 1, 1), _caja(1, 2, 2, inicio_h=6.0)]


# ---------------------------------------------------------------- cambios por comando
def test_aplicar_cambios_no_modifica_los_originales():
    base = _dos()
    nuevos = aplicar_cambios(base, inicio={2: 20.0}, tcol={1: 10.0})
    assert [s.inicio_h for s in nuevos] == [0.0, 20.0]
    assert nuevos[0].temperatura_colocacion_C == 10.0
    assert base[1].inicio_h == 6.0 and base[0].temperatura_colocacion_C == 18.0


def test_aplicar_intervalo_y_luego_una_hora_puntual():
    base = _dos() + [_caja(2, 3, 3)]
    assert [s.inicio_h for s in aplicar_cambios(base, intervalo_h=8.0)] == [0.0, 8.0, 16.0]
    assert [s.inicio_h for s in aplicar_cambios(base, intervalo_h=8.0, inicio={3: 30.0})] == [0.0, 8.0, 30.0]


@pytest.mark.parametrize("kwargs", [{"inicio": {9: 1.0}}, {"tcol": {9: 1.0}}])
def test_vertida_inexistente_se_rechaza(kwargs):
    with pytest.raises(KeyError, match="no existe"):
        aplicar_cambios(_dos(), **kwargs)


def test_inicio_negativo_se_rechaza():
    with pytest.raises(ValueError, match="negativ"):
        aplicar_cambios(_dos(), inicio={2: -1.0})


def test_avisa_si_una_vertida_va_antes_que_la_de_abajo():
    assert revisar_secuencia(_dos()) == []
    avisos = revisar_secuencia(aplicar_cambios(_dos(), inicio={1: 10.0}))
    assert len(avisos) == 1 and "no es construible" in avisos[0]


# ---------------------------------------------------------------- la secuencia manda
def test_cambiar_la_hora_cambia_cuando_entra_la_vertida():
    instantes = [3.0, 9.0]
    pronto = _resolver(_dos(), duracion_h=9.0, intervalo_salida_h=1.0, dt_s=600.0, instantes_campo_h=instantes)
    tarde = _resolver(aplicar_cambios(_dos(), inicio={2: 12.0}), duracion_h=9.0, intervalo_salida_h=1.0,
                      dt_s=600.0, instantes_campo_h=instantes)
    # A las 9 h, en el caso base ya entro la vertida 2; retrasada a las 12 h, todavia no
    assert np.isfinite(pronto.campos[9.0][:, :, 4:]).all()
    assert np.isnan(tarde.campos[9.0][:, :, 4:]).all()
    assert np.isnan(pronto.campos[3.0][:, :, 4:]).all()


def test_cambiar_la_temperatura_cambia_el_inicio_de_esa_vertida():
    r = _resolver(aplicar_cambios(_dos(), tcol={2: 5.0}), duracion_h=6.0, intervalo_salida_h=1.0, dt_s=300.0,
                  instantes_campo_h=[6.0])
    assert np.nanmin(r.campos[6.0][:, :, 4:]) == pytest.approx(5.0)


def test_cambiar_la_secuencia_cambia_el_resultado():
    base = _resolver(_dos(), duracion_h=48.0, intervalo_salida_h=1.0, dt_s=600.0)
    otra = _resolver(aplicar_cambios(_dos(), inicio={2: 24.0}), duracion_h=48.0, intervalo_salida_h=1.0, dt_s=600.0)
    assert abs(np.nanmax(base.T_max_global) - np.nanmax(otra.T_max_global)) > 0.5


def test_el_solver_no_conoce_nombres_ni_horas_de_vertidas():
    # El solver recibe la secuencia en el plan: en su codigo no hay vertidas con nombre ni horas de obra
    codigo = (ROOT / "src" / "mcplan" / "thermal.py").read_text(encoding="utf-8")
    for texto in ("Vertida_0", "InicioPlanificado", "foundation.ifc", "UANDES"):
        assert texto not in codigo


# ---------------------------------------------------------------- campos guardados
def test_campo_guardado_es_igual_a_terminar_la_corrida_ahi():
    con = _resolver(_dos(), duracion_h=24.0, intervalo_salida_h=1.0, dt_s=600.0, instantes_campo_h=[12.0])
    hasta = _resolver(_dos(), duracion_h=12.0, intervalo_salida_h=1.0, dt_s=600.0)
    np.testing.assert_array_equal(con.campos[12.0], hasta.T_final)


def test_sin_pedir_campos_no_se_guardan():
    assert _resolver(_dos(), duracion_h=2.0, intervalo_salida_h=1.0, dt_s=600.0).campos == {}


# ---------------------------------------------------------------- exportar y visor
@pytest.fixture
def resultado():
    pytest.importorskip("pyvista")
    solidos = _dos()
    vox = voxelizar(solidos, dx=0.25)
    r = solve(build_model(plan_desde_solidos(_plantilla(), solidos, 0.25), voxeles=vox),
              duracion_h=12.0, intervalo_salida_h=1.0, dt_s=600.0, instantes_campo_h=[3.0, 9.0, 12.0])
    return vox, r


def test_vti_conserva_vertida_y_temperatura(resultado, tmp_path):
    import pyvista as pv
    from mcplan.visualization import guardar_serie
    vox, r = resultado
    archivos = guardar_serie(tmp_path, vox.grid, vox.vertida_id, r.campos)
    assert len(archivos) == 3 and (tmp_path / "serie.pvd").exists()
    leida = pv.read(archivos[-1])
    assert leida.n_cells == vox.grid.n_cells
    assert leida.spacing == pytest.approx((vox.grid.dx, vox.grid.dy, vox.grid.dz))
    np.testing.assert_array_equal(np.asarray(leida.cell_data["vertida_id"]).reshape(vox.grid.shape, order="F"),
                                  vox.vertida_id)
    np.testing.assert_allclose(np.asarray(leida.cell_data["temperature"]).reshape(vox.grid.shape, order="F"),
                               r.campos[12.0])


def test_visor_oculta_muestra_y_respeta_la_activacion(resultado, tmp_path):
    from mcplan.visualization import VisorVertidas
    vox, r = resultado
    visor = VisorVertidas(vox.grid, vox.vertida_id, r.campos, off_screen=True, tamano=(400, 300))
    try:
        visor.fijar_tiempo(3.0)
        assert visor.vertidas_dibujadas() == [1]        # la vertida 2 entra a las 6 h
        visor.fijar_tiempo(9.0)
        assert visor.vertidas_dibujadas() == [1, 2]
        visor.alternar(2)
        assert visor.vertidas_dibujadas() == [1]
        assert not visor.piezas[(2, "entera")][1].GetVisibility()
        visor.alternar(2)
        assert visor.vertidas_dibujadas() == [1, 2]
        visor.fijar_corte(True)
        assert visor.piezas[(1, "media")][1].GetVisibility()
        assert not visor.piezas[(1, "entera")][1].GetVisibility()
        visor.alternar(1, False)
        visor.crear_controles()
        # Las casillas parten como esta el visor y siguen a las teclas
        assert visor._casillas[1].GetRepresentation().GetState() == 0
        assert visor._casillas["corte"].GetRepresentation().GetState() == 1
        visor.alternar(1)
        assert visor._casillas[1].GetRepresentation().GetState() == 1
        visor.captura(tmp_path / "v.png")
        assert (tmp_path / "v.png").stat().st_size > 1000
    finally:
        visor.cerrar()


# ---------------------------------------------------------------- de punta a punta
def _correr_sin_pyvista(*argumentos):
    pytest.importorskip("ifcopenshell")
    script = ROOT / "scripts" / "simular_fundacion_ifc.py"
    codigo = ("import runpy, sys; sys.modules['pyvista'] = None; "
              f"sys.argv = ['simular', *{list(argumentos)!r}]; "
              f"runpy.run_path({str(script)!r}, run_name='__main__')")
    return subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8")


def test_sin_pyvista_el_comando_termina_y_avisa(tmp_path):
    r = _correr_sin_pyvista("--dx", "1", "--sin-comparar", "--salida", str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "PyVista no esta instalado" in r.stdout
    assert (tmp_path / "corrida.json").exists() and (tmp_path / "series_fundacion.png").exists()
    assert not (tmp_path / "vista_3d.png").exists()


def test_visor_sin_pyvista_falla_antes_de_simular(tmp_path):
    r = _correr_sin_pyvista("--dx", "1", "--visor", "--salida", str(tmp_path))
    assert r.returncode == 2
    assert "--visor requiere PyVista" in r.stderr
    assert not (tmp_path / "corrida.json").exists()


def test_comando_completo_con_cambios(tmp_path):
    pytest.importorskip("ifcopenshell")
    pytest.importorskip("pyvista")
    salida = tmp_path / "caso"
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "simular_fundacion_ifc.py"), "--dx", "0.5", "--duracion-h", "48",
         "--inicio", "2=12", "--tcol", "3=10", "--salida", str(salida)],
        capture_output=True, text=True, encoding="utf-8", timeout=240,
    )
    assert p.returncode == 0, p.stderr
    datos = json.loads((salida / "corrida.json").read_text(encoding="utf-8"))
    vertidas = {v["id"]: v for v in datos["vertidas"]}
    assert vertidas[2]["inicio_h"] == 12.0 and vertidas[3]["T_colocacion_C"] == 10.0
    for archivo in ("series.csv", "series_fundacion.png", "activacion_cortes.png", "comparacion.png",
                    "vista_3d.png", "vti/serie.pvd"):
        assert (salida / archivo).exists(), archivo
    assert "Efecto del cambio" in p.stdout
    # El IFC no se toca: su secuencia sigue siendo la del caso base
    from mcplan.bim import extraer_solidos
    assert [s.inicio_h for s in extraer_solidos(ROOT / "geometry" / "foundation.ifc")] == [0, 6, 12, 18, 24]
