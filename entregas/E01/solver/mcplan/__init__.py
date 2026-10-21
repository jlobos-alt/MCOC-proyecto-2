"""Paquete `mcplan`: plan declarativo, solver termico, criterios y confiabilidad.

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

__all__ = [
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
