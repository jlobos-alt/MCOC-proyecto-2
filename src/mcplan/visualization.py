"""Visualizacion 3D con PyVista/VTK: exportar campos y ver las vertidas (E08).

BIM != solver != visualizador: este modulo solo recibe la grilla, `vertida_id` y campos
de temperatura ya calculados. PyVista se importa aqui dentro, asi que el solver funciona
aunque PyVista no este instalado.

Una grilla cartesiana uniforme es exactamente un `pyvista.ImageData` (dimensiones,
spacing, origen). Los datos van por celda y en orden Fortran, que es el de VTK.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .grid import Grid


def a_image_data(grid: Grid, vertida_id: np.ndarray, T: np.ndarray | None = None):
    """Grilla como ImageData, con vertida_id y, si se da, temperatura por celda."""
    import pyvista as pv

    malla = pv.ImageData(
        dimensions=(grid.nx + 1, grid.ny + 1, grid.nz + 1),
        spacing=(grid.dx, grid.dy, grid.dz),
        origin=(grid.x0, grid.y0, grid.z0),
    )
    malla.cell_data["vertida_id"] = np.asarray(vertida_id).ravel(order="F")
    if T is not None:
        malla.cell_data["temperature"] = np.asarray(T, dtype=float).ravel(order="F")
    return malla


def guardar_serie(carpeta, grid: Grid, vertida_id: np.ndarray, campos: dict[float, np.ndarray]) -> list[Path]:
    """Guarda temperature_XXXXh.vti por instante y serie.pvd para abrir todo en ParaView."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = []
    filas = []
    for t_h in sorted(campos):
        ruta = carpeta / f"temperature_{t_h:07.1f}h.vti"
        a_image_data(grid, vertida_id, campos[t_h]).save(str(ruta))
        archivos.append(ruta)
        filas.append(f'    <DataSet timestep="{t_h:g}" file="{ruta.name}"/>')
    (carpeta / "serie.pvd").write_text(
        '<?xml version="1.0"?>\n<VTKFile type="Collection" version="0.1">\n  <Collection>\n'
        + "\n".join(filas) + "\n  </Collection>\n</VTKFile>\n",
        encoding="utf-8",
    )
    return archivos


class VisorVertidas:
    """Muestra cada vertida como una pieza separada que se puede ocultar o mostrar.

    La logica (`alternar`, `fijar_tiempo`, `fijar_corte`, `captura`) es independiente de la
    ventana: los botones y las teclas solo llaman a estos metodos, y por eso se puede probar
    y generar imagenes sin abrir nada (`off_screen=True`).

    Una vertida aun no colocada tiene T = NaN en todas sus celdas: no se dibuja, aunque
    este marcada como visible. Asi se ve la activacion en el tiempo.
    """

    def __init__(self, grid: Grid, vertida_id: np.ndarray, campos: dict[float, np.ndarray],
                 off_screen: bool = False, clim: tuple[float, float] | None = None,
                 tamano: tuple[int, int] = (1250, 850)):
        import pyvista as pv

        self.tiempos = sorted(campos)
        self.campos = campos
        self.ids = [int(v) for v in np.unique(vertida_id) if v >= 0]
        self.visible = {v: True for v in self.ids}
        self.corte = False
        self.t = self.tiempos[-1]
        self._casillas = {}             # botones de la ventana: se mantienen al dia con las teclas
        if clim is None:
            maximo = max(float(np.nanmax(T)) for T in campos.values() if np.isfinite(T).any())
            clim = (10.0, float(np.ceil(maximo / 5.0) * 5.0))

        base = a_image_data(grid, vertida_id, campos[self.t])
        _, y, _ = grid.centers()
        plano = grid.y0 + grid.ny * grid.dy / 2.0     # plano medio; en la fundacion es y = 0
        # Se deja la mitad lejana a la camara, para que la cara cortada quede a la vista
        media = np.broadcast_to(y[None, :, None] >= plano, grid.shape).ravel(order="F")
        ids_f = np.asarray(vertida_id).ravel(order="F")

        self.plotter = pv.Plotter(off_screen=off_screen, window_size=tamano)
        self.plotter.set_background("white")
        self.piezas = {}
        barra = True
        for v in self.ids:
            for modo, seleccion in (("entera", ids_f == v), ("media", (ids_f == v) & media)):
                malla = base.extract_cells(np.flatnonzero(seleccion))
                actor = self.plotter.add_mesh(
                    malla, scalars="temperature", cmap="inferno", clim=clim, nan_color="#d9d9d9",
                    show_scalar_bar=barra,
                    scalar_bar_args={"title": "T [°C]", "color": "black", "vertical": True, "position_x": 0.88,
                                     "position_y": 0.25, "height": 0.5, "width": 0.07, "n_labels": 6, "fmt": "%.0f"},
                )
                barra = False
                self.piezas[(v, modo)] = (malla, actor)
        self.plotter.camera_position = [(27.0, -31.0, 19.0), (0.0, 0.0, 1.9), (0.0, 0.0, 1.0)]
        self._dibujar()

    # ------------------------------------------------------------ logica sin ventana
    def _instante(self, t_h: float) -> float:
        return min(self.tiempos, key=lambda x: abs(x - t_h))

    def _colocada(self, v: int) -> bool:
        malla, _ = self.piezas[(v, "entera")]
        return bool(np.isfinite(malla.cell_data["temperature"]).any())

    def vertidas_dibujadas(self) -> list[int]:
        """Las que se ven ahora: marcadas como visibles y ya colocadas en este instante."""
        return [v for v in self.ids if self.visible[v] and self._colocada(v)]

    def _dibujar(self) -> None:
        T = self.campos[self.t].ravel(order="F")
        for malla, _ in self.piezas.values():
            malla.cell_data["temperature"] = T[malla.cell_data["vtkOriginalCellIds"]]
        for (v, modo), (_, actor) in self.piezas.items():
            modo_activo = "media" if self.corte else "entera"
            actor.SetVisibility(modo == modo_activo and self.visible[v] and self._colocada(v))
        dibujadas = self.vertidas_dibujadas()
        if dibujadas:
            vistos = np.concatenate([self.piezas[(v, "entera")][0].cell_data["temperature"] for v in dibujadas])
            maximo = f"{np.nanmax(vistos):.1f} °C"
        else:
            maximo = "-"
        self.plotter.add_text(
            f"t = {self.t:.0f} h   vertidas: {dibujadas}   T máx visible: {maximo}",
            position="upper_edge", font_size=11, color="black", name="estado",
        )

    def alternar(self, v: int, visible: bool | None = None) -> None:
        self.visible[v] = (not self.visible[v]) if visible is None else bool(visible)
        self._sincronizar(v, self.visible[v])
        self._dibujar()

    def fijar_tiempo(self, t_h: float) -> None:
        self.t = self._instante(t_h)
        self._dibujar()

    def fijar_corte(self, activo: bool) -> None:
        """Muestra solo la mitad de la grilla en y, para ver el interior."""
        self.corte = bool(activo)
        self._sincronizar("corte", self.corte)
        self._dibujar()

    def _sincronizar(self, clave, estado: bool) -> None:
        casilla = self._casillas.get(clave)
        if casilla is not None:
            casilla.GetRepresentation().SetState(int(estado))

    def captura(self, ruta) -> None:
        self.plotter.screenshot(str(ruta))

    def cerrar(self) -> None:
        self.plotter.close()

    # ------------------------------------------------------------ ventana interactiva
    def abrir(self) -> None:
        """Abre la ventana: casillas o teclas 1-9 para las vertidas, x para el corte, barra para t."""
        self.crear_controles()
        self.plotter.show()

    def crear_controles(self) -> None:
        for i, v in enumerate(self.ids):
            y = self.plotter.window_size[1] - 90 - 45 * i
            self._casillas[v] = self.plotter.add_checkbox_button_widget(
                lambda estado, v=v: self.alternar(v, estado), value=self.visible[v], position=(12, y), size=34,
                color_on="#2a9d8f", color_off="#bbbbbb",
            )
            self.plotter.add_text(f"Vertida {v} (tecla {v})", position=(54, y + 8), font_size=10, color="black",
                                  name=f"etiqueta{v}")
            self.plotter.add_key_event(str(v), lambda v=v: self.alternar(v))
        y = self.plotter.window_size[1] - 90 - 45 * len(self.ids)
        self._casillas["corte"] = self.plotter.add_checkbox_button_widget(
            lambda estado: self.fijar_corte(estado), value=self.corte, position=(12, y), size=34,
            color_on="#e76f51", color_off="#bbbbbb",
        )
        self.plotter.add_text("Corte en y = 0 (tecla x)", position=(54, y + 8), font_size=10, color="black",
                              name="etiqueta_corte")
        self.plotter.add_key_event("x", lambda: self.fijar_corte(not self.corte))
        self.plotter.add_slider_widget(
            lambda t: self.fijar_tiempo(t), rng=(self.tiempos[0], self.tiempos[-1]), value=self.t,
            title="t [h]", pointa=(0.3, 0.07), pointb=(0.9, 0.07), color="black", fmt="%.0f",
            style="modern", interaction_event="always",
        )
