"""Solver termico por balance de celdas (volumenes finitos cartesiano).

Ecuacion resuelta por celda i:

    rho_i * cp_i * V_i * dT_i/dt
        = sum_j G_ij * (T_j - T_i)
        + Qdot_i * V_i
        + Q_borde_i

donde:

    G_ij  = k_ij * A_ij / d_ij     conductancia entre celdas vecinas
    G_b   = A / R_total             conductancia hacia el medio (frontera)
    Qdot  = rho * cp * d(theta_ad)/dt   calor de hidratacion

Se usa un esquema explicito (Euler) con paso de tiempo elegido a partir del
criterio de estabilidad derivado del balance:

    dt <= C_i / (sum_j G_ij + G_b,i)

que, para grilla uniforme y un solo material, se reduce al criterio de Fourier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .boundary import BoundaryGroup, ConductionLayer, ConvectionLayer, ScheduledLayer
from .grid import Grid, box_mask, core_cells, surface_cells
from .hydration import HydrationModel
from .materials import Material
from .plan import Plan
from .weather import TemperatureSeries


@dataclass
class FaceSet:
    """Caras de una misma direccion, con su celda ducena y su vecina."""

    owner: np.ndarray
    neighbor: np.ndarray
    area: float
    spacing: float
    axis: int
    sign: np.ndarray


@dataclass
class Model:
    """Modelo numerico listo para resolver."""

    grid: Grid
    mask: np.ndarray
    lift_of_cell: np.ndarray
    k_flat: np.ndarray
    rho_cp_flat: np.ndarray
    place_time: np.ndarray
    placement_T: np.ndarray
    materials: list[Material]
    hydration: HydrationModel
    groups: dict[str, BoundaryGroup]
    ambient: TemperatureSeries
    ground: TemperatureSeries
    is_core: np.ndarray
    is_surface: np.ndarray
    internal: dict[int, FaceSet] = field(default_factory=dict)
    internal_G: dict[int, np.ndarray] = field(default_factory=dict)
    internal_start: dict[int, np.ndarray] = field(default_factory=dict)
    exposed: dict[int, FaceSet] = field(default_factory=dict)
    exposed_group: dict[int, np.ndarray] = field(default_factory=dict)
    exposed_start: dict[int, np.ndarray] = field(default_factory=dict)
    exposed_end: dict[int, np.ndarray] = field(default_factory=dict)


@dataclass
class Result:
    """Salida de una simulacion deterministica."""

    time_h: np.ndarray
    T_max_global: np.ndarray
    T_max_core: np.ndarray
    T_min_surface: np.ndarray
    delta_T: np.ndarray
    T_mean: np.ndarray
    dt_s: float
    T_final: np.ndarray
    active_final: np.ndarray
    metadata: dict = field(default_factory=dict)

    @property
    def T_max_abs(self) -> float:
        return float(np.nanmax(self.T_max_global)) if self.time_h.size else float("nan")

    @property
    def delta_T_max(self) -> float:
        return float(np.nanmax(self.delta_T)) if self.time_h.size else float("nan")

    def time_of_max(self, series: np.ndarray) -> float:
        """Instante en que la serie alcanza su maximo."""
        if series.size == 0 or np.all(np.isnan(series)):
            return float("nan")
        return float(self.time_h[int(np.nanargmax(series))])

    def time_of_min(self, series: np.ndarray) -> float:
        """Instante en que la serie alcanza su minimo."""
        if series.size == 0 or np.all(np.isnan(series)):
            return float("nan")
        return float(self.time_h[int(np.nanargmin(series))])


def _slice_along(array: np.ndarray, axis: int, index) -> np.ndarray:
    if axis == 0:
        return array[index, :, :]
    if axis == 1:
        return array[:, index, :]
    return array[:, :, index]


def _face_area(grid: Grid, axis: int) -> float:
    return grid.face_area(axis)


def build_model(plan: Plan) -> Model:
    """Construye el modelo numerico a partir de un plan declarativo."""
    geom = plan.geometria
    dx = geom.dx
    grid = Grid(
        nx=int(round((geom.x[1] - geom.x[0]) / dx)),
        ny=int(round((geom.y[1] - geom.y[0]) / dx)),
        nz=int(round((geom.z[1] - geom.z[0]) / dx)),
        dx=dx,
        dy=dx,
        dz=dx,
        x0=geom.x[0],
        y0=geom.y[0],
        z0=geom.z[0],
    )

    material_names = sorted({lift.material for lift in plan.vertidas})
    materials = [
        Material(
            name=name,
            k=plan.materiales[name].k,
            cp=plan.materiales[name].cp,
            rho=plan.materiales[name].rho,
        )
        for name in material_names
    ]
    material_index = {name: i for i, name in enumerate(material_names)}

    mask = np.zeros(grid.shape, dtype=bool)
    lift_of_cell = np.full(grid.shape, -1, dtype=int)
    place_time = np.full(grid.shape, np.inf)
    placement_T = np.full(grid.shape, np.nan)

    for lift in plan.vertidas:
        lift_mask = box_mask(grid, geom.x, geom.y, (lift.z_min, lift.z_max))
        mask |= lift_mask
        lift_of_cell[lift_mask] = lift.id
        place_time[lift_mask] = lift.inicio_h
        placement_T[lift_mask] = lift.temperatura_colocacion_C

    k_field = np.zeros(grid.shape)
    rho_cp_field = np.zeros(grid.shape)
    for name, index in material_index.items():
        selection = lift_of_cell >= 0
        for lift in plan.vertidas:
            if lift.material != name:
                continue
            cells = (lift_of_cell == lift.id) & selection
            material = materials[index]
            k_field[cells] = material.k
            rho_cp_field[cells] = material.volumetric_heat_capacity

    ids = np.arange(grid.n_cells).reshape(grid.shape)

    k_flat = k_field.ravel()
    rho_cp_flat = rho_cp_field.ravel()
    place_time_flat = place_time.ravel()
    placement_T_flat = placement_T.ravel()
    lift_flat = lift_of_cell.ravel()
    mask_flat = mask.ravel()

    ambient = TemperatureSeries.from_spec(
        {
            "media_C": plan.ambiente.media_C,
            "amplitud_C": plan.ambiente.amplitud_C,
            "periodo_h": plan.ambiente.periodo_h,
            "desfase_h": plan.ambiente.desfase_h,
            "datos": plan.ambiente.datos,
        }
    )
    ground = TemperatureSeries.from_spec(
        {
            "media_C": plan.suelo.media_C,
            "amplitud_C": plan.suelo.amplitud_C,
            "periodo_h": plan.suelo.periodo_h,
            "desfase_h": plan.suelo.desfase_h,
            "datos": plan.suelo.datos,
        }
    )

    groups: dict[str, BoundaryGroup] = {}
    for spec in plan.fronteras:
        far_field = ground if spec.direccion == "base" else ambient
        capas: list[ScheduledLayer] = []
        for layer in spec.capas:
            if layer.tipo == "convectiva":
                base_layer = ConvectionLayer(h=layer.h, name=layer.nombre)
            else:
                base_layer = ConductionLayer(
                    thickness=layer.espesor_m,
                    conductivity=layer.k,
                    name=layer.nombre,
                )
            capas.append(
                ScheduledLayer(
                    layer=base_layer,
                    desde_h=layer.desde_h,
                    hasta_h=layer.hasta_h,
                )
            )
        group = BoundaryGroup(
            name=spec.name,
            tipo=spec.tipo,
            h=spec.h,
            capas=capas,
            far_field=far_field,
            valor_dirichlet_C=spec.valor_dirichlet_C,
        )
        groups[spec.name] = group

    if "adiabatico" not in groups:
        groups["adiabatico"] = BoundaryGroup(
            name="adiabatico",
            tipo="adiabatica",
            far_field=ground,
        )

    model = Model(
        grid=grid,
        mask=mask.ravel(),
        lift_of_cell=lift_flat,
        k_flat=k_flat,
        rho_cp_flat=rho_cp_flat,
        place_time=place_time_flat,
        placement_T=placement_T_flat,
        materials=materials,
        hydration=HydrationModel(
            theta_inf_1_C=plan.hidratacion.elevacion_adibatica_C,
            tau_1_h=plan.hidratacion.tau_h,
            theta_inf_2_C=plan.hidratacion.elevacion_adibatica_2_C,
            tau_2_h=plan.hidratacion.tau_2_h,
            activation_temperature_K=(
                plan.hidratacion.energia_activacion_K if plan.hidratacion.madurez else 0.0
            ),
        ),
        groups=groups,
        ambient=ambient,
        ground=ground,
        is_core=core_cells(mask, plan.criterios.core_erosion).ravel(),
        is_surface=surface_cells(mask, plan.criterios.incluir_base_en_superficie).ravel(),
    )

    _build_faces(model, plan, ids, mask_flat)
    _definir_conjuntos_de_control(model, plan, mask_flat)
    return model


def _definir_conjuntos_de_control(model: Model, plan: Plan, mask_flat: np.ndarray) -> None:
    """Define las celdas de superficie y de nucleo usadas por los criterios.

    La superficie se toma de las caras expuestas permanentes (las que quedan
    expuestas al final de la secuencia constructiva), excluyendo la base en
    contacto con el suelo salvo que se pida incluirla. Las caras transitorias
    (superficie de una vertida que espera la siguiente) no se consideran: no
    representan la superficie final de la obra.
    """
    nombre_base = next(
        (spec.name for spec in plan.fronteras if spec.direccion == "base"),
        "base",
    )
    superficie = np.zeros(model.grid.n_cells, dtype=bool)
    for axis, face in model.exposed.items():
        if face.owner.size == 0:
            continue
        permanentes = np.isinf(model.exposed_end[axis])
        grupos = model.exposed_group[axis]
        seleccion = permanentes & (grupos != nombre_base)
        if plan.criterios.incluir_base_en_superficie:
            seleccion = permanentes
        superficie[face.owner[seleccion]] = True
    model.is_surface = superficie & mask_flat


def _build_faces(model: Model, plan: Plan, ids: np.ndarray, mask_flat: np.ndarray) -> None:
    """Clasifica las caras en internas (conductancia fija) y expuestas (frontera).

    Una cara interior entre dos celdas de la geometria conduce a partir de
    max(t_A, t_B). Antes de eso, la celda ya colocada tiene esa cara expuesta al
    medio: por eso las caras se registran como registros dirigidos (celda duena,
    celda vecina) y el periodo de exposicion depende de las horas de vertida.
    """
    grid = model.grid

    for axis in range(3):
        n = grid.shape[axis]
        area = _face_area(grid, axis)
        spacing = grid.axis_length(axis)

        a_all = _slice_along(ids, axis, slice(0, n - 1)).ravel()
        b_all = _slice_along(ids, axis, slice(1, n)).ravel()
        low = _slice_along(ids, axis, 0).ravel()
        high = _slice_along(ids, axis, n - 1).ravel()

        internal_owner = []
        internal_neighbor = []
        internal_G = []
        internal_start = []

        both = mask_flat[a_all] & mask_flat[b_all]
        if np.any(both):
            k_owner = model.k_flat[a_all[both]]
            k_neighbor = model.k_flat[b_all[both]]
            k_face = 2.0 * k_owner * k_neighbor / np.maximum(k_owner + k_neighbor, 1e-12)
            internal_owner.append(a_all[both])
            internal_neighbor.append(b_all[both])
            internal_G.append(k_face * area / spacing)
            internal_start.append(
                np.maximum(model.place_time[a_all[both]], model.place_time[b_all[both]])
            )

        records_owner = []
        records_neighbor = []
        records_sign = []

        records_owner.append(a_all)
        records_neighbor.append(b_all)
        records_sign.append(np.ones_like(a_all))

        records_owner.append(b_all)
        records_neighbor.append(a_all)
        records_sign.append(-np.ones_like(a_all))

        records_owner.append(low)
        records_neighbor.append(np.full_like(low, -1))
        records_sign.append(-np.ones_like(low))

        records_owner.append(high)
        records_neighbor.append(np.full_like(high, -1))
        records_sign.append(np.ones_like(high))

        owner = np.concatenate(records_owner)
        neighbor = np.concatenate(records_neighbor)
        sign = np.concatenate(records_sign)

        keep = mask_flat[owner] & np.isfinite(model.place_time[owner])
        owner = owner[keep]
        neighbor = neighbor[keep]
        sign = sign[keep]

        start = model.place_time[owner].copy()
        has_neighbor = neighbor >= 0
        neighbor_inside = np.zeros(owner.size, dtype=bool)
        neighbor_time = np.full(owner.size, np.inf)
        if np.any(has_neighbor):
            neighbor_inside[has_neighbor] = mask_flat[neighbor[has_neighbor]]
            neighbor_time[has_neighbor] = model.place_time[neighbor[has_neighbor]]

        waiting = has_neighbor & neighbor_inside & (neighbor_time > start)
        exposed = waiting | ~has_neighbor
        end = np.where(waiting, neighbor_time, np.inf)

        owner = owner[exposed]
        neighbor = neighbor[exposed]
        sign = sign[exposed]
        start = start[exposed]
        end = end[exposed]

        if internal_owner:
            model.internal[axis] = FaceSet(
                owner=np.concatenate(internal_owner),
                neighbor=np.concatenate(internal_neighbor),
                area=area,
                spacing=spacing,
                axis=axis,
                sign=np.ones_like(np.concatenate(internal_owner)),
            )
            model.internal_G[axis] = np.concatenate(internal_G)
            model.internal_start[axis] = np.concatenate(internal_start)

        if owner.size:
            model.exposed[axis] = FaceSet(
                owner=owner,
                neighbor=neighbor,
                area=area,
                spacing=spacing,
                axis=axis,
                sign=sign,
            )
            model.exposed_group[axis] = _group_for_face(plan, axis, sign, owner)
            model.exposed_start[axis] = start
            model.exposed_end[axis] = end


def _group_for_face(plan: Plan, axis: int, sign: np.ndarray, owner: np.ndarray) -> np.ndarray:
    """Asigna el grupo de frontera a cada cara expuesta.

    `sign` indica el sentido en que la cara mira hacia afuera: +1 si la celda
    ausente esta en el sentido positivo del eje, -1 en el sentido negativo. Para
    el eje z eso distingue la cara superior de la base.
    """
    specs = plan.fronteras
    by_direction: dict[str, str] = {}
    for spec in specs:
        by_direction.setdefault(spec.direccion, spec.name)

    if axis in (0, 1):
        out = np.full(owner.shape, by_direction.get("perimetro", "adiabatico"), dtype=object)
    else:
        up = by_direction.get("superficie", "adiabatico")
        down = by_direction.get("base", "adiabatico")
        out = np.where(sign > 0, up, down).astype(object)

    for spec in specs:
        if spec.direccion != "ejes" or axis not in spec.ejes:
            continue
        if spec.signo == "+":
            selection = sign > 0
        elif spec.signo == "-":
            selection = sign < 0
        else:
            selection = np.ones(owner.shape, dtype=bool)
        out[selection] = spec.name
    return out


def estimate_timestep(model: Model, safety: float = 0.8) -> float:
    """Paso de tiempo estable segun el criterio de estabilidad del balance."""
    n_cells = model.grid.n_cells
    conductance = np.zeros(n_cells)
    for axis, face in model.internal.items():
        np.add.at(conductance, face.owner, model.internal_G[axis])
        np.add.at(conductance, face.neighbor, model.internal_G[axis])

    breakpoints = _schedule_breakpoints(model)
    for axis, face in model.exposed.items():
        if face.owner.size == 0:
            continue
        resistance = np.empty(face.owner.size)
        group_names = model.exposed_group[axis]
        for name in np.unique(group_names):
            group = model.groups[str(name)]
            selection = group_names == name
            r_min = group.minimum_resistance(breakpoints)
            if np.isinf(r_min):
                resistance[selection] = np.inf
                continue
            half = face.spacing / 2.0
            k_owner = model.k_flat[face.owner[selection]]
            r_half = np.where(k_owner > 0, half / np.maximum(k_owner, 1e-12), np.inf)
            resistance[selection] = r_half + r_min
        with np.errstate(divide="ignore"):
            g_face = face.area / resistance
        np.add.at(conductance, face.owner, np.nan_to_num(g_face, posinf=0.0))

    capacity = model.rho_cp_flat * model.grid.cell_volume
    active = model.mask & np.isfinite(model.place_time)
    denominator = conductance[active]
    valid = denominator > 0
    if not np.any(valid):
        return float("inf")
    limits = capacity[active][valid] / denominator[valid]
    return float(safety * np.min(limits))


def _schedule_breakpoints(model: Model) -> list[float]:
    breakpoints: list[float] = []
    for group in model.groups.values():
        for scheduled in group.capas:
            breakpoints.append(scheduled.desde_h)
            if np.isfinite(scheduled.hasta_h):
                breakpoints.append(scheduled.hasta_h)
    return breakpoints


def solve(
    model: Model,
    duracion_h: float = 168.0,
    intervalo_salida_h: float = 1.0,
    dt_s: float | None = None,
    factor_estabilidad: float = 0.8,
    guardar_campo: bool = True,
    temperatura_inicial=None,
) -> Result:
    """Resuelve el problema termico y devuelve las series de salida.

    `temperatura_inicial` permite imponer un perfil propio (por ejemplo el
    sinusoidal de la verificacion analitica) en lugar de la temperatura de
    colocacion. Acepta un vector plano o una funcion de (x, y, z).
    """
    grid = model.grid
    n_cells = grid.n_cells
    dt = dt_s if dt_s else estimate_timestep(model, factor_estabilidad)
    if not np.isfinite(dt):
        raise ValueError("No se pudo estimar un paso de tiempo: revise las fronteras.")

    output_dt_s = intervalo_salida_h * 3600.0
    steps_per_output = max(1, int(np.ceil(output_dt_s / dt)))
    dt = output_dt_s / steps_per_output

    initial = _initial_field(model, temperatura_inicial)

    T = np.full(n_cells, np.nan)
    equivalent_age = np.zeros(n_cells)

    placed_mask = np.zeros(n_cells, dtype=bool)
    active = placed_mask.copy()

    n_steps = int(np.ceil(duracion_h * 3600.0 / dt))
    times: list[float] = []
    max_global: list[float] = []
    max_core: list[float] = []
    min_surface: list[float] = []
    mean_values: list[float] = []

    for step in range(n_steps + 1):
        t_h = step * dt / 3600.0

        newly = model.mask & (~placed_mask) & (model.place_time <= t_h + 1e-9)
        if np.any(newly):
            T[newly] = initial[newly]
            placed_mask |= newly
            active = placed_mask.copy()

        if step % steps_per_output == 0:
            times.append(t_h)
            max_global.append(_max_or_nan(T, active))
            max_core.append(_max_or_nan(T, active & model.is_core))
            min_surface.append(_min_or_nan(T, active & model.is_surface))
            mean_values.append(_mean_or_nan(T, active))

        if step == n_steps:
            break

        net = np.zeros(n_cells)

        _accumulate_internal(model, T, net, t_h)
        _accumulate_boundary(model, T, net, t_h)
        _accumulate_sources(model, T, net, dt, t_h, active, equivalent_age)

        update = np.zeros(n_cells)
        capacity = model.rho_cp_flat * grid.cell_volume
        with np.errstate(divide="ignore", invalid="ignore"):
            update = np.where(capacity > 0, dt * net / np.where(capacity > 0, capacity, 1.0), 0.0)
        T = np.where(active, T + update, T)

    time_h = np.array(times)
    return Result(
        time_h=time_h,
        T_max_global=np.array(max_global),
        T_max_core=np.array(max_core),
        T_min_surface=np.array(min_surface),
        delta_T=np.array(max_core) - np.array(min_surface),
        T_mean=np.array(mean_values),
        dt_s=dt,
        T_final=T.reshape(grid.shape),
        active_final=placed_mask.reshape(grid.shape),
        metadata={"n_cells": int(n_cells), "pasos": int(n_steps)},
    )


def _initial_field(model: Model, temperatura_inicial) -> np.ndarray:
    """Campo de temperatura inicial por celda."""
    if temperatura_inicial is None:
        return model.placement_T.copy()
    if callable(temperatura_inicial):
        x, y, z = model.grid.centers()
        X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
        return np.asarray(temperatura_inicial(X, Y, Z), dtype=float).ravel()
    values = np.asarray(temperatura_inicial, dtype=float).ravel()
    if values.size != model.grid.n_cells:
        raise ValueError("El campo inicial no tiene el numero de celdas esperado.")
    return values


def _accumulate_internal(model: Model, T: np.ndarray, net: np.ndarray, t_h: float) -> None:
    n_cells = model.grid.n_cells
    for axis, face in model.internal.items():
        conducting = model.internal_start[axis] <= t_h + 1e-9
        if not np.any(conducting):
            continue
        owner = face.owner[conducting]
        neighbor = face.neighbor[conducting]
        g = model.internal_G[axis][conducting]
        flux = g * (T[neighbor] - T[owner])
        net += np.bincount(owner, weights=flux, minlength=n_cells)
        net -= np.bincount(neighbor, weights=flux, minlength=n_cells)


def _accumulate_boundary(model: Model, T: np.ndarray, net: np.ndarray, t_h: float) -> None:
    for axis, face in model.exposed.items():
        if face.owner.size == 0:
            continue
        group_names = model.exposed_group[axis]
        start = model.exposed_start[axis]
        end = model.exposed_end[axis]
        active = (start <= t_h + 1e-9) & (t_h < end)
        if not np.any(active):
            continue
        owner = face.owner[active]
        group_names = group_names[active]
        half = face.spacing / 2.0
        k_owner = model.k_flat[owner]
        resistance = np.empty(owner.size)
        far_field = np.empty(owner.size)
        for name in np.unique(group_names):
            selection = group_names == name
            group = model.groups[str(name)]
            if group.tipo == "adiabatica":
                resistance[selection] = np.inf
                far_field[selection] = np.nan
                continue
            r_layers = group.capas_resistance(t_h)
            r_conv = group.convective_resistance()
            r_half = np.where(k_owner[selection] > 0, half / np.maximum(k_owner[selection], 1e-12), np.inf)
            if group.tipo == "dirichlet":
                resistance[selection] = r_half
                far_field[selection] = group.far_field_at(t_h)
                continue
            resistance[selection] = r_half + r_layers + r_conv
            far_field[selection] = group.far_field_at(t_h)
        with np.errstate(divide="ignore", invalid="ignore"):
            conductance = face.area / resistance
        valid = np.isfinite(conductance) & np.isfinite(far_field)
        flux = np.zeros(owner.size)
        flux[valid] = conductance[valid] * (far_field[valid] - T[owner[valid]])
        net += np.bincount(owner, weights=flux, minlength=model.grid.n_cells)


def _accumulate_sources(
    model: Model,
    T: np.ndarray,
    net: np.ndarray,
    dt: float,
    t_h: float,
    active: np.ndarray,
    equivalent_age: np.ndarray,
) -> None:
    if not np.any(active):
        return
    indices = np.flatnonzero(active)
    age_h = t_h - model.place_time[indices]
    age_h = np.maximum(age_h, 0.0)
    temperature = T[indices]
    rho_cp = model.rho_cp_flat[indices]

    if model.hydration.uses_maturity:
        maturity = model.hydration.maturity_factor(temperature)
        equivalent_age[indices] += dt / 3600.0 * maturity
        dtheta_dt = model.hydration.dtheta_dage(equivalent_age[indices])
    else:
        dtheta_dt = model.hydration.dtheta_dage(age_h)

    qdot = rho_cp * dtheta_dt / 3600.0
    net[indices] += qdot * model.grid.cell_volume


def _max_or_nan(T: np.ndarray, selection: np.ndarray) -> float:
    if not np.any(selection):
        return float("nan")
    return float(np.nanmax(T[selection]))


def _min_or_nan(T: np.ndarray, selection: np.ndarray) -> float:
    if not np.any(selection):
        return float("nan")
    return float(np.nanmin(T[selection]))


def _mean_or_nan(T: np.ndarray, selection: np.ndarray) -> float:
    if not np.any(selection):
        return float("nan")
    return float(np.nanmean(T[selection]))
