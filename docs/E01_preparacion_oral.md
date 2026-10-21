# E01 — Machete para la revisión oral

## BIM / IFC
- **BIM**: no es un programa, es una *forma estructurada de representar y gestionar la información* de una obra: identidad, geometría, materiales, propiedades, relaciones, fases y cantidades. Ejemplo: Vertida_03 tiene geometría, hormigón M1, T de colocación e inicio.
- **IFC**: estándar **abierto** (buildingSMART, ISO 16739) y neutral respecto del fabricante para intercambiar modelos BIM. Guarda objetos con **GUID**, clases (`IfcFooting`), geometría, materiales, *property sets* y relaciones (`IfcRelAggregates`, `IfcRelContainedInSpatialStructure`, `IfcRelDefinesByProperties`). **No** es un solver ni sirve para guardar millones de temperaturas.
- **Blender**: suite 3D libre. Aquí es solo el *viewport* y el modelador geométrico. Por sí solo una malla no es BIM.
- **Bonsai**: extensión de Blender que agrega la **autoría BIM/IFC** (clases, Psets, árbol espacial, guardar en `.ifc`). Usa por dentro **IfcOpenShell**.
- **¿Por qué el solver no depende de Blender?** Por separación de capas (*BIM ≠ solver ≠ visualizador*). El contrato es el archivo IFC, así que cualquier herramienta (Revit, Bonsai...) puede alimentar el pipeline. Además el solver se puede testear, correr en HPC o Monte Carlo sin interfaz gráfica, y los resultados son reproducibles. Flujo: `Bonsai → IFC → Python normal`, **no** `Blender abierto → script interno`.
- **Fuente de verdad**: el `.ifc`, no el `.blend`.
- **En el repo**: `geometry/foundation.ifc` tiene 5 `IfcFooting` con `Pset_HormigonMasivo` y fue guardado con Bonsai 0.9 / Blender 5.2. Para mostrarlo, abrirlo en Blender (File > Open IFC Project) y seleccionar una vertida: en *Object Information* aparecen su clase, GUID y Pset. Desde Python: `python scripts/inspect_ifc.py`.
- **Clases IFC usadas**: IfcProject > IfcSite > IfcBuilding > IfcBuildingStorey (árbol espacial) y 5 IfcFooting. Geometría: `IfcExtrudedAreaSolid` (prismas y cilindro) e `IfcFacetedBrep` (troncos). GUID deterministas, que no cambian al regenerar.

## Física
| Símbolo | Significado | Unidades | Hormigón típico |
|---|---|---|---|
| k | conductividad: qué tan fácil conduce calor | W/(m·K) | 2–3 |
| ρ | densidad | kg/m³ | 2400 |
| c_p | calor específico: energía para subir 1 K un kg | J/(kg·K) | 900–1000 |
| ρc_p | capacidad volumétrica: cuánta energía "almacena" | J/(m³·K) | ≈2.3·10⁶ |
| α = k/(ρc_p) | difusividad: qué tan rápido se propaga un cambio de T | m²/s | ≈1·10⁻⁶ |

- **Tiempo característico**: t ~ L²/α. Con L = 1.65 m (medio espesor) da ≈ 2.5·10⁶ s ≈ **1 mes**. Por eso el núcleo del hormigón masivo se mantiene caliente y aparece gradiente con la superficie.
- **Ecuación**: ρc_p ∂T/∂t = k∇²T + Q̇ (con Q̇ = calor de hidratación, W/m³).
- **Balance de energía en una celda**: lo que se acumula = lo que entra por conducción + lo que se genera + lo que entra por el borde. `C_i dT_i/dt = Σ G_ij (T_j − T_i) + Q̇_i V_i + Q_borde`, con `C_i = ρc_pV_i` y `G_ij = kA/d`.
- **Condición inicial**: T(x, 0) en todo el dominio. En hormigón es la **temperatura de colocación**, y cada vertida se activa en su hora de inicio.
- **Borde Dirichlet**: T impuesta (T = T_b), p.ej. contacto con un medio de T conocida.
- **Borde Neumann**: flujo impuesto, −k ∂T/∂n = q_n. Con q_n = 0 es **adiabático** (simetría o aislación perfecta). La radiación solar absorbida es un flujo (W/m²).
- **Borde Robin**: convección, −k ∂T/∂n = h(T − T_∞). El flujo depende de la diferencia con el aire. Con h→∞ tiende a Dirichlet y con h→0 a adiabático.
- **Fuente vs borde**: la hidratación es una fuente **volumétrica** (W/m³). La convección y el sol son **de borde** (W/m²).
- **Límites del proyecto**: T_max ≤ 70 °C (riesgo de DEF/etringita diferida) y ΔT núcleo–superficie ≤ 20 °C (fisuración térmica por tracción en la superficie).

## Discretización 1D (nuestro código: `src/mcplan/thermal1d.py`)
- Grilla uniforme de nx nodos, Δx = L/(nx−1). Cada nodo es un volumen de control, y los nodos de borde tienen **media celda** (Δx/2).
- Euler explícito (**FTCS**): `T_i^{n+1} = T_i^n + Fo (T_{i+1} − 2T_i + T_{i−1}) + Δt Q̇/(ρc_p)`, con **Fo = αΔt/Δx²**.
- Neumann y Robin se aplican con un balance en la media celda: `(ρc_pΔx/2) dT_0/dt = k(T_1−T_0)/Δx − q` o `+ h(T_∞ − T_0)`. Esto equivale al *ghost node* de las guías.
- Precisión: O(Δt) en el tiempo y O(Δx²) en el espacio. El test `test_dirichlet_convergence_order_2` lo verifica.

## Estabilidad
- El esquema explícito es **condicionalmente estable**: Fo ≤ ½ en 1D, ¼ en 2D y ⅙ en 3D (grilla uniforme).
- Razón física: el nuevo valor es un promedio ponderado `(1−2Fo)T_i + Fo T_{i+1} + Fo T_{i−1}`. Si Fo > ½, el peso de T_i se vuelve negativo, aparecen oscilaciones que crecen y se viola el principio del máximo.
- Forma general (por celda): `Δt ≤ C_i / (Σ G_ij + G_borde)`. **Robin con h grande reduce Δt** (`stable_dt_1d`).
- Consecuencia: Δt ∝ Δx². Si refinas la malla al doble, el paso baja 4 veces y el costo sube 8 veces en 1D (más aún en 3D).
- En el código, si `dt > dt_max` se lanza un `ValueError`. El test `test_unstable_blows_up` muestra que con Fo = 0.6 la solución explota.

## Para navegar el código en vivo
1. `pytest -v` → 19 tests en verde.
2. Abrir `thermal1d.py`: `stable_dt_1d` (estabilidad), el loop de `solve_1d` (balance) y el bloque `for idx, bc in ...` (bordes).
3. `python scripts/run_1d_demo.py`: losa de 3.3 m con hidratación. Muestra que T_max y ΔT dependen de h, de T_col y del espesor, lo que motiva dividir en vertidas.
4. `python scripts/inspect_ifc.py` → las 5 vertidas con GUID y Pset.
