"""E12 - Simulacion determinista de 14 dias (336 h) con una sola curva de hidratacion.

Un unico caso, sin variantes: el plan de vertidas del IFC, el clima de los
snapshots y la curva C1. El script produce todo lo que pide la entrega:

  [1] snapshots y clima hora a hora, con la fuente de cada tramo
  [2] plan de vertidas y condicion inicial
  [3] condicion de borde Robin alimentada por la serie (h(t), T infinito(t))
  [4] simulacion 3D de 336 h, malla de 0,5 m
  [5] T_max y delta_T_max con su instante y su celda
  [6] curvas nucleo/superficie
  [7] figuras 3D y serie .vti/.pvd para ParaView
  [8] resumen JSON, series CSV y tablas de borde

Curva de hidratacion: C1 (la unica del caso)

    theta_ad(t) = 45 C * (1 - exp(-t / 30 h))

con madurez de Arrhenius Ea/R = 4000 K y T_ref = 20 C. No hay segunda rama
exponencial. Cambiar de curva es editar `datos/fundacion_e12.yaml`; la fisica
no cambia.

Uso (desde entregas/entrega12):
    python scripts/e12_determinista.py                 # 336 h, dx = 0,5 m
    python scripts/e12_determinista.py --dx 1.0        # malla mas gruesa
    python scripts/e12_determinista.py --sin-3d        # omite PyVista
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan import (  # noqa: E402
    aplicar_ambiente,
    assemble_timeline,
    build_model,
    condiciones_de_timeline,
    dz_que_calza,
    evaluar_criterios,
    extraer_solidos,
    latest_snapshot,
    load_plan,
    load_snapshot,
    plan_desde_solidos,
    solve,
    verify,
    voxelizar,
)
from mcplan.hydration import HydrationModel  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Eje temporal del caso: primera vertida del IFC (viernes 27-nov-2026, 04:00 local).
INICIO_LOCAL = "2026-11-27T04:00:00"
ABSORTIVIDAD = 0.6      # hormigon visto: alfa ~ 0.6
EMISIVIDAD = 0.9        # hormigon: eps ~ 0.9

AZUL = "#2b6cb0"
VERDE = "#2f9e44"
ROJO = "#c92a2a"
GRIS = "#6c757d"
NARANJA = "#e76f51"


def titulo(n: int, texto: str) -> None:
    print(f"\n[{n}] {texto}")


def fecha_local(t_h: float) -> str:
    return (datetime.fromisoformat(INICIO_LOCAL) + timedelta(hours=float(t_h))).isoformat(
        timespec="minutes"
    )


# ---------------------------------------------------------------------------
# [1] Snapshots y clima
# ---------------------------------------------------------------------------


def leer_clima(carpeta: Path):
    verificados = verify(carpeta)
    meta_f = latest_snapshot(carpeta, "open-meteo-forecast")
    meta_a = latest_snapshot(carpeta, "open-meteo-archive")
    if meta_f is None or meta_a is None:
        raise SystemExit("Faltan snapshots de forecast o de archivo en datos/forecast.")
    forecast = load_snapshot(carpeta, meta_f.snapshot_id)[0]
    archivo = load_snapshot(carpeta, meta_a.snapshot_id)[0]
    return forecast, meta_f, archivo, meta_a, verificados


def imprimir_clima(meta_f, meta_a, timeline, verificados) -> None:
    titulo(1, "Clima: snapshots y cobertura del horizonte")
    print(f"    forecast : {meta_f.snapshot_id}")
    print(f"               emitido {meta_f.issued_at} · horizonte {meta_f.first_time} -> "
          f"{meta_f.last_time} ({meta_f.n_hours} h)")
    print(f"               SHA-256 csv {meta_f.sha256_csv[:16]}...")
    print(f"    archivo  : {meta_a.snapshot_id}")
    print(f"               horizonte {meta_a.first_time} -> {meta_a.last_time} "
          f"({meta_a.n_hours} h) · SHA-256 csv {meta_a.sha256_csv[:16]}...")
    print(f"    Hashes verificados: {len(verificados)} snapshot(s) sin alteraciones")
    print(f"    Ventana simulada  : {INICIO_LOCAL} -> {timeline.points[-1].time_local} "
          f"({len(timeline) - 1:g} h)")
    print(f"    Fuente por hora   : {dict(timeline.sources)}")
    print("    El forecast del 11-nov termina el 24-nov y no cubre la primera vertida:")
    print("    0 h de forecast y las 337 h de climatologia del mismo calendario (2025-11-27")
    print("    -> 2025-12-11) desplazada al anio del caso. Cada fila del CSV lo declara.")


def figura_clima(timeline, suelo, h_fn, t_fn, carpeta: Path) -> None:
    t = np.array([p.t_h for p in timeline.points])
    T_aire = np.array([p.temperature_C for p in timeline.points])
    T_sa = np.array([t_fn(x) for x in t])
    T_suelo = np.array([suelo.temperature(x) for x in t])
    viento = np.array([p.wind_ms for p in timeline.points])
    solar = np.array([p.solar_W_m2 for p in timeline.points])
    h_total = np.array([h_fn(x) for x in t])
    fuentes = [p.source for p in timeline.points]

    fig, ejes = plt.subplots(3, 1, figsize=(12.5, 8.2), sharex=True,
                             gridspec_kw={"height_ratios": [2.0, 1.15, 1.0]})
    ax = ejes[0]
    ax.axvspan(0, t[-1], color="#f7e6c4", alpha=0.55, zorder=0)
    ax.plot(t, T_aire, color=AZUL, lw=1.5, label="T aire (2 m)")
    ax.plot(t, T_sa, color=NARANJA, lw=1.7, label="T sol-aire (lo que ve el Robin)")
    ax.plot(t, T_suelo, color=VERDE, lw=1.4, ls="--", label="T suelo a 1 m")
    ax.set(ylabel="T [°C]", title="Clima del caso: 336 h desde la primera vertida (climatología)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right", ncol=3)
    ax.text(0.01, 0.95, f"fuente: {', '.join(sorted(set(fuentes)))}",
            transform=ax.transAxes, fontsize=8, color="#555", va="top")

    ax = ejes[1]
    ax.plot(t, viento, color="#264653", lw=1.5, label="viento [m/s]")
    ax.set(ylabel="v [m/s]")
    ax2 = ax.twinx()
    ax2.plot(t, h_total, color="#e9c46a", lw=1.6, label="h total [W/(m²·K)]")
    ax2.set_ylabel("h [W/(m²·K)]")
    lineas = ax.get_lines() + ax2.get_lines()
    ax.legend(lineas, [ln.get_label() for ln in lineas], fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)

    ax = ejes[2]
    ax.plot(t, solar, color="#f4a261", lw=1.4, label="G solar [W/m²]")
    ax.set(xlabel="t desde la primera vertida [h]", ylabel="G [W/m²]")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")

    for a in ejes:
        for h in (24, 72, 168, 336):
            a.axvline(h, color="#999", lw=0.6, ls=":")
        for llamada, texto in ((0, "V1"), (6, "V2"), (12, "V3"), (18, "V4"), (24, "V5")):
            ejes[0].axvline(llamada, color=ROJO, lw=0.8, alpha=0.7)

    fig.tight_layout()
    fig.savefig(carpeta / "e12_clima.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figuras de hidratacion y criterios
# ---------------------------------------------------------------------------


def figura_hidratacion(plantilla, carpeta: Path) -> None:
    titulo(2, "Curva de hidratacion C1 (unica del caso)")
    h = HydrationModel(
        theta_inf_1_C=plantilla.hidratacion.elevacion_adibatica_C,
        tau_1_h=plantilla.hidratacion.tau_h,
        theta_inf_2_C=plantilla.hidratacion.elevacion_adibatica_2_C,
        tau_2_h=plantilla.hidratacion.tau_2_h,
        activation_temperature_K=(
            plantilla.hidratacion.energia_activacion_K if plantilla.hidratacion.madurez else 0.0
        ),
    )
    rho_cp = 2400.0 * 970.0
    edad = np.linspace(0.0, 336.0, 2000)
    theta = h.theta(edad)
    qdot = h.heat_rate(edad, volumetric_heat_capacity=rho_cp)
    qdot_40 = h.heat_rate(edad, temperature_C=40.0, volumetric_heat_capacity=rho_cp)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.6, 4.4))
    a1.plot(edad, theta, color=ROJO, lw=2.0, label="θ_ad(t) = 45·(1 − e^(−t/30))")
    a1.axhline(45, color=GRIS, ls=":", lw=1.0)
    a1.text(336, 45.6, "θ∞ = 45 °C", ha="right", fontsize=8, color="#555")
    for marca, texto in ((24, "24 h"), (72, "72 h"), (168, "168 h"), (336, "336 h")):
        a1.plot([marca], [float(h.theta(marca))], "o", ms=4, color=ROJO)
        a1.annotate(f"{texto}: {float(h.theta(marca)):.1f} °C", (marca, float(h.theta(marca))),
                    textcoords="offset points", xytext=(6, -12), fontsize=7)
    a1.set(xlabel="edad del hormigón [h]", ylabel="elevación adiabática [°C]",
           title="Curva C1: una sola exponencial, τ = 30 h")
    a1.grid(alpha=0.3)
    a1.legend(fontsize=8)

    a2.plot(edad, qdot / 1e3, color=AZUL, lw=2.0, label="q̇ a 20 °C")
    a2.plot(edad, qdot_40 / 1e3, color=NARANJA, lw=1.6, ls="--", label="q̇ a 40 °C (madurez)")
    a2.set(xlabel="edad [h]", ylabel="q̇ [kW/m³]",
           title="Calor volumétrico: ρ·cp·dθ/dt·m(T)")
    a2.grid(alpha=0.3)
    a2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(carpeta / "e12_curva_c1.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"    θ_ad(24 h) = {float(h.theta(24.0)):.2f} °C, θ_ad(168 h) = {float(h.theta(168.0)):.2f} °C")
    print(f"    q̇(0) = {float(h.heat_rate(0.0, volumetric_heat_capacity=rho_cp)) / 1e3:.2f} kW/m³")


def figura_criterios(r, t_T, t_dT, carpeta: Path) -> None:
    t = np.asarray(r.time_h)
    T = np.asarray(r.T_max_global)
    dT = np.asarray(r.delta_T)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.0, 4.6))
    a1.plot(t, T, color=ROJO, lw=1.8, label="T máx global")
    a1.axhline(70, color=GRIS, ls=":", lw=1.1)
    a1.axvline(t_T, color=ROJO, lw=0.7, ls="--", alpha=0.6)
    a1.plot([t_T], [np.nanmax(T)], "o", color=ROJO, ms=6)
    a1.annotate(f"máx {np.nanmax(T):.2f} °C\n{t_T:g} h", (t_T, np.nanmax(T)),
                textcoords="offset points", xytext=(8, -18), fontsize=8, color=ROJO)
    a1.set(xlabel="t [h]", ylabel="T [°C]", title="Criterio T_max ≤ 70 °C")
    a1.grid(alpha=0.3)
    a1.legend(fontsize=8, loc="lower right")

    a2.plot(t, dT, color=AZUL, lw=1.8, label="ΔT = núcleo − superficie")
    a2.axhline(20, color=GRIS, ls=":", lw=1.1)
    a2.axvline(t_dT, color=AZUL, lw=0.7, ls="--", alpha=0.6)
    a2.plot([t_dT], [np.nanmax(dT)], "o", color=AZUL, ms=6)
    a2.annotate(f"máx {np.nanmax(dT):.2f} °C\n{t_dT:g} h", (t_dT, np.nanmax(dT)),
                textcoords="offset points", xytext=(8, -20), fontsize=8, color=AZUL)
    a2.set(xlabel="t [h]", ylabel="ΔT [°C]", title="Criterio ΔT ≤ 20 °C")
    a2.grid(alpha=0.3)
    a2.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(carpeta / "e12_criterios.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def figura_nucleo_superficie(r, t_T, t_dT, carpeta: Path) -> None:
    t = np.asarray(r.time_h)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12.6, 7.4), sharex=True,
                                 gridspec_kw={"height_ratios": [1.7, 1.0]})
    a1.plot(t, r.T_max_core, color=ROJO, lw=1.7, label="T máx núcleo")
    a1.plot(t, r.T_min_surface, color=VERDE, lw=1.7, label="T mín superficie")
    a1.plot(t, r.T_mean, color=GRIS, lw=1.1, label="T media del hormigón")
    a1.axhline(70, color=GRIS, ls=":", lw=1.0)
    a1.axvline(t_T, color=ROJO, ls="--", lw=0.8, alpha=0.7)
    a1.annotate(f"T_max = {np.nanmax(r.T_max_global):.2f} °C @ {t_T:g} h",
                (t_T, np.nanmax(r.T_max_core)), textcoords="offset points", xytext=(8, 4),
                fontsize=8, color=ROJO)
    a1.set(ylabel="T [°C]", title="Curvas núcleo/superficie y criterio de 70 °C")
    a1.grid(alpha=0.3)
    a1.legend(fontsize=8, loc="upper right")

    a2.plot(t, r.delta_T, color=AZUL, lw=1.8, label="ΔT = T máx núcleo − T mín superficie")
    a2.axhline(20, color=ROJO, ls=":", lw=1.2)
    a2.text(t[-1], 20.6, "límite 20 °C", ha="right", fontsize=8, color=ROJO)
    a2.fill_between(t, 20, r.delta_T, where=(np.asarray(r.delta_T) > 20),
                    color=AZUL, alpha=0.18, interpolate=True)
    a2.axvline(t_dT, color=AZUL, ls="--", lw=0.8, alpha=0.7)
    a2.annotate(f"ΔT_max = {np.nanmax(r.delta_T):.2f} °C @ {t_dT:g} h",
                (t_dT, np.nanmax(r.delta_T)), textcoords="offset points", xytext=(8, -18),
                fontsize=8, color=AZUL)
    a2.set(xlabel="t desde la primera vertida [h]", ylabel="ΔT [°C]",
           title="ΔT con el criterio de 20 °C")
    a2.grid(alpha=0.3)
    a2.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(carpeta / "e12_nucleo_superficie.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# [5] Localizacion de maximos
# ---------------------------------------------------------------------------


def _campo_en(r, t_h: float) -> np.ndarray:
    clave = min(r.campos, key=lambda x: abs(x - t_h))
    return r.campos[clave]


def localizar(modelo, vox, r, t_T: float, t_dT: float) -> dict:
    forma = modelo.grid.shape
    X, Y, Z = np.meshgrid(*modelo.grid.centers(), indexing="ij")
    vid = vox.vertida_id

    campo_T = _campo_en(r, t_T)
    idx = int(np.nanargmax(campo_T))
    i = np.unravel_index(idx, forma)
    tmax = {
        "T_C": round(float(campo_T[i]), 3),
        "t_h": float(t_T),
        "time_local": fecha_local(t_T),
        "x_m": round(float(X[i]), 3),
        "y_m": round(float(Y[i]), 3),
        "z_m": round(float(Z[i]), 3),
        "vertida": int(vid[i]),
    }

    campo_d = _campo_en(r, t_dT)
    nucleo = modelo.is_core.reshape(forma) & np.isfinite(campo_d)
    superficie = modelo.is_surface.reshape(forma) & np.isfinite(campo_d)
    i_c = np.unravel_index(int(np.nanargmax(np.where(nucleo, campo_d, np.nan))), forma)
    i_s = np.unravel_index(int(np.nanargmin(np.where(superficie, campo_d, np.nan))), forma)
    dmax = {
        "delta_T_C": round(float(campo_d[i_c] - campo_d[i_s]), 3),
        "t_h": float(t_dT),
        "time_local": fecha_local(t_dT),
        "nucleo": {
            "T_C": round(float(campo_d[i_c]), 3),
            "x_m": round(float(X[i_c]), 3), "y_m": round(float(Y[i_c]), 3),
            "z_m": round(float(Z[i_c]), 3), "vertida": int(vid[i_c]),
        },
        "superficie": {
            "T_C": round(float(campo_d[i_s]), 3),
            "x_m": round(float(X[i_s]), 3), "y_m": round(float(Y[i_s]), 3),
            "z_m": round(float(Z[i_s]), 3), "vertida": int(vid[i_s]),
        },
    }
    return {"T_max": tmax, "delta_T_max": dmax}


def por_vertida(modelo, vox, r) -> dict:
    """Maximo de cada vertida recorriendo los campos horarios guardados."""
    forma = modelo.grid.shape
    X, Y, Z = np.meshgrid(*modelo.grid.centers(), indexing="ij")
    vid = vox.vertida_id
    salida: dict[str, dict] = {}
    for v in range(1, int(np.nanmax(vid)) + 1):
        mascara = vid == v
        mejor = (-np.inf, float("nan"), None)
        for t, campo in sorted(r.campos.items()):
            valores = np.where(mascara, campo, np.nan)
            if not np.isfinite(valores).any():
                continue
            m = float(np.nanmax(valores))
            if m > mejor[0]:
                mejor = (m, float(t), np.unravel_index(int(np.nanargmax(valores)), forma))
        if mejor[2] is None:
            continue
        i = mejor[2]
        salida[str(v)] = {
            "T_max_C": round(mejor[0], 3), "t_h": mejor[1], "time_local": fecha_local(mejor[1]),
            "x_m": round(float(X[i]), 2), "y_m": round(float(Y[i]), 2), "z_m": round(float(Z[i]), 2),
        }
    return salida


# ---------------------------------------------------------------------------
# [7] 3D
# ---------------------------------------------------------------------------


def _plano_3d(ax, X, Y, Z, T, cmap, norm) -> None:
    """Superficie coloreada con la temperatura; transparente donde no hay hormigon."""
    colores = cmap(norm(np.nan_to_num(T, nan=norm.vmin)))
    colores[..., 3] = np.where(np.isfinite(T), 1.0, 0.0)
    ax.plot_surface(X, Y, Z, facecolors=colores, rstride=1, cstride=1,
                    shade=False, linewidth=0, antialiased=False)


def _vista_3d(ax, modelo, campo, cmap, norm, titulo_ax: str) -> None:
    """Tres cortes ortogonales (x=0, y=0, z medio) del campo de temperatura."""
    xc, yc, zc = modelo.grid.centers()
    j = int(np.argmin(np.abs(xc - 0.0)))
    i = int(np.argmin(np.abs(yc - 0.0)))
    k = int(np.argmin(np.abs(zc - 1.6)))
    X, Y = np.meshgrid(xc, yc, indexing="ij")
    Z = np.full_like(X, zc[k])
    _plano_3d(ax, X, Y, Z, campo[:, :, k], cmap, norm)

    Yp, Zp = np.meshgrid(yc, zc, indexing="ij")
    Xp = np.full_like(Yp, xc[j])
    _plano_3d(ax, Xp, Yp, Zp, campo[j, :, :], cmap, norm)

    Xp, Zp = np.meshgrid(xc, zc, indexing="ij")
    Yp = np.full_like(Xp, yc[i])
    _plano_3d(ax, Xp, Yp, Zp, campo[:, i, :], cmap, norm)

    ax.set(xlabel="x [m]", ylabel="y [m]", zlabel="z [m]", title=titulo_ax)
    ax.set_box_aspect((2.0, 2.0, 0.55))
    ax.view_init(elev=24, azim=-58)
    ax.grid(alpha=0.25)


def figuras_3d(vox, modelo, r, local, t_T, t_dT, carpeta: Path) -> None:
    from mcplan import visualization as vis

    formas = modelo.grid.shape
    zonas = {"nucleo": modelo.is_core.reshape(formas), "superficie": modelo.is_surface.reshape(formas)}
    extras = {k: v.astype(np.uint8) for k, v in zonas.items()}
    vmax = float(np.ceil(np.nanmax([np.nanmax(c) for c in r.campos.values()]) / 5.0) * 5.0)

    # Serie .vti/.pvd para ParaView: cada 24 h + los dos instantes maximos.
    tiempos = sorted(r.campos)
    elegidos = sorted({t for t in tiempos if abs(t - round(t / 24.0) * 24.0) < 1e-6} |
                      {min(tiempos, key=lambda x: abs(x - t_T)), min(tiempos, key=lambda x: abs(x - t_dT))})
    archivos = vis.guardar_serie(carpeta / "vti", vox.grid, vox.vertida_id,
                                 {t: r.campos[t] for t in elegidos}, extras)
    print(f"    {len(archivos)} .vti + {carpeta / 'vti' / 'serie.pvd'} (abrir en ParaView)")

    cmap = plt.get_cmap("inferno")
    norm = matplotlib.colors.Normalize(vmin=10.0, vmax=vmax)
    x = local["T_max"]
    d = local["delta_T_max"]

    for t_h, nombre, texto in (
        (t_T, "e12_3d_tmax.png",
         f"t = {t_T:g} h · T_max = {x['T_C']:.1f} °C en ({x['x_m']:.2f}; {x['y_m']:.2f}; {x['z_m']:.2f}) m"),
        (t_dT, "e12_3d_dtmax.png",
         f"t = {t_dT:g} h · ΔT_max = {d['delta_T_C']:.1f} °C "
         f"(núcleo {d['nucleo']['T_C']:.1f} / superficie {d['superficie']['T_C']:.1f})"),
    ):
        fig = plt.figure(figsize=(10.5, 6.2))
        ax = fig.add_subplot(111, projection="3d")
        _vista_3d(ax, modelo, _campo_en(r, t_h), cmap, norm, texto)
        barra = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax,
                             shrink=0.65, pad=0.10)
        barra.set_label("T [°C]")
        fig.tight_layout()
        fig.savefig(carpeta / nombre, dpi=160, bbox_inches="tight")
        plt.close(fig)

    # Zonas de control a t = ΔT_max: nucleo y superficie sobre el resto del hormigon.
    campo = _campo_en(r, t_dT)
    X, Y, Z = np.meshgrid(*modelo.grid.centers(), indexing="ij")
    activo = np.isfinite(campo) & (vox.vertida_id >= 0)
    nucleo = zonas["nucleo"] & activo
    superficie = zonas["superficie"] & activo
    resto = activo & ~nucleo & ~superficie
    fig = plt.figure(figsize=(9.5, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(X[resto], Y[resto], Z[resto], c="#b0b0b0", s=3, alpha=0.30, label="hormigón interior")
    ax.scatter(X[nucleo], Y[nucleo], Z[nucleo], c="#c92a2a", s=6, alpha=0.85, label="núcleo")
    ax.scatter(X[superficie], Y[superficie], Z[superficie], c="#2f9e44", s=6, alpha=0.85, label="superficie")
    ax.set(xlabel="x [m]", ylabel="y [m]", zlabel="z [m]",
           title=f"Zonas de control a t = {t_dT:g} h (ΔT = {d['delta_T_C']:.1f} °C)")
    ax.set_box_aspect((2.0, 2.0, 0.55))
    ax.view_init(elev=24, azim=-58)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(carpeta / "e12_3d_zonas.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("    3D: e12_3d_tmax.png, e12_3d_dtmax.png, e12_3d_zonas.png")


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------


def escribir_series(r, timeline, h_fn, t_fn, suelo, carpeta: Path) -> None:
    campos = ["t_h", "time_local", "source", "T_aire_C", "T_sol_aire_C", "viento_ms",
              "solar_W_m2", "nubosidad_pct", "h_total_W_m2K", "T_suelo_C",
              "T_max_global_C", "T_max_nucleo_C", "T_min_superficie_C", "T_media_C", "delta_T_C"]
    with open(carpeta / "series_e12.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for p in timeline.points:
            fila = {
                "t_h": f"{p.t_h:g}",
                "time_local": p.time_local,
                "source": p.source,
                "T_aire_C": f"{p.temperature_C:.3f}",
                "T_sol_aire_C": f"{float(t_fn(p.t_h)):.3f}",
                "viento_ms": f"{p.wind_ms:.3f}",
                "solar_W_m2": f"{p.solar_W_m2:.1f}",
                "nubosidad_pct": f"{p.cloud_pct:.0f}",
                "h_total_W_m2K": f"{float(h_fn(p.t_h)):.3f}",
                "T_suelo_C": f"{float(suelo.temperature(p.t_h)):.3f}",
                "T_max_global_C": f"{float(np.interp(p.t_h, r.time_h, r.T_max_global)):.3f}",
                "T_max_nucleo_C": f"{float(np.interp(p.t_h, r.time_h, r.T_max_core)):.3f}",
                "T_min_superficie_C": f"{float(np.interp(p.t_h, r.time_h, r.T_min_surface)):.3f}",
                "T_media_C": f"{float(np.interp(p.t_h, r.time_h, r.T_mean)):.3f}",
                "delta_T_C": f"{float(np.interp(p.t_h, r.time_h, r.delta_T)):.3f}",
            }
            w.writerow(fila)


def escribir_plan(plantilla, carpeta: Path) -> None:
    with open(carpeta / "plan_vertidas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["vertida", "inicio_h", "inicio_local", "T_colocacion_C", "moldaje",
                    "aislacion", "retiro_moldaje_h", "R_moldaje_m2K_W", "R_aislacion_m2K_W"])
        for v in plantilla.vertidas:
            capa = plantilla.moldajes.get(v.moldaje or "")
            aisl = plantilla.aislaciones.get(v.aislacion or "")
            w.writerow([v.id, v.inicio_h, fecha_local(v.inicio_h), v.temperatura_colocacion_C,
                        v.moldaje or "ninguno", v.aislacion or "ninguna", v.retiro_moldaje_h,
                        f"{capa.resistencia if capa else 0.0:.4f}",
                        f"{aisl.resistencia if aisl else 0.0:.4f}"])


def escribir_borde(plantilla, timeline, h_fn, t_fn, suelo, carpeta: Path) -> dict:
    """Tabla de condiciones de borde: R de cada capa y valores en instantes clave."""
    clave = [0.0, 6.0, 12.0, 18.0, 24.0, 48.0, 72.0, 168.0, 336.0]
    filas = []
    for t in clave:
        p = timeline.at(t)
        filas.append({
            "t_h": t,
            "time_local": fecha_local(t),
            "T_aire_C": round(p.temperature_C, 2),
            "viento_ms": round(p.wind_ms, 2),
            "solar_W_m2": round(p.solar_W_m2, 1),
            "h_total_W_m2K": round(float(h_fn(t)), 2),
            "T_sol_aire_C": round(float(t_fn(t)), 2),
            "T_suelo_C": round(float(suelo.temperature(t)), 2),
        })
    with open(carpeta / "condiciones_borde.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    return {"filas": filas, "R_base_m2K_W": round(suelo.resistance, 4)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ifc", type=Path, default=ROOT / "geometry" / "foundation.ifc")
    ap.add_argument("--plantilla", type=Path, default=ROOT / "datos" / "fundacion_e12.yaml")
    ap.add_argument("--forecast-dir", type=Path, default=ROOT / "datos" / "forecast")
    ap.add_argument("--dx", type=float, default=0.5)
    ap.add_argument("--dz", type=float, default=None)
    ap.add_argument("--duracion-h", type=float, default=None)
    ap.add_argument("--salida", type=Path, default=ROOT / "results" / "e12")
    ap.add_argument("--sin-3d", action="store_true", help="no exporta .vti ni figuras PyVista")
    args = ap.parse_args()

    carpeta = args.salida
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "vti").mkdir(exist_ok=True)

    plantilla = load_plan(str(args.plantilla))
    duracion = args.duracion_h or plantilla.simulacion.duracion_h

    forecast, meta_f, archivo, meta_a, verificados = leer_clima(args.forecast_dir)
    timeline = assemble_timeline(
        INICIO_LOCAL, hours=np.arange(0.0, duracion + 1e-9, 1.0).tolist(),
        forecast=forecast, climatology=archivo,
    )
    imprimir_clima(meta_f, meta_a, timeline, verificados)
    if "missing" in timeline.sources:
        raise SystemExit("Hay horas sin dato meteorologico: revisar los snapshots.")

    h_fn, t_fn = condiciones_de_timeline(timeline, absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    figura_clima(timeline, plantilla.suelo, h_fn, t_fn, carpeta)
    figura_hidratacion(plantilla, carpeta)

    # ---- Modelo y plan ----
    titulo(3, "Plan de vertidas y condicion inicial")
    solidos = extraer_solidos(args.ifc)
    dx = args.dx
    dz = args.dz or dz_que_calza(solidos, dx)
    vox = voxelizar(solidos, dx=dx, dz=dz)
    plan = plan_desde_solidos(plantilla, solidos, dx)
    plan = copy.deepcopy(plan)
    plan.simulacion.duracion_h = duracion
    aplicar_ambiente(plan, timeline, con_viento=True, con_radiacion=True,
                     absorptivity=ABSORTIVIDAD, emissivity=EMISIVIDAD)
    print(f"    Grilla {vox.grid.shape} · dx = {dx:g} m, dz = {dz:g} m · "
          f"{int(vox.mask.sum())} celdas activas · error de volumen {100 * vox.error_volumen():.2f} %")
    for v in plan.vertidas:
        print(f"    V{v.id}: inicio {v.inicio_h:5.1f} h ({fecha_local(v.inicio_h)}) · "
              f"T_colocación {v.temperatura_colocacion_C:4.1f} °C · {v.moldaje}/{v.aislacion} · "
              f"retiro {v.retiro_moldaje_h:g} h")
    print(f"    Condición inicial: T = T_colocación en cada celda al momento de su vertida.")
    print(f"    Base: Robin conductivo con R_suelo = {plan.suelo.resistance:.3f} m²K/W "
          f"(suelo semi-infinito a {plan.suelo.depth_m:g} m).")

    # ---- Simulacion ----
    titulo(4, f"Simulación determinista: {duracion:g} h, malla de {dx:g} m")
    modelo = build_model(plan, voxeles=vox)
    r = solve(
        modelo,
        duracion_h=duracion,
        intervalo_salida_h=plan.simulacion.intervalo_salida_h,
        factor_estabilidad=plan.simulacion.factor_estabilidad,
        guardar_campo=False,
        instantes_campo_h=np.arange(0.0, duracion + 1e-9, 1.0),
    )
    print(f"    dt = {r.dt_s:.0f} s · {r.metadata['pasos']} pasos · "
          f"{len(r.time_h)} instantes de salida · {len(r.campos)} campos 3D guardados")

    veredicto = evaluar_criterios(r, plan.criterios)
    for linea in veredicto.resumen().splitlines():
        print("    " + linea)

    t_T = float(r.time_of_max(r.T_max_global))
    t_dT = float(r.time_of_max(r.delta_T))
    local = localizar(modelo, vox, r, t_T, t_dT)

    titulo(5, "Máximos: instante y ubicación")
    x = local["T_max"]
    print(f"    T_max = {x['T_C']:.2f} °C a {x['t_h']:g} h ({x['time_local']})")
    print(f"            celda ({x['x_m']:.2f}; {x['y_m']:.2f}; {x['z_m']:.2f}) m · vertida V{x['vertida']}")
    d = local["delta_T_max"]
    print(f"    ΔT_max = {d['delta_T_C']:.2f} °C a {d['t_h']:g} h ({d['time_local']})")
    print(f"            núcleo {d['nucleo']['T_C']:.2f} °C en "
          f"({d['nucleo']['x_m']:.2f}; {d['nucleo']['y_m']:.2f}; {d['nucleo']['z_m']:.2f}) m · V{d['nucleo']['vertida']}")
    print(f"            superficie {d['superficie']['T_C']:.2f} °C en "
          f"({d['superficie']['x_m']:.2f}; {d['superficie']['y_m']:.2f}; {d['superficie']['z_m']:.2f}) m · V{d['superficie']['vertida']}")

    dT = np.asarray(r.delta_T)
    sobre = np.where(dT > plan.criterios.delta_T_max_C)[0]
    excede = {
        "horas_sobre_20": int(sobre.size),
        "primera_h": float(r.time_h[sobre[0]]) if sobre.size else None,
        "ultima_h": float(r.time_h[sobre[-1]]) if sobre.size else None,
        "primera_local": fecha_local(r.time_h[sobre[0]]) if sobre.size else None,
        "ultima_local": fecha_local(r.time_h[sobre[-1]]) if sobre.size else None,
    }
    print(f"    ΔT > 20 °C durante {excede['horas_sobre_20']} h registradas "
          f"({excede['primera_h']} h a {excede['ultima_h']} h)")

    # ---- Figuras de series ----
    figura_criterios(r, t_T, t_dT, carpeta)
    figura_nucleo_superficie(r, t_T, t_dT, carpeta)

    # ---- 3D ----
    if not args.sin_3d:
        titulo(6, "Resultados 3D")
        figuras_3d(vox, modelo, r, local, t_T, t_dT, carpeta)

    # ---- Tablas y resumen ----
    titulo(7, "Tablas y resumen")
    escribir_series(r, timeline, h_fn, t_fn, plan.suelo, carpeta)
    escribir_plan(plan, carpeta)
    borde = escribir_borde(plan, timeline, h_fn, t_fn, plan.suelo, carpeta)

    def capa_R(nombre: str, catalogo) -> float:
        capa = catalogo.get(nombre)
        return round(capa.resistencia, 4) if capa else 0.0

    resumen = {
        "entrega": "E12 - simulación determinista de 14 días",
        "caso": plan.caso,
        "inicio_local": INICIO_LOCAL,
        "duracion_h": duracion,
        "fecha_fin_local": timeline.points[-1].time_local,
        "malla": {
            "dx_m": dx, "dz_m": dz, "shape": list(vox.grid.shape),
            "celdas_activas": int(vox.mask.sum()),
            "error_volumen_pct": round(100 * vox.error_volumen(), 3),
        },
        "hidratacion": {
            "curva": "C1",
            "theta_inf_C": plan.hidratacion.elevacion_adibatica_C,
            "tau_h": plan.hidratacion.tau_h,
            "segunda_rama_C": plan.hidratacion.elevacion_adibatica_2_C,
            "madurez": bool(plan.hidratacion.madurez),
            "Ea_R_K": plan.hidratacion.energia_activacion_K,
            "T_ref_C": 20.0,
        },
        "clima": {
            "snapshots_verificados": len(verificados),
            "forecast": asdict(meta_f),
            "archivo": asdict(meta_a),
            "cobertura": dict(timeline.sources),
            "horas_simuladas": len(timeline) - 1,
            "puntos": len(timeline),
            "T_aire_min_C": round(min(p.temperature_C for p in timeline.points), 2),
            "T_aire_max_C": round(max(p.temperature_C for p in timeline.points), 2),
            "viento_medio_ms": round(float(np.mean([p.wind_ms for p in timeline.points])), 2),
            "viento_max_ms": round(float(np.max([p.wind_ms for p in timeline.points])), 2),
            "G_max_W_m2": round(float(np.max([p.solar_W_m2 for p in timeline.points])), 1),
            "h_total_min_W_m2K": round(float(min(h_fn(p.t_h) for p in timeline.points)), 2),
            "h_total_max_W_m2K": round(float(max(h_fn(p.t_h) for p in timeline.points)), 2),
            "T_sol_aire_max_C": round(float(max(t_fn(p.t_h) for p in timeline.points)), 2),
            "tratamiento_horizonte": (
                "0 h de forecast: el snapshot del 11-nov termina el 24-nov y la primera "
                "vertida es el 27-nov. Las 336 h se completan con climatología ERA5 del "
                "mismo calendario (2025-11-27 a 2025-12-11) desplazada al año del caso, "
                "hora a hora, sin interpolar entre años."
            ),
        },
        "suelo": {
            "R_m2K_W": round(plan.suelo.resistance, 4),
            "profundidad_m": plan.suelo.depth_m,
            "amortiguacion": round(plan.suelo.damping, 4),
            "atraso_fase_h": round(plan.suelo.phase_lag_h, 1),
        },
        "plan_vertidas": [
            {"id": v.id, "inicio_h": v.inicio_h, "inicio_local": fecha_local(v.inicio_h),
             "T_colocacion_C": v.temperatura_colocacion_C, "moldaje": v.moldaje,
             "aislacion": v.aislacion, "retiro_moldaje_h": v.retiro_moldaje_h}
            for v in plan.vertidas
        ],
        "moldajes_R_m2K_W": {n: capa_R(n, plan.moldajes) for n in plan.moldajes},
        "aislaciones_R_m2K_W": {n: capa_R(n, plan.aislaciones) for n in plan.aislaciones},
        "condiciones_borde": {
            "tipo_lateral_y_superior": "Robin: -k dT/dn = h(t) (T - T_sol_aire(t))",
            "tipo_base": "Robin conductivo con R_suelo = e/k y T no perturbada a 1 m",
            "R_base_m2K_W": borde["R_base_m2K_W"],
            "muestras": borde["filas"],
        },
        "resultado": {
            "T_max_C": round(float(r.T_max_abs), 3),
            "T_max_h": t_T,
            "T_max_local": fecha_local(t_T),
            "delta_T_max_C": round(float(r.delta_T_max), 3),
            "delta_T_h": t_dT,
            "delta_T_local": fecha_local(t_dT),
            "T_final_max_C": round(float(r.T_max_global[-1]), 3),
            "delta_T_final_C": round(float(r.delta_T[-1]), 3),
            "veredicto": veredicto.resumen(),
            "cumple_T_max": bool(r.T_max_abs <= plan.criterios.T_max_C),
            "cumple_delta_T": bool(r.delta_T_max <= plan.criterios.delta_T_max_C),
        },
        "localizacion": local,
        "por_vertida": por_vertida(modelo, vox, r),
        "excedencia_delta_T": excede,
        "dt_s": round(float(r.dt_s), 1),
        "pasos": int(r.metadata.get("pasos", 0)),
        "supuestos": {
            "absortividad": ABSORTIVIDAD,
            "emisividad": EMISIVIDAD,
            "h_convectiva": "ASHRAE pared plana: h = 5,7 + 3,8 v",
            "radiacion": "incluida en T sol-aire; no se suma como flujo aparte",
            "determinista": "sin Monte Carlo: un clima, una curva, un plan",
        },
    }
    (carpeta / "resumen_e12.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"    series_e12.csv, plan_vertidas.csv, condiciones_borde.csv, resumen_e12.json")
    print(f"\nResultados en {carpeta}")


if __name__ == "__main__":
    main()
