"""Tres condiciones de borde en el bloque 3 x 3 x 0.6 m (scripts/casos_borde_bloque.py).

    python -m pytest tests/test_casos_borde_bloque.py -v
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

_ruta = Path(__file__).resolve().parents[1] / "scripts" / "casos_borde_bloque.py"
_spec = importlib.util.spec_from_file_location("casos_borde_bloque", _ruta)
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)


def params(**kw):
    base = dict(L=3.0, H=0.6, nxy=6, nz=12, Tbase=20.0, Tsup=30.0, beta=5.0, Tinf=20.0, TbaseRobin=30.0)
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.mark.parametrize("Tbase,Tsup", [(20.0, 30.0), (10.0, 40.0)])
def test_dirichlet_20_30(Tbase, Tsup):
    caso = cb.caso_dirichlet(params(Tbase=Tbase, Tsup=Tsup))[0]
    assert caso.ok, caso.linea()


def test_neumann_adiabatico_conserva_energia_y_va_al_promedio():
    caso, z, num, exacto, _ = cb.caso_adiabatico(params())
    assert caso.ok, caso.linea()
    assert abs(num - 25.0).max() < 1e-6


@pytest.mark.parametrize("beta", [1.0, 5.0, 50.0])
def test_robin_beta(beta):
    caso = cb.caso_robin(params(beta=beta))[0]
    assert caso.ok, caso.linea()
