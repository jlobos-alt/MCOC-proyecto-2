"""Paquete `mcplan`: solver 1D (E01), plan declarativo, solver termico 3D, criterios y confiabilidad.

Solver 1D (E01):  from mcplan.thermal1d import Material, BC, solve_1d

Uso tipico:

    from mcplan import load_plan, build_model, solve, evaluar_criterios

    plan = load_plan("datos/caso_fundacion.yaml")
    model = build_model(plan)
    result = solve(model, duracion_h=plan.simulacion.duracion_h)
    veredicto = evaluar_criterios(result, plan.criterios)
"""

from .boundary import BoundaryGroup
from .criteria import Criterio, Veredicto, evaluar_criterios
from .grid import Grid
from .hydration import HydrationModel
from .materials import Material
from .plan import Plan, load_plan, plan_from_dict, read_ifc_vertidas
from .reliability import MuestraConfiabilidad, ejecutar_montecarlo
from .thermal import Model, Result, build_model, estimate_timestep, solve
from .weather import TemperatureSeries
from .thermal1d import BC, Result1D, solve_1d, stable_dt_1d
from .thermal1d import Material as Material1D

__all__ = [
    "BC",
    "Material1D",
    "Result1D",
    "solve_1d",
    "stable_dt_1d",
    "BoundaryGroup",
    "Criterio",
    "Grid",
    "HydrationModel",
    "Material",
    "Model",
    "MuestraConfiabilidad",
    "Plan",
    "Result",
    "TemperatureSeries",
    "Veredicto",
    "build_model",
    "estimate_timestep",
    "evaluar_criterios",
    "ejecutar_montecarlo",
    "load_plan",
    "plan_from_dict",
    "read_ifc_vertidas",
    "solve",
]
