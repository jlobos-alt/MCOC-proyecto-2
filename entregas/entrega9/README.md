# E09 — Baseline 3D con hidratación

**Objetivo:** entregar la primera simulación 3D físicamente interpretable del caso de referencia, con geometría del curso, hidratación, vertidas y condiciones ambientales simplificadas pero declaradas.

**Canvas:** solo `Repositorio` y `Commit evaluado`, sin texto adicional.

Carpeta autocontenida, igual que las entregas anteriores.

## Entregables

| Archivo | Contenido |
|---|---|
| `E09_informe.pdf` | Informe final renderizado (8 páginas, figuras y tablas). |
| `E09_informe.docx` | Versión Word editable del mismo informe. |
| `E09_informe.md` | Fuente Markdown del informe (1179 palabras narrativas). |
| `results/e09/` | Series, resumen JSON, figuras y cortes generados por la simulación. |

## Reproducir

```powershell
pip install -r requirements.txt
python scripts/baseline_e09.py        # simulación + figuras + CSV/JSON (~15 s)
python -m pytest tests -q             # 116 pruebas
```

`baseline_e09.py` corre el caso del IFC con Δx = 0,25 m y Δz = 0,275 m (72 × 72 × 16, 37 164 celdas activas), guarda `results/e09/series_e09.csv` y `results/e09/resumen_e09.json`, y regenera las seis figuras del informe.

Para el visualizador 3D de E08 (requiere PyVista):

```powershell
python scripts/simular_fundacion_ifc.py --salida results/e09/base --t 72 --corte --vti-cada-h 0
```

## Resultados clave

| Métrica | Valor |
|---|---|
| T máxima del hormigón | **63,06 °C a las 52 h** |
| ΔT en centros de celda | **47,18 °C a las 166 h** |
| ΔT estimado a 25 mm de la superficie | **49,17 °C a las 138 h** |
| Error de volumen total | **0,29 %** (V IFC 636,88 m³) |
| Núcleo (0,0; 0,0; 2,06 m) | 62,63 °C a las 84 h |
| Superficie superior, 1.ª celda | 43,44 °C a las 57 h |
| Base (0,0; 0,0; 0,14 m) | 55,28 °C a las 42 h |
| Borde lateral (−6,1; 0,0; 2,06 m) | 42,27 °C a las 42 h |

**Veredicto:** T_max cumple el límite de 70 °C; el ΔT no cumple el límite de 20 °C (ni el de 30 °C de la ICH). Es un **baseline**, no una validación.

## Estructura

| Requisito E09 | Dónde |
|---|---|
| Repo + commit | `E09_informe.pdf`, portada del `.docx`, Canvas |
| Imagen BIM | `results/e09/bim_base.png` |
| Voxelización | `results/e09/voxeles_cortes.png`, `src/mcplan/voxel.py` |
| Error de volumen | `results/e09/resumen_e09.json`, tabla en el informe |
| Definición de vertidas | `geometry/foundation.ifc`, `datos/fundacion_ifc.yaml` |
| Modelo de hidratación | `src/mcplan/hydration.py`, sección 4 del informe |
| T_max(t) | `results/e09/e09_tmax.png` |
| Temperaturas en puntos | `results/e09/e09_puntos.png` |
| Cortes 3D | `results/e09/e09_cortes.png`, `results/e09/e09_vista3d.png` |
| Comparación con Ju & Lei | Sección 6 del informe |

## Condiciones declaradas

- Aire 15 ± 5 °C, período 24 h; suelo 12 °C.
- Convección h = 12 W/(m²·K) en perímetro y superficie.
- Encofrado de madera de 20 mm, k = 0,5 W/(m·K), común a todas las vertidas y retirado a las 72 h.
- Hidratación: θ∞ = 45 °C, τ = 30 h, Ea/R = 4000 K, madurez de Arrhenius.
- Sin radiación solar, viento ni curado superficial.

Estos parámetros son **provisorios**: sirven para interpretar el baseline y se calibrarán en E10–E12 con el clima de Chanco.

## Limitaciones

- La hidratación y el clima no están calibrados contra mediciones.
- El ΔT se informa en centros de celda y a 25 mm; falta un sensor virtual equivalente al del paper.
- La vertida 5 tiene 10,07 % de error de volumen por su cara superior cilíndrica.
- La comparación con Ju & Lei (2019) es cualitativa.

## Referencia

Ju, Y. y Lei, H. (2019). *Actual Temperature Evolution of Thick Raft Concrete Foundations and Cracking Risk Analysis*. Advances in Materials Science and Engineering, Article ID 7029671. https://doi.org/10.1155/2019/7029671
