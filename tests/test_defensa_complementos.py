"""Defensa: el caso real cierra su balance de energia y es insensible al paso temporal."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def dc():
    pytest.importorskip("ifcopenshell")
    import defensa_complementos as modulo
    import defensa_plan as dp
    if dp._ctx(1.0)["provisoria"]:
        pytest.skip("sin curvas reales")
    modulo.DX = 1.0                       # malla gruesa: misma cadena, mas rapido
    return modulo


def _energia(dc, dt):
    import defensa_plan as dp
    curva = dp._ctx(1.0)["curvas"][0]
    r, modelo, p, D, H = dc.correr_detalle(dc.ELEGIDO, curva, None, dx=1.0, dt_s=dt, adiabatico=True, campos=False)
    activa = np.isfinite(modelo.place_time) & modelo.mask
    V, rho_cp = modelo.grid.cell_volume, modelo.rho_cp_flat[activa]
    generado = np.sum(rho_cp * V * curva.theta(H - modelo.place_time[activa]))
    almacenado = np.sum(rho_cp * V * (r.T_final.ravel()[activa] - dc.ELEGIDO.t_col_C))
    return abs(almacenado - generado) / generado


def test_balance_de_energia_cierra_y_mejora_con_dt(dc):
    # Fundacion aislada con la curva real y colocacion por capas: lo almacenado es lo generado.
    # La diferencia es la fraccion de paso antes de que nazca cada celda, y baja con dt.
    grueso, fino = _energia(dc, 3600.0), _energia(dc, 900.0)
    assert grueso < 1e-3
    assert fino < grueso / 2
