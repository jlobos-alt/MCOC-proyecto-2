"""Voxelizacion cartesiana: pasa los solidos del IFC a una grilla de celdas.

Regla de pertenencia: una celda es de una vertida si su CENTRO esta dentro del
solido. El borde queda en escalera (staircase), que es lo que pide el baseline.

Como se decide "dentro" (conteo de cruces): desde el centro de la celda se lanza
un rayo vertical hacia abajo y se cuentan los triangulos de la malla que cruza.
Numero impar: dentro. Numero par: fuera.

    z ^         cruces bajo el punto
      |  o  2   par    -> fuera (sobre el solido)
      | /////
      | /o/ 1   impar  -> dentro
      | /////
      |  o  0   par    -> fuera (bajo el solido)

Para no probar celda por celda se trabaja por columnas: cada triangulo se
proyecta en planta, se calcula a que altura lo cruza cada columna (x, y) y se
marca ese cruce. Una suma acumulada a lo largo de z da los cruces bajo cada
centro. El intervalo es semiabierto, [z_abajo, z_arriba): un centro justo en la
interfaz entre dos vertidas pertenece solo a la de arriba.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .bim import SolidoVertida
from .grid import Grid

FUERA = -1

# Corrimiento de los rayos, muy inferior a dx: evita que un rayo pase exactamente
# por una arista compartida por dos triangulos, donde se contaria dos veces.
_RAYO_DX = 1.37e-7
_RAYO_DY = 0.71e-7
_DECIMALES_Z = 9


@dataclass
class Voxelizacion:
    """Resultado: la grilla y la vertida a la que pertenece cada celda."""

    grid: Grid
    vertida_id: np.ndarray             # shape = grid.shape; FUERA (-1) si no hay hormigon
    solidos: list[SolidoVertida]
    solapes: int = 0                   # celdas reclamadas por mas de un solido

    @property
    def mask(self) -> np.ndarray:
        return self.vertida_id != FUERA

    def volumen_voxel(self, vertida_id: int | None = None) -> float:
        """V_h = N_activo * dx * dy * dz, total o de una vertida."""
        seleccion = self.mask if vertida_id is None else self.vertida_id == vertida_id
        return int(seleccion.sum()) * self.grid.cell_volume

    def volumen_geometrico(self, vertida_id: int | None = None) -> float:
        return sum(
            s.volumen for s in self.solidos if vertida_id is None or s.vertida_id == vertida_id
        )

    def error_volumen(self, vertida_id: int | None = None) -> float:
        """e_V = |V_h - V_geom| / V_geom."""
        v_geom = self.volumen_geometrico(vertida_id)
        return abs(self.volumen_voxel(vertida_id) - v_geom) / v_geom


def _contar_cruces(verts, faces, x, y, z) -> np.ndarray:
    """Marca en cruces[i, j, k] cada cruce de la columna (i, j) a la altura de la celda k."""
    cruces = np.zeros((x.size, y.size, z.size + 1), dtype=np.int32)
    xr, yr = x + _RAYO_DX, y + _RAYO_DY
    z_redondeado = np.round(z, _DECIMALES_Z)

    for tri in verts[faces]:
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
        doble_area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(doble_area) < 1e-12:
            continue                   # cara vertical: un rayo vertical no la cruza

        i0, i1 = np.searchsorted(xr, [min(x0, x1, x2), max(x0, x1, x2)])
        j0, j1 = np.searchsorted(yr, [min(y0, y1, y2), max(y0, y1, y2)])
        if i0 == i1 or j0 == j1:
            continue
        X, Y = np.meshgrid(xr[i0:i1], yr[j0:j1], indexing="ij")

        # Coordenadas baricentricas en planta: las tres >= 0 si (X, Y) cae en el triangulo
        w1 = ((X - x0) * (y2 - y0) - (x2 - x0) * (Y - y0)) / doble_area
        w2 = ((x1 - x0) * (Y - y0) - (X - x0) * (y1 - y0)) / doble_area
        w0 = 1.0 - w1 - w2
        adentro = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not np.any(adentro):
            continue

        z_cruce = np.round(w0[adentro] * z0 + w1[adentro] * z1 + w2[adentro] * z2, _DECIMALES_Z)
        ii, jj = np.nonzero(adentro)
        # Primera celda cuyo centro queda en o sobre el cruce: desde ahi el cruce esta "abajo"
        kk = np.searchsorted(z_redondeado, z_cruce, side="left")
        np.add.at(cruces, (ii + i0, jj + j0, kk), 1)
    return cruces


def centros_dentro(verts: np.ndarray, faces: np.ndarray, grid: Grid) -> np.ndarray:
    """Mascara de las celdas cuyo centro esta dentro de la malla cerrada."""
    x, y, z = grid.centers()
    cruces = _contar_cruces(verts, faces, x, y, z)
    if np.any(cruces.sum(axis=2) % 2):
        raise ValueError("Una columna cruza la malla un numero impar de veces: malla abierta.")
    return np.cumsum(cruces, axis=2)[:, :, :-1] % 2 == 1


def _grid_para(solidos: list[SolidoVertida], dx: float, dy: float, dz: float) -> Grid:
    """Grilla con caras en multiplos de dx: si el solido parte en z = 0, la base calza."""
    verts = np.vstack([s.verts for s in solidos])
    lo, hi = verts.min(axis=0), verts.max(axis=0)

    def limites(a: float, b: float, d: float) -> tuple[int, int]:
        return math.floor(a / d + 1e-9), math.ceil(b / d - 1e-9)

    i0, i1 = limites(lo[0], hi[0], dx)
    j0, j1 = limites(lo[1], hi[1], dy)
    k0, k1 = limites(lo[2], hi[2], dz)
    return Grid(
        nx=i1 - i0, ny=j1 - j0, nz=k1 - k0,
        dx=dx, dy=dy, dz=dz,
        x0=i0 * dx, y0=j0 * dy, z0=k0 * dz,
    )


def voxelizar(
    solidos: list[SolidoVertida],
    dx: float,
    dy: float | None = None,
    dz: float | None = None,
) -> Voxelizacion:
    """Asigna cada celda a la vertida que contiene su centro."""
    grid = _grid_para(solidos, dx, dy or dx, dz or dx)
    vertida_id = np.full(grid.shape, FUERA, dtype=int)
    solapes = 0
    for solido in solidos:
        dentro = centros_dentro(solido.verts, solido.faces, grid)
        libres = vertida_id == FUERA
        solapes += int((dentro & ~libres).sum())
        vertida_id[dentro & libres] = solido.vertida_id
    return Voxelizacion(grid=grid, vertida_id=vertida_id, solidos=solidos, solapes=solapes)


def dz_que_calza(solidos: list[SolidoVertida], dx: float) -> float:
    """dz mas cercano a dx con el que las interfaces entre vertidas caen en caras de celda.

    Si una interfaz cae dentro de una celda, esa celda queda entera en una de las dos
    vertidas: el volumen total casi no cambia, pero el de cada vertida (y con el, el
    calor y el momento en que entra) si. La cara superior de la ultima vertida no se
    exige: solo calza con dz muy chicos y su error queda en esa vertida.
    """
    interfaces = sorted({round(float(s.verts[:, 2].min()), 6) for s in solidos})
    base = interfaces[0]
    alturas = [z - base for z in interfaces[1:]]
    if not alturas:
        return dx
    mejor = dx
    for n in range(1, 2 + int(alturas[0] / min(dx, alturas[0]) * 2)):
        d = alturas[0] / n
        if all(abs(h / d - round(h / d)) < 1e-6 for h in alturas):
            if mejor == dx or abs(d - dx) < abs(mejor - dx):
                mejor = d
    return mejor


def area_expuesta(mask: np.ndarray, grid: Grid) -> float:
    """Area de las caras entre una celda de hormigon y el exterior (la escalera)."""
    total = 0.0
    for axis in range(3):
        relleno = [(0, 0)] * 3
        relleno[axis] = (1, 1)
        cambios = np.diff(np.pad(mask.astype(np.int8), relleno), axis=axis)
        total += np.count_nonzero(cambios) * grid.face_area(axis)
    return total


def area_exterior(solidos: list[SolidoVertida]) -> float:
    """Area real de la superficie exterior de la union de las vertidas.

    Las caras inclinadas y verticales son siempre exteriores. En cada plano
    horizontal se descuenta lo que queda tapado: |area que mira arriba - area que
    mira abajo|. Supone vertidas apiladas, cada una apoyada en la de abajo.
    """
    total = 0.0
    planos: dict[float, float] = {}
    for solido in solidos:
        a, b, c = (solido.verts[solido.faces[:, n]] for n in range(3))
        normal = np.cross(b - a, c - a)
        areas = 0.5 * np.linalg.norm(normal, axis=1)
        z_tri = np.stack([a[:, 2], b[:, 2], c[:, 2]], axis=1)
        horizontal = np.ptp(z_tri, axis=1) < 1e-9
        total += float(areas[~horizontal].sum())
        for area, n_z, z in zip(areas[horizontal], normal[horizontal, 2], z_tri[horizontal, 0]):
            clave = round(float(z), 6)
            planos[clave] = planos.get(clave, 0.0) + float(area) * (1.0 if n_z > 0 else -1.0)
    return total + sum(abs(v) for v in planos.values())
