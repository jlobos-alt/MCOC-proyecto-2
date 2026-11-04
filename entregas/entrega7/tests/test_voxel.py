"""E07: del IFC a la grilla. Geometria, voxelizador, volumen, superficie y vertidas."""
from pathlib import Path

import numpy as np
import pytest

from mcplan.bim import SolidoVertida, horas_desde_primera, volumen_malla
from mcplan.voxel import FUERA, area_expuesta, area_exterior, centros_dentro, dz_que_calza, voxelizar

ROOT = Path(__file__).resolve().parents[1]
IFC = ROOT / "geometry" / "foundation.ifc"


def _solido(verts, faces, vertida_id=1):
    return SolidoVertida(
        vertida_id=vertida_id, nombre=f"S{vertida_id}", guid="g",
        verts=np.array(verts, dtype=float), faces=np.array(faces, dtype=int),
        inicio_h=0.0, temperatura_colocacion_C=18.0, tipo_hormigon="M1",
        moldaje="-", aislacion="-", retiro_moldaje_h=72.0,
    )


def _caja(x0, x1, y0, y1, z0, z1, vertida_id=1):
    verts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return _solido(verts, faces, vertida_id)


def _piramide(a, h):
    """Base cuadrada de lado 2a en z = 0 y apice en (0, 0, h)."""
    verts = [(-a, -a, 0), (a, -a, 0), (a, a, 0), (-a, a, 0), (0, 0, h)]
    faces = [(0, 2, 1), (0, 3, 2), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return _solido(verts, faces)


# ---------------------------------------------------------------- regla de pertenencia
def test_caja_alineada_da_el_volumen_exacto():
    vox = voxelizar([_caja(0, 2, 0, 1, 0, 1.5)], dx=0.25)
    assert vox.volumen_voxel() == pytest.approx(3.0)
    assert vox.error_volumen() == pytest.approx(0.0, abs=1e-12)


def test_pertenencia_coincide_con_la_formula_de_la_piramide():
    solido = _piramide(a=2.0, h=3.0)
    vox = voxelizar([solido], dx=0.17)
    X, Y, Z = np.meshgrid(*vox.grid.centers(), indexing="ij")
    exacta = np.maximum(np.abs(X), np.abs(Y)) < 2.0 * (1.0 - Z / 3.0)
    assert (vox.mask != exacta).sum() == 0


def test_malla_abierta_se_rechaza():
    solido = _caja(0, 1, 0, 1, 0, 1)
    with pytest.raises(ValueError, match="malla abierta"):
        # Sin las dos caras de la tapa superior, cada columna cruza una sola vez
        centros_dentro(solido.verts, np.delete(solido.faces, [2, 3], axis=0),
                       voxelizar([solido], dx=0.25).grid)


# ---------------------------------------------------------------- interfaz entre vertidas
def test_centro_justo_en_la_interfaz_pertenece_solo_a_la_de_arriba():
    # Con dz = 0.5 hay centros en z = 0.25, 0.75, ...; la interfaz cae en z = 0.75
    abajo = _caja(0, 1, 0, 1, 0, 0.75, vertida_id=1)
    arriba = _caja(0, 1, 0, 1, 0.75, 1.5, vertida_id=2)
    vox = voxelizar([abajo, arriba], dx=0.5)
    assert vox.solapes == 0
    assert (vox.vertida_id[:, :, 0] == 1).all()
    assert (vox.vertida_id[:, :, 1] == 2).all()
    assert (vox.vertida_id[:, :, 2] == 2).all()


# ---------------------------------------------------------------- superficie y escalera
def test_area_expuesta_de_una_caja_es_exacta():
    solido = _caja(0, 2, 0, 1, 0, 1)
    vox = voxelizar([solido], dx=0.25)
    assert area_expuesta(vox.mask, vox.grid) == pytest.approx(10.0)
    assert area_exterior([solido]) == pytest.approx(10.0)


def test_el_volumen_converge_pero_el_area_de_una_pendiente_no():
    # Pirámide con aristas a 45° en planta/alzado: refinar no corrige el área en escalera.
    solido = _piramide(a=2.0, h=2.0)
    errores_v, razones_a = [], []
    for dx in (0.2, 0.1, 0.05):
        vox = voxelizar([solido], dx=dx)
        errores_v.append(vox.error_volumen())
        razones_a.append(area_expuesta(vox.mask, vox.grid) / area_exterior([solido]))
    assert errores_v[2] < errores_v[0] / 4
    # Caras con normal (1,0,1)/sqrt2: la escalera mide (|nx|+|nz|) = sqrt2 veces más
    # en las caras inclinadas. La base es plana y exacta, por eso el total da menos.
    area_real = area_exterior([solido])
    esperado = (16.0 + (area_real - 16.0) * np.sqrt(2)) / area_real
    assert razones_a[-1] == pytest.approx(esperado, rel=0.02)
    assert razones_a[0] == pytest.approx(razones_a[-1], rel=0.05)


# ---------------------------------------------------------------- IFC real
@pytest.fixture(scope="module")
def solidos():
    pytest.importorskip("ifcopenshell")
    from mcplan.bim import extraer_solidos
    return extraer_solidos(IFC)


def test_ifc_entrega_cinco_solidos_con_su_volumen(solidos):
    assert [s.vertida_id for s in solidos] == [1, 2, 3, 4, 5]
    for s in solidos:
        assert s.volumen == pytest.approx(s.volumen_pset_m3, rel=1e-3), s.nombre
    assert sum(s.volumen for s in solidos) == pytest.approx(636.9, abs=0.1)


def test_ifc_entrega_altura_y_secuencia(solidos):
    assert [s.verts[:, 2].min() for s in solidos] == pytest.approx([0.0, 0.55, 1.10, 2.20, 3.30])
    assert [s.verts[:, 2].max() for s in solidos] == pytest.approx([0.55, 1.10, 2.20, 3.30, 4.30])
    assert [s.inicio_h for s in solidos] == pytest.approx([0.0, 24.0, 48.0, 72.0, 96.0])


def test_read_ifc_vertidas_lee_los_inicios_reales():
    pytest.importorskip("ifcopenshell")
    from mcplan.plan import read_ifc_vertidas
    assert [v["inicio_h"] for v in read_ifc_vertidas(str(IFC))] == [0.0, 24.0, 48.0, 72.0, 96.0]


def test_horas_desde_primera():
    assert horas_desde_primera(["2026-01-02T06:00:00", "2026-01-01T00:00:00"]) == [30.0, 0.0]


@pytest.mark.parametrize("dx", [0.5, 0.25, 0.125, 0.1])
def test_fundacion_cada_celda_en_una_sola_vertida(solidos, dx):
    vox = voxelizar(solidos, dx=dx)
    assert vox.solapes == 0
    assert set(np.unique(vox.vertida_id)) == {FUERA, 1, 2, 3, 4, 5}
    # La malla es simetrica respecto de los ejes x e y
    assert (vox.mask == vox.mask[::-1, :, :]).all()
    assert (vox.mask == vox.mask[:, ::-1, :]).all()


def test_fundacion_error_de_volumen_baja_al_refinar(solidos):
    gruesa = voxelizar(solidos, dx=0.5).error_volumen()
    fina = voxelizar(solidos, dx=0.125).error_volumen()
    assert fina < gruesa
    assert fina < 0.01


def test_fundacion_los_voxeles_respetan_cada_vertida_en_altura(solidos):
    vox = voxelizar(solidos, dx=0.25)
    _, _, z = vox.grid.centers()
    for s in solidos:
        k = np.nonzero((vox.vertida_id == s.vertida_id).any(axis=(0, 1)))[0]
        assert z[k].min() >= s.verts[:, 2].min() and z[k].max() < s.verts[:, 2].max()


def test_dz_que_calza_con_las_interfaces(solidos):
    assert dz_que_calza(solidos, 0.25) == pytest.approx(0.275)
    assert dz_que_calza(solidos, 0.125) == pytest.approx(0.1375)


def test_calzar_dz_corrige_el_volumen_de_cada_vertida(solidos):
    sin_calzar = voxelizar(solidos, dx=0.25)
    calzada = voxelizar(solidos, dx=0.25, dz=dz_que_calza(solidos, 0.25))
    for vertida in (1, 2, 3, 4):
        assert calzada.error_volumen(vertida) < 0.02
    assert max(sin_calzar.error_volumen(v) for v in (1, 2, 3, 4)) > 0.09


def test_vertida_mas_delgada_que_la_celda_desaparece_y_el_solver_avisa(solidos):
    from mcplan.plan import load_plan, plan_desde_solidos
    from mcplan.thermal import build_model
    vox = voxelizar(solidos, dx=1.0)
    assert vox.volumen_voxel(2) == 0.0
    plantilla = load_plan(str(ROOT / "datos" / "fundacion_ifc.yaml"))
    with pytest.raises(ValueError, match="no tiene celdas"):
        build_model(plan_desde_solidos(plantilla, solidos, 1.0), voxeles=vox)


def test_volumen_malla_cubo():
    s = _caja(1, 3, 1, 3, 1, 3)
    assert volumen_malla(s.verts, s.faces) == pytest.approx(8.0)
