# E12 — Simulación determinista de 14 días (3 puntos)

**Objetivo:** un único caso determinista de 336 h con la física integrada de E09–E11
(geometría del IFC, vertidas, curva de hidratación, suelo, moldaje/aislación, clima y
visualización 3D), y el veredicto de los criterios de 70 °C y 20 °C.

**Canvas:** `Repositorio` y `Commit evaluado`. Informe final:
[E12_informe_final.pdf](E12_informe_final.pdf) (9 páginas, 7 figuras, 1326 palabras).
Fuentes editables: [E12_informe.docx](E12_informe.docx) y [E12_informe.md](E12_informe.md)
(1394 palabras).

Carpeta autocontenida: `src`, `tests`, `datos`, `geometry`, `scripts` y `results`.

## Preparar

```powershell
pip install -r requirements.txt
python scripts/e12_determinista.py        # 336 h, malla de 0,5 m (~1 min)
python -m pytest tests -q                # suite de la entrega
python scripts/generar_informe_e12.py --commit <SHA>   # regenera MD y DOCX
```

## Un solo comando para toda la entrega

`python scripts/e12_determinista.py` imprime siete pasos numerados y deja en
`results/e12/`:

| Paso | Qué muestra | Evidencia |
|---|---|---|
| [1] | Snapshots, hashes y cobertura del horizonte | `resumen_e12.json`, `series_e12.csv` (`source` por hora) |
| [2] | Curva C1 y calor volumétrico | `e12_curva_c1.png` |
| [3] | Plan de vertidas del IFC y condición inicial | `plan_vertidas.csv` |
| [4] | Simulación 336 h, malla 0,5 m | `resumen_e12.json` (`dt_s`, `pasos`, `malla`) |
| [5] | `T_max` y `ΔT_max`: instante y celda | `resumen_e12.json` → `localizacion` |
| [6] | Visualización 3D y serie para ParaView | `e12_3d_*.png`, `vti/serie.pvd` |
| [7] | Tablas, series y resumen | `condiciones_borde.csv`, `resumen_e12.json` |

La serie `.vti` (17 archivos: cada 24 h más los dos instantes máximos) se genera al
correr el script y **no se versiona** (`.gitignore` excluye `*.vti`/`*.pvd`); el `.pvd`
se abre en ParaView con temperatura, vertida y las máscaras de núcleo y superficie.

## Resultado (caso único, sin variantes)

| Criterio | Límite | Valor | Instante | Ubicación | Veredicto |
|---|---|---|---|---|---|
| `T_max` | 70 °C | **63,98 °C** | 54 h (2026-11-29 10:00) | (−0,25; −0,25; 1,38) m, V3 | cumple |
| `ΔT_max` | 20 °C | **42,06 °C** | 148 h (2026-12-03 08:00) | núcleo (−0,25; −0,25; 1,93) m / superficie (−8,75; −3,75; 0,82) m | **no cumple** |

- Curva **C1**: θ_ad = 45·(1 − e^(−a/30)) °C, madurez Arrhenius Ea/R = 4000 K, T_ref = 20 °C, sin segunda rama.
- Clima: **0 h de forecast + 337 puntos de climatología**. El forecast del 11-nov termina el 24-nov; la obra parte el 27-nov. Cada fila del CSV declara su fuente.
- `ΔT > 20 °C` en 313 de 337 horas registradas: desde las 24 h hasta el final de la ventana.
- El mecanismo que controla el ΔT es el desacople núcleo-superficie al retirarse el moldaje (72–96 h), no el pico del núcleo.

## Rúbrica

| Criterio | Pts | Dónde |
|---|---|---|
| Integración física | 0,9 | `scripts/e12_determinista.py` usa `environment`, `soil`, `boundary` y `thermal` con el plan del IFC; un solo caso determinista |
| Clima trazable | 0,6 | `src/mcplan/snapshots.py` (`verify`), `series_e12.csv` con `source`, `resumen_e12.json` con timestamps y SHA-256 |
| Criterios 70/20 °C | 0,6 | `src/mcplan/criteria.py`; `resumen_e12.json` con instante y celda de ambos máximos |
| Visualización | 0,5 | `e12_3d_tmax.png`, `e12_3d_dtmax.png`, `e12_3d_zonas.png`, `vti/serie.pvd` |
| Síntesis y reproducibilidad | 0,4 | `E12_informe.docx`, 9 tests, `dt = 3600 s` fijo y corridas repetibles bit a bit |

## Reproducibilidad

- `dt = 3600 s`, 336 pasos, sin aleatoriedad: dos corridas del mismo caso dan la misma serie (`test_dos_corridas_del_mismo_caso_son_identicas`).
- Los snapshots se verifican por SHA-256 antes de simular; si cambia un byte, el script se detiene.
- Todas las cifras del informe salen de `results/e12/resumen_e12.json`; Markdown y DOCX se generan con el mismo script.

## Limitaciones

- El forecast disponible no cubre la ventana: se usa climatología ERA5 del mismo calendario, declarada hora a hora.
- La superficie se mide en centros de celda, a 0,25 m de la cara; el ΔT real a 25 mm sería mayor.
- La curva C1 es la única declarada en el repo. Si el profesor entrega otras curvas, se cambia θ∞, τ y Ea/R en `datos/fundacion_e12.yaml` y se vuelve a correr; el resto no cambia.
