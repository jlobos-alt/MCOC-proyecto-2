# E10 — Ambiente real, moldaje por vertida y snapshots de forecast

**Objetivo:** demostrar cómo el ambiente real entra a la física del solver y cómo se obtienen pronósticos trazables. La entrega cubre los cinco requisitos de la revisión oral: módulo de condiciones de borde, tratamiento de suelo, moldaje/aislación por vertida, primer cliente meteorológico y esquema de snapshots de forecast.

**Canvas:** solo `Repositorio:` y `Commit evaluado:`, sin texto adicional.

Carpeta autocontenida, igual que las entregas anteriores.

## Entregables

| Archivo | Contenido |
|---|---|
| `docs/E10_guia_oral.md` | Guía de la revisión oral: las 9 preguntas con respuesta corta, guion de demo y límites. |
| `src/mcplan/boundary.py` | Robin con `h(t)` variable en el tiempo y capas en serie. |
| `src/mcplan/environment.py` | Viento → `h`, sol-aire, radiación, flujos y puente clima → frontera. |
| `src/mcplan/soil.py` | Suelo semi-infinito: onda anual amortiguada y resistencia de capa. |
| `src/mcplan/meteo.py` | Cliente Open-Meteo (forecast y reanalysis) + ensamblado forecast/climatología. |
| `src/mcplan/snapshots.py` | Snapshots inmutables: JSON crudo, CSV normalizado, SHA-256 e índice. |
| `datos/fundacion_e10.yaml` | Catálogos de moldaje/aislación, suelo anual y fronteras. |
| `datos/forecast/` | Snapshots reales descargados el 11-nov-2026 + `index.json`. |
| `scripts/e10_ambiente.py` | Demo ejecutable: descarga, ensambla clima, corre 4 casos y genera figuras. |
| `results/e10/` | Series, resumen JSON, moldaje por vertida y 4 figuras. |

## Reproducir

```powershell
pip install -r requirements.txt
python scripts/e10_ambiente.py                 # usa los snapshots guardados
python scripts/e10_ambiente.py --actualizar    # descarga y guarda un snapshot nuevo
python -m pytest tests -q
```

La corrida de referencia usa `dx = 0,5 m`, `dz = 0,55 m`, 36 × 36 × 8 = 4 656 celdas activas (error de volumen 0,52 %), 336 h y paso de 1 h.

## Snapshots de clima

Cada descarga se guarda sin sobrescribirse:

```
datos/forecast/
  index.json
  20261111T193622Z_open-meteo-forecast/
      raw.json            # JSON crudo de la API
      normalizado.csv     # serie horaria con unidades homogéneas
      metadata.json       # emisión, cobertura, endpoint y hashes
  20261111T193623Z_open-meteo-archive/
      ...
```

| Snapshot | Cobertura | Horas | SHA-256 del crudo |
|---|---|---|---|
| Forecast `20261111T193622Z` | 2026-11-11 00:00 → 2026-11-24 23:00 | 336 | `f97ae82f…dac7d7` |
| Reanalysis `20261111T193623Z` | 2025-11-27 00:00 → 2025-12-11 23:00 | 360 | `a56377b6…86bbb1` |

`verify()` recalcula ambos hashes y falla si un archivo fue alterado. Si se intenta guardar el mismo `snapshot_id` con otro contenido, `save_snapshot()` lanza `FileExistsError`: el forecast viejo no se pisa.

El forecast del 11 de noviembre termina el 24 de noviembre; la obra parte el 27 de noviembre. Por eso la ventana de simulación queda marcada hora a hora como `climatology` (337 h, 0 h de forecast). El reanalysis del mismo calendario de 2025 se desplaza a 2026: no se inventa el clima, se declara de dónde salió.

## Casos y resultados

Los cuatro casos comparten IFC, grilla e hidratación; cambia solo la frontera ambiental.

| Caso | Clima | Moldaje | Aislación | T max | ΔT max |
|---|---|---|---|---|---|
| `base` | sinusoidal 15 ± 5 °C, `h = 12` | capa global 0–72 h | ninguna | 63,23 °C @ 55 h | 44,47 °C @ 192 h |
| `ambiente` | forecast/climatología + viento + sol-aire | por vertida, retiro a 72 h | ninguna | 63,98 °C @ 54 h | 42,06 °C @ 148 h |
| `sin_radiacion` | igual, sin flujo solar ni onda larga | por vertida | ninguna | 63,21 °C @ 55 h | 43,62 °C @ 148 h |
| `aislado` | igual que `ambiente` | por vertida | EPS 50 mm | 63,98 °C @ 54 h | 34,72 °C @ 197 h |

Lectura: el clima de la costa de Maule en primavera es suave (8,0–20,6 °C), así que el efecto sobre `T_max` es menor (+0,75 °C respecto del caso base). La radiación aporta ≈ 0,8 °C en `T_max` y ≈ 1,6 °C en `ΔT`; la aislación reduce `ΔT` en 7,3 °C pero no cambia `T_max`, porque el máximo ocurre a las 54 h por hidratación y la cara superior queda sin aislación. El `ΔT` sigue muy por encima de 20 °C: la hidratación es provisoria y esta entrega no calibra.

## Requisito → dónde está

| Requisito E10 | Dónde |
|---|---|
| Módulo de condiciones de borde | `src/mcplan/boundary.py` (`BoundaryGroup`, `h_series`, `minimum_resistance`) y `src/mcplan/environment.py` |
| Tratamiento de suelo | `src/mcplan/soil.py` (`SoilSpec`: onda anual, `R = e/k`) + frontera `base` del YAML |
| Moldaje / aislación | `datos/fundacion_e10.yaml` (catálogos), `plan.py` (`LiftSpec.moldaje/aislacion`), `thermal.py` (`r_moldaje_flat`, `formwork_end_flat`) |
| Primer cliente / loader meteorológico | `src/mcplan/meteo.py` (`OpenMeteoClient`, `assemble_timeline`) |
| Esquema de snapshots de forecast | `src/mcplan/snapshots.py` + `datos/forecast/index.json` |
| Evidencia de la demo | `results/e10/` y `docs/E10_guia_oral.md` |

## Respuestas cortas (detalle en la guía oral)

1. **Temperatura ambiente:** es el `far_field` del Robin (`T_inf`). Con sol-aire se usa `T_sol_aire`, no la temperatura del aire cruda.
2. **Viento:** entra en `h_conv = 5,7 + 3,8 v`; `h(t)` se evalúa en cada paso y `h_max` fija el paso estable.
3. **Resistencia de moldaje:** `R = e/k` (madera 19 mm → 0,158 m²K/W), en serie con el medio celda de hormigón y la película convectiva.
4. **Al desmoldar:** `R` baja de golpe en la cara lateral; la frontera cambia en el tiempo, sin remallar. Cada vertida se desmolda a sus 72 h.
5. **Flujo solar:** `q_solar = α G` [W/m²], con `G` la radiación de onda corta y `α = 0,6`.
6. **Doble conteo:** se elige una sola vía. Aquí la radiación va dentro de `T_sol_aire` y de `h_total`; no se suma además como flujo Neumann.
7. **Forecast / reanalysis / observación:** predicción emitida, serie histórica consistente y medición de terreno; solo la observación valida.
8. **Forecast que no cubre:** se rellena con climatología desplazada y cada hora queda etiquetada `forecast`, `climatology` o `missing`; se reemplaza cuando llegue un forecast nuevo.
9. **Conservar forecasts viejos:** trazabilidad y reproducibilidad; los snapshots con hash permiten auditar qué se sabía el día de la corrida.

## Límites declarados

- `T_sol_aire` se aplica por igual a todas las caras laterales: no hay orientación, sombra ni distinción sol/sombra.
- Suelo 1D: onda anual a 1 m; no se resuelve flujo horizontal ni estratigrafía.
- No hay evaporación, lluvia sobre la superficie ni viento direccional.
- Hidratación provisoria (Ju & Lei sin calibrar): `T_max` y `ΔT` sirven para comparar casos, no para aprobar el plan.
- El forecast guardado es el del 11-nov-2026. Cuando exista un forecast que cubra el 27-nov, se agrega un snapshot nuevo y se vuelve a correr; no se edita el anterior.
