"""Grilla cartesiana uniforme y utilidades de seleccion de celdas."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid:
    """Grilla cartesiana de paso uniforme."""

    nx: int
    ny: int
    nz: int
    dx: float
    dy: float
    dz: float
    x0: float = 0.0
    y0: float = 0.0
    z0: float = 0.0

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.nx, self.ny, self.nz)

    @property
    def n_cells(self) -> int:
        return self.nx * self.ny * self.nz

    @property
    def cell_volume(self) -> float:
        return self.dx * self.dy * self.dz

    def axis_length(self, axis: int) -> float:
        return (self.dx, self.dy, self.dz)[axis]

    def centers(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Coordenadas de los centros de celda en cada direccion."""
        x = self.x0 + (np.arange(self.nx) + 0.5) * self.dx
        y = self.y0 + (np.arange(self.ny) + 0.5) * self.dy
        z = self.z0 + (np.arange(self.nz) + 0.5) * self.dz
        return x, y, z

    def flat_index(self, i: np.ndarray, j: np.ndarray, k: np.ndarray) -> np.ndarray:
        return (i * self.ny + j) * self.nz + k

    def unravel(self, flat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        k = flat % self.nz
        rest = flat // self.nz
        j = rest % self.ny
        i = rest // self.ny
        return i, j, k

    def face_area(self, axis: int) -> float:
        """Area de una cara perpendicular al eje indicado."""
        if axis == 0:
            return self.dy * self.dz
        if axis == 1:
            return self.dx * self.dz
        return self.dx * self.dy


def box_mask(grid: Grid, x_range, y_range, z_range) -> np.ndarray:
    """Mascara booleana de las celdas cuyo centro cae dentro de la caja."""
    x, y, z = grid.centers()
    mask = (
        ((x >= x_range[0]) & (x <= x_range[1]))[:, None, None]
        & ((y >= y_range[0]) & (y <= y_range[1]))[None, :, None]
        & ((z >= z_range[0]) & (z <= z_range[1]))[None, None, :]
    )
    return mask.copy()


def erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Erosion binaria: celdas a distancia mayor o igual a `iterations` del exterior."""
    result = mask.copy()
    for _ in range(iterations):
        shrunk = result.copy()
        shrunk[0, :, :] = False
        shrunk[-1, :, :] = False
        shrunk[:, 0, :] = False
        shrunk[:, -1, :] = False
        shrunk[:, :, 0] = False
        shrunk[:, :, -1] = False
        shrunk[:-1, :, :] &= result[1:, :, :]
        shrunk[1:, :, :] &= result[:-1, :, :]
        shrunk[:, :-1, :] &= result[:, 1:, :]
        shrunk[:, 1:, :] &= result[:, :-1, :]
        shrunk[:, :, :-1] &= result[:, :, 1:]
        shrunk[:, :, 1:] &= result[:, :, :-1]
        result = shrunk
    return result


def surface_cells(mask: np.ndarray, include_bottom: bool = False) -> np.ndarray:
    """Celdas con al menos una cara expuesta (fuera de la mascara)."""
    exposed = np.zeros_like(mask)
    exposed[:-1, :, :] |= ~mask[1:, :, :]
    exposed[1:, :, :] |= ~mask[:-1, :, :]
    exposed[:, :-1, :] |= ~mask[:, 1:, :]
    exposed[:, 1:, :] |= ~mask[:, :-1, :]
    exposed[:, :, :-1] |= ~mask[:, :, 1:]
    exposed[:, :, 1:] |= ~mask[:, :, :-1]
    if not include_bottom:
        exposed[:, :, 0] = False
    return mask & exposed


def core_cells(mask: np.ndarray, erosion: int = 2) -> np.ndarray:
    """Nucleo interior de la geometria (erosion de la mascara)."""
    return erode(mask, erosion)
