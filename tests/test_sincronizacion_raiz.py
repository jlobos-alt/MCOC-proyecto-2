"""La raiz reune E06-E10: suelo variable en Monte Carlo y snapshots verificables."""
from pathlib import Path

import pytest

from mcplan.plan import apply_overrides, load_plan
from mcplan.thermal import build_model

ROOT = Path(__file__).resolve().parents[1]


def test_override_de_suelo_cambia_la_temperatura_del_suelo():
    plan = load_plan(str(ROOT / "datos" / "caso_fundacion.yaml"))
    nuevo = apply_overrides(plan, {"suelo.media_C": 5.0})
    assert nuevo.suelo.mean_C == 5.0
    assert plan.suelo.mean_C != 5.0                       # el original no cambia
    assert build_model(nuevo).ground(0.0) == pytest.approx(5.0)


def test_suelo_antiguo_con_media_constante_se_lee_igual():
    plan = load_plan(str(ROOT / "datos" / "fundacion_ifc.yaml"))
    assert plan.suelo.mean_C == 12.0
    assert plan.suelo.amplitude_C == 0.0
    assert plan.suelo.series()(500.0) == pytest.approx(12.0)


def test_snapshots_del_repo_calzan_con_su_hash():
    # Falla si Git cambio el fin de linea al descargar (ver .gitattributes)
    from mcplan.snapshots import verify
    carpeta = ROOT / "datos" / "forecast"
    assert verify(carpeta)
