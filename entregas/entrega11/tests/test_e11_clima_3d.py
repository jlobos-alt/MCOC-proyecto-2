"""E11: el snapshot llega a la frontera y los resultados 3D muestran nucleo y superficie."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mcplan.environment import aplicar_ambiente, condiciones_de_timeline
from mcplan.meteo import assemble_timeline
from mcplan.snapshots import latest_snapshot, load_snapshot

ROOT = Path(__file__).resolve().parents[1]
FORECAST = ROOT / "datos" / "forecast"


@pytest.fixture(scope="module")
def forecast():
    meta = latest_snapshot(FORECAST, "open-meteo-forecast")
    return load_snapshot(FORECAST, meta.snapshot_id)


def _csv(meta):
    with open(FORECAST / meta.snapshot_id / "normalizado.csv", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def test_la_frontera_recibe_la_temperatura_del_archivo(forecast):
    frame, meta = forecast
    filas = _csv(meta)
    timeline = assemble_timeline(meta.first_time + ":00", list(range(25)), forecast=frame)
    h_fn, t_fn = condiciones_de_timeline(timeline, con_viento=False, con_radiacion=False)
    for t in (0, 5, 13, 24):
        assert t_fn(t) == pytest.approx(float(filas[t]["temperature_2m"]))
        assert h_fn(t) == pytest.approx(5.7)                  # aire en calma, sin viento
    assert timeline.sources == {"forecast": 25}


def test_viento_y_radiacion_entran_por_h_y_sol_aire(forecast):
    frame, meta = forecast
    fila = _csv(meta)[12]
    v, G, T = float(fila["wind_speed_10m"]), float(fila["shortwave_radiation"]), float(fila["temperature_2m"])
    timeline = assemble_timeline(meta.first_time + ":00", list(range(25)), forecast=frame)
    h_fn, t_fn = condiciones_de_timeline(timeline)
    h_rad = 4 * 0.9 * 5.670374419e-8 * (T + 273.15) ** 3
    assert h_fn(12) == pytest.approx(5.7 + 3.8 * v + h_rad)
    assert G > 100 and t_fn(12) > T                            # con sol, T sol-aire supera al aire


def test_aplicar_ambiente_no_toca_la_base(forecast):
    from mcplan.plan import load_plan
    frame, meta = forecast
    plan = load_plan(str(ROOT / "datos" / "fundacion_e10.yaml"))
    timeline = assemble_timeline(meta.first_time + ":00", list(range(25)), forecast=frame)
    aplicar_ambiente(plan, timeline)
    for frontera in plan.fronteras:
        tiene_serie = frontera.far_field_series is not None
        assert tiene_serie == (frontera.direccion != "base"), frontera.name


def test_vti_con_nucleo_y_superficie(tmp_path):
    pv = pytest.importorskip("pyvista")
    from mcplan.grid import Grid
    from mcplan.visualization import guardar_serie
    grid = Grid(nx=4, ny=3, nz=2, dx=1.0, dy=1.0, dz=1.0)
    ids = np.ones(grid.shape, dtype=int)
    nucleo = np.zeros(grid.shape, dtype=np.uint8)
    nucleo[1:3, 1, :] = 1
    archivos = guardar_serie(tmp_path, grid, ids, {0.0: np.full(grid.shape, 20.0)},
                             extras={"nucleo": nucleo, "superficie": 1 - nucleo})
    leida = pv.read(archivos[0])
    np.testing.assert_array_equal(np.asarray(leida.cell_data["nucleo"]).reshape(grid.shape, order="F"), nucleo)
    assert int(np.asarray(leida.cell_data["superficie"]).sum()) == grid.n_cells - int(nucleo.sum())


def test_visor_resalta_nucleo_y_superficie():
    pytest.importorskip("pyvista")
    from mcplan.grid import Grid
    from mcplan.visualization import VisorVertidas
    grid = Grid(nx=6, ny=6, nz=4, dx=1.0, dy=1.0, dz=1.0)
    ids = np.ones(grid.shape, dtype=int)
    nucleo = np.zeros(grid.shape, dtype=bool)
    nucleo[2:4, 2:4, 1:3] = True
    visor = VisorVertidas(grid, ids, {0.0: np.full(grid.shape, 30.0)}, off_screen=True, tamano=(300, 200),
                          zonas={"nucleo": nucleo, "superficie": ~nucleo})
    try:
        assert not visor.zonas[("nucleo", "entera")].GetVisibility()
        visor.mostrar_zona("nucleo", True)
        assert visor.zonas[("nucleo", "entera")].GetVisibility()
        assert visor.piezas[(1, "entera")][1].GetProperty().GetOpacity() < 0.5   # el resto se transparenta
        visor.fijar_corte(True)
        assert visor.zonas[("nucleo", "media")].GetVisibility()
        visor.crear_controles()
        assert visor._casillas["nucleo"].GetRepresentation().GetState() == 1
        visor.mostrar_zona("nucleo")
        assert visor._casillas["nucleo"].GetRepresentation().GetState() == 0
        assert visor.piezas[(1, "media")][1].GetProperty().GetOpacity() == 1.0
    finally:
        visor.cerrar()


def test_comando_e11_completo(tmp_path):
    pytest.importorskip("ifcopenshell")
    pytest.importorskip("pyvista")
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e11_clima_3d.py"), "--dx", "1", "--duracion-h", "24",
         "--salida", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", timeout=240,
    )
    assert p.returncode == 0, p.stderr
    for paso in range(1, 9):
        assert f"[{paso}]" in p.stdout
    for archivo in ("clima.png", "frontera.png", "cortes_3d.png", "vista_3d.png", "nucleo_superficie.png",
                    "corrida.json", "vti/serie.pvd"):
        assert (tmp_path / archivo).exists(), archivo
    datos = json.loads((tmp_path / "corrida.json").read_text(encoding="utf-8"))
    assert datos["fuentes_por_hora"] == {"forecast": 25}
    assert set(datos["zonas"]) == {"nucleo", "superficie"}
