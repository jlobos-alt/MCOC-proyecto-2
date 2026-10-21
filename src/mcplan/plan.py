"""Plan declarativo del caso: entradas, vertidas, fronteras y criterios.

El solver nunca lee archivos: recibe un `Plan`. Modificar el plan de vertidas,
la aislacion o el clima no requiere tocar el codigo del solver.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace

import yaml


@dataclass
class MaterialSpec:
    name: str
    k: float
    cp: float
    rho: float


@dataclass
class LiftSpec:
    """Vertida de hormigon: se coloca, empieza a hidratar y tiene su propia isotermia."""

    id: int
    inicio_h: float
    z_min: float
    z_max: float
    material: str
    temperatura_colocacion_C: float = 18.0
    aislacion_mm: float = 0.0
    retiro_moldaje_h: float | None = None


@dataclass
class LayerSpec:
    """Capa en serie dentro de una frontera."""

    tipo: str = "conductiva"
    nombre: str = "capa"
    espesor_m: float = 0.0
    k: float = 0.0
    h: float = 0.0
    desde_h: float = 0.0
    hasta_h: float = float("inf")


@dataclass
class BoundarySpec:
    """Frontera termica asociada a un conjunto de caras.

    `direccion` define el conjunto de caras por defecto:
        "perimetro": caras laterales (x, y)
        "superficie": cara superior (z+)
        "base": cara inferior (z-), contacto con el suelo
        "ejes": eleccion explicita mediante `ejes` (0=x, 1=y, 2=z) y `signo`
    """

    name: str
    direccion: str = "perimetro"
    tipo: str = "convectiva"
    h: float = 12.0
    valor_dirichlet_C: float | None = None
    ejes: list[int] = field(default_factory=list)
    signo: str = "ambos"
    capas: list[LayerSpec] = field(default_factory=list)


@dataclass
class HydrationSpec:
    elevacion_adibatica_C: float = 45.0
    tau_h: float = 30.0
    elevacion_adibatica_2_C: float = 0.0
    tau_2_h: float = 0.0
    madurez: bool = False
    energia_activacion_K: float = 4000.0


@dataclass
class AmbientSpec:
    media_C: float = 15.0
    amplitud_C: float = 0.0
    periodo_h: float = 24.0
    desfase_h: float = 0.0
    datos: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class GeometrySpec:
    x: tuple[float, float] = (0.0, 24.0)
    y: tuple[float, float] = (0.0, 16.0)
    z: tuple[float, float] = (0.0, 2.4)
    dx: float = 0.3


@dataclass
class CriteriaSpec:
    T_max_C: float = 70.0
    delta_T_max_C: float = 20.0
    core_erosion: int = 2
    incluir_base_en_superficie: bool = False


@dataclass
class SimulationSpec:
    duracion_h: float = 168.0
    intervalo_salida_h: float = 1.0
    factor_estabilidad: float = 0.8


@dataclass
class Plan:
    """Caso completo, listo para el solver."""

    caso: str = "caso"
    descripcion: str = ""
    geometria: GeometrySpec = field(default_factory=GeometrySpec)
    materiales: dict[str, MaterialSpec] = field(default_factory=dict)
    vertidas: list[LiftSpec] = field(default_factory=list)
    hidratacion: HydrationSpec = field(default_factory=HydrationSpec)
    ambiente: AmbientSpec = field(default_factory=AmbientSpec)
    suelo: AmbientSpec = field(default_factory=AmbientSpec)
    fronteras: list[BoundarySpec] = field(default_factory=list)
    criterios: CriteriaSpec = field(default_factory=CriteriaSpec)
    simulacion: SimulationSpec = field(default_factory=SimulationSpec)


def plan_from_dict(data: dict) -> Plan:
    """Construye un `Plan` desde un diccionario (por ejemplo, un YAML)."""
    geom = data.get("geometria", {}) or {}
    geometry = GeometrySpec(
        x=tuple(geom.get("x", (0.0, 24.0))),
        y=tuple(geom.get("y", (0.0, 16.0))),
        z=tuple(geom.get("z", (0.0, 2.4))),
        dx=float(geom.get("dx", 0.3)),
    )

    materiales = {
        name: MaterialSpec(
            name=name,
            k=float(spec["k"]),
            cp=float(spec["cp"]),
            rho=float(spec["rho"]),
        )
        for name, spec in (data.get("materiales", {}) or {}).items()
    }

    vertidas = [
        LiftSpec(
            id=int(v["id"]),
            inicio_h=float(v.get("inicio_h", 0.0)),
            z_min=float(v["z_min"]),
            z_max=float(v["z_max"]),
            material=str(v.get("material", "M1")),
            temperatura_colocacion_C=float(v.get("temperatura_colocacion_C", 18.0)),
            aislacion_mm=float(v.get("aislacion_mm", 0.0)),
            retiro_moldaje_h=(
                float(v["retiro_moldaje_h"]) if v.get("retiro_moldaje_h") is not None else None
            ),
        )
        for v in data.get("vertidas", []) or []
    ]

    hyd = data.get("hidratacion", {}) or {}
    hydration = HydrationSpec(
        elevacion_adibatica_C=float(hyd.get("elevacion_adibatica_C", 45.0)),
        tau_h=float(hyd.get("tau_h", 30.0)),
        elevacion_adibatica_2_C=float(hyd.get("elevacion_adibatica_2_C", 0.0)),
        tau_2_h=float(hyd.get("tau_2_h", 0.0)),
        madurez=bool(hyd.get("madurez", False)),
        energia_activacion_K=float(hyd.get("energia_activacion_K", 4000.0)),
    )

    def ambient(spec: dict | None) -> AmbientSpec:
        spec = spec or {}
        return AmbientSpec(
            media_C=float(spec.get("media_C", 15.0)),
            amplitud_C=float(spec.get("amplitud_C", 0.0)),
            periodo_h=float(spec.get("periodo_h", 24.0)),
            desfase_h=float(spec.get("desfase_h", 0.0)),
            datos=[(float(t), float(v)) for t, v in spec.get("datos", [])],
        )

    fronteras = [
        BoundarySpec(
            name=spec["name"],
            direccion=str(spec.get("direccion", "perimetro")),
            tipo=str(spec.get("tipo", "convectiva")),
            h=float(spec.get("h", 12.0)),
            valor_dirichlet_C=(
                float(spec["valor_dirichlet_C"])
                if spec.get("valor_dirichlet_C") is not None
                else None
            ),
            ejes=[int(axis) for axis in spec.get("ejes", []) or []],
            signo=str(spec.get("signo", "ambos")),
            capas=[
                LayerSpec(
                    tipo=str(layer.get("tipo", "conductiva")),
                    nombre=str(layer.get("nombre", "capa")),
                    espesor_m=float(layer.get("espesor_m", 0.0)),
                    k=float(layer.get("k", 0.0)),
                    h=float(layer.get("h", 0.0)),
                    desde_h=float(layer.get("desde_h", 0.0)),
                    hasta_h=float(layer.get("hasta_h", float("inf"))),
                )
                for layer in spec.get("capas", []) or []
            ],
        )
        for spec in data.get("fronteras", []) or []
    ]

    crit = data.get("criterios", {}) or {}
    criteria = CriteriaSpec(
        T_max_C=float(crit.get("T_max_C", 70.0)),
        delta_T_max_C=float(crit.get("delta_T_max_C", 20.0)),
        core_erosion=int(crit.get("core_erosion", 2)),
        incluir_base_en_superficie=bool(crit.get("incluir_base_en_superficie", False)),
    )

    sim = data.get("simulacion", {}) or {}
    simulation = SimulationSpec(
        duracion_h=float(sim.get("duracion_h", 168.0)),
        intervalo_salida_h=float(sim.get("intervalo_salida_h", 1.0)),
        factor_estabilidad=float(sim.get("factor_estabilidad", 0.8)),
    )

    return Plan(
        caso=str(data.get("caso", "caso")),
        descripcion=str(data.get("descripcion", "")),
        geometria=geometry,
        materiales=materiales,
        vertidas=vertidas,
        hidratacion=hydration,
        ambiente=ambient(data.get("ambiente")),
        suelo=ambient(data.get("suelo")),
        fronteras=fronteras,
        criterios=criteria,
        simulacion=simulation,
    )


def load_plan(path: str) -> Plan:
    """Lee un plan declarativo desde YAML."""
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return plan_from_dict(data)


def apply_overrides(plan: Plan, values: dict[str, float]) -> Plan:
    """Devuelve una copia del plan con los parametros indicados modificados.

    Rutas soportadas:
        ambiente.media_C, suelo.media_C,
        hidratacion.elevacion_adibatica_C, hidratacion.tau_h,
        materiales.<nombre>.k, materiales.<nombre>.cp, materiales.<nombre>.rho,
        fronteras.<nombre>.h, fronteras.<nombre>.valor_dirichlet_C,
        vertidas.temperatura_colocacion_C, vertidas.retiro_moldaje_h
    """
    updated = copy.deepcopy(plan)
    for path, value in values.items():
        if path == "ambiente.media_C":
            updated.ambiente.media_C = float(value)
        elif path == "suelo.media_C":
            updated.suelo.media_C = float(value)
        elif path == "hidratacion.elevacion_adibatica_C":
            updated.hidratacion.elevacion_adibatica_C = float(value)
        elif path == "hidratacion.tau_h":
            updated.hidratacion.tau_h = float(value)
        elif path == "vertidas.temperatura_colocacion_C":
            for lift in updated.vertidas:
                lift.temperatura_colocacion_C = float(value)
        elif path == "vertidas.retiro_moldaje_h":
            for lift in updated.vertidas:
                lift.retiro_moldaje_h = float(value)
        elif path.startswith("fronteras."):
            _, name, prop = path.split(".", 2)
            grupo = next((g for g in updated.fronteras if g.name == name), None)
            if grupo is None:
                raise KeyError(f"Frontera desconocida en override: {name}")
            if prop == "h":
                grupo.h = float(value)
            elif prop == "valor_dirichlet_C":
                grupo.valor_dirichlet_C = float(value)
            else:
                raise KeyError(f"Propiedad de frontera no soportada: {path}")
        elif path.startswith("materiales."):
            _, name, prop = path.split(".", 2)
            if name not in updated.materiales:
                raise KeyError(f"Material desconocido en override: {name}")
            material = updated.materiales[name]
            if prop == "k":
                updated.materiales[name] = replace(material, k=float(value))
            elif prop == "cp":
                updated.materiales[name] = replace(material, cp=float(value))
            elif prop == "rho":
                updated.materiales[name] = replace(material, rho=float(value))
            else:
                raise KeyError(f"Propiedad de material no soportada: {path}")
        else:
            raise KeyError(f"Ruta de override no soportada: {path}")
    return updated


def read_ifc_vertidas(path: str) -> list[dict]:
    """Lee las vertidas y sus propiedades desde un IFC con property sets.

    Requiere que cada producto tenga un pset con VertidaID, Inicio_h,
    TemperaturaColocacion_C, TipoHormigon, Moldaje, Aislacion y RetiroMoldaje_h.
    """
    import ifcopenshell

    model = ifcopenshell.open(path)
    vertidas: list[dict] = []
    for product in model.by_type("IfcProduct"):
        if not getattr(product, "Name", None):
            continue
        properties: dict[str, object] = {}
        for relation in getattr(product, "IsDefinedBy", []) or []:
            definition = relation.RelatingPropertyDefinition
            if definition.is_a("IfcPropertySet"):
                for prop in definition.HasProperties:
                    value = prop.NominalValue.wrappedValue
                    properties[prop.Name] = value
        if "VertidaID" not in properties:
            continue
        vertidas.append(
            {
                "id": int(properties["VertidaID"]),
                "nombre": product.Name,
                "inicio_h": float(properties.get("Inicio_h", 0.0)),
                "temperatura_colocacion_C": float(properties.get("TemperaturaColocacion_C", 18.0)),
                "material": str(properties.get("TipoHormigon", "M1")),
                "aislacion": str(properties.get("Aislacion", "TBD")),
                "moldaje": str(properties.get("Moldaje", "TBD")),
                "retiro_moldaje_h": float(properties.get("RetiroMoldaje_h", 72.0)),
            }
        )
    vertidas.sort(key=lambda v: v["id"])
    return vertidas
