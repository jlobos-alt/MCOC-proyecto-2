"""E06: convergencia con el espacio y el tiempo separados."""
from mcplan import verificacion as v


def test_espacial_1d_orden_2_con_dt_fijo():
    caso = v.convergencia_espacial(1, ns=(10, 20, 40), dt_s=40.0, t_h=12.0)
    assert caso.ok, caso.detalle
    # Sin el error temporal, el orden no se pasa de 2 por cancelacion de errores
    assert 1.9 < caso.datos["ordenes"][-1] < 2.1


def test_temporal_1d_orden_1_con_malla_fija():
    caso = v.convergencia_temporal(1, n=20, dts=(240.0, 120.0, 60.0), dt_ref=7.5, t_h=12.0)
    assert caso.ok, caso.detalle
    assert 0.9 < caso.datos["ordenes"][-1] < 1.1
