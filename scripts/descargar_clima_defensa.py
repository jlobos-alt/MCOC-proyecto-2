"""Descarga y congela el clima de la defensa: t0 = jueves 19-nov-2026 08:00 (America/Santiago).

Guarda en datos/forecast_defensa/ (indice propio; los snapshots de E10-E13 no se tocan):

  - forecast determinista de Open-Meteo (best_match, 16 dias);
  - ensemble GFS completo (31 miembros, 16 dias) como un snapshot con el JSON crudo entero;
  - los 3 miembros representativos, cada uno como snapshot propio;
  - reanalysis ERA5 del mismo calendario de 2025, para completar las horas que el
    ensemble no cubre (cada hora queda etiquetada);
  - escenarios/<sello>.json: que miembros se eligieron, con que criterio y que peso.

Uso:
    python scripts/descargar_clima_defensa.py            # descarga y guarda (requiere internet)
Nada se sobrescribe: una segunda descarga crea snapshots y un archivo de escenarios nuevos.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcplan.escenarios_clima import (  # noqa: E402
    ahora_utc, descargar_ensemble, miembro, nombres_miembros, representativos,
)
from mcplan.meteo import SITIO_PAHUIL, OpenMeteoClient  # noqa: E402
from mcplan.snapshots import save_snapshot, verify  # noqa: E402

T0_LOCAL = "2026-11-19T08:00:00"
HORIZONTE_H = 336          # 14 dias desde t0
CARPETA = ROOT / "datos" / "forecast_defensa"
MODELO = "gfs_seamless"


def main() -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    cliente = OpenMeteoClient(timeout_s=90.0)
    sello = datetime.fromisoformat(ahora_utc()).strftime("%Y%m%dT%H%M%SZ")

    print("Forecast determinista (best_match, 16 dias)...")
    det = cliente.forecast(SITIO_PAHUIL, days=16)
    m_det = save_snapshot(det, CARPETA, notes="Forecast determinista para la defensa (t0 = 19-nov 08:00).")
    print(f"  {m_det.snapshot_id}: {m_det.first_time} -> {m_det.last_time}")

    t0 = datetime.fromisoformat(T0_LOCAL)
    desde = (t0 - timedelta(days=1)).date().replace(year=t0.year - 1).isoformat()
    hasta = (t0 + timedelta(days=30)).date().replace(year=t0.year - 1).isoformat()
    print(f"Reanalysis ERA5 {desde}..{hasta} (relleno de horas sin forecast)...")
    era = cliente.archive(SITIO_PAHUIL, desde, hasta)
    m_era = save_snapshot(era, CARPETA, notes="ERA5 del mismo calendario 2025: completa las horas que el ensemble no cubre.")
    print(f"  {m_era.snapshot_id}: {m_era.first_time} -> {m_era.last_time}")

    print(f"Ensemble {MODELO} (16 dias)...")
    payload, crudo = descargar_ensemble(SITIO_PAHUIL, MODELO, 16)
    fetched = ahora_utc()
    nombres = nombres_miembros(payload)
    frames = {n: miembro(payload, n, MODELO, fetched) for n in nombres}
    completo = miembro(payload, "control", MODELO, fetched, raw=crudo)
    completo.notes = f"Ensemble {MODELO} completo ({len(nombres)} miembros). raw.json = respuesta entera de la API."
    m_ens = save_snapshot(completo, CARPETA, snapshot_id=f"{sello}_open-meteo-ensemble-{MODELO}")
    print(f"  {m_ens.snapshot_id}: {len(nombres)} miembros, {m_ens.first_time} -> {m_ens.last_time}")

    fin = (t0 + timedelta(hours=HORIZONTE_H)).isoformat()
    reps = representativos(frames, T0_LOCAL, fin, k=3)
    escenarios = []
    for etiqueta, r in zip(("frio", "medio", "calido"), reps):
        r.frame.raw = json.dumps({"latitude": r.frame.latitude, "longitude": r.frame.longitude,
                                  "miembro": r.nombre, "hourly": {
                                      "time": r.frame.times, "temperature_2m": r.frame.temperature_C,
                                      "wind_speed_10m": r.frame.wind_ms, "shortwave_radiation": r.frame.solar_W_m2,
                                      "cloud_cover": r.frame.cloud_pct}}, ensure_ascii=False).encode("utf-8")
        meta = save_snapshot(r.frame, CARPETA, snapshot_id=f"{sello}_gfs-ens-{etiqueta}-{r.nombre}",
                             notes=f"Miembro {r.nombre} del ensemble {m_ens.snapshot_id}; representa "
                                   f"{len(r.representa)} de {len(nombres)} miembros (grupo {etiqueta}).")
        escenarios.append({
            "etiqueta": etiqueta, "miembro": r.nombre, "snapshot_id": meta.snapshot_id,
            "peso": r.peso, "T_media_ventana_C": round(r.T_media_C, 3),
            "grupo_T_media_C": [round(x, 3) for x in r.rango_grupo_C], "representa": r.representa,
        })
        print(f"  {etiqueta:<7} {r.nombre:<9} T media {r.T_media_C:5.2f} C  peso {r.peso:.3f}  "
              f"(grupo {r.rango_grupo_C[0]:.2f}..{r.rango_grupo_C[1]:.2f} C)")

    definicion = {
        "t0_local": T0_LOCAL, "zona_horaria": SITIO_PAHUIL.timezone, "horizonte_h": HORIZONTE_H,
        "sitio": {"nombre": SITIO_PAHUIL.name, "lat": SITIO_PAHUIL.latitude, "lon": SITIO_PAHUIL.longitude},
        "celda_open_meteo": {"lat": payload.get("latitude"), "lon": payload.get("longitude")},
        "ensemble": m_ens.snapshot_id, "forecast_determinista": m_det.snapshot_id, "relleno": m_era.snapshot_id,
        "metodo": "Miembros ordenados por T media del aire en [t0, t0 + 14 d], tres grupos de tamano parecido; "
                  "de cada grupo, el miembro mas cercano a la mediana del grupo; peso = fraccion de miembros del grupo. "
                  "Horas sin dato del ensemble: ERA5 del mismo calendario de 2025.",
        "perdidos": "Los miembros extremos de cada grupo no se simulan: los pesos son una hipotesis del modelo.",
        "escenarios": escenarios,
    }
    (CARPETA / "escenarios").mkdir(exist_ok=True)
    ruta = CARPETA / "escenarios" / f"{sello}.json"
    if ruta.exists():
        raise FileExistsError(ruta)
    ruta.write_text(json.dumps(definicion, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Escenarios: {ruta}")
    print(f"Snapshots verificados: {len(verify(CARPETA))}")


if __name__ == "__main__":
    main()
