# MCOC — Proyecto 2: Hormigón masivo

**Grupo 5** · José Lobos · Clemente Sánchez · Matías Campos

Fundación de aerogenerador (geometría docente inspirada en Ju & Lei, 2019).
Objetivo: diseñar un plan de vertidas que respete **T_max ≤ 70 °C** y **ΔT ≤ 20 °C** (núcleo–superficie).

```text
Bonsai/Blender ──> IFC ──> IfcOpenShell ──> voxelización ──> solver térmico ──> Monte Carlo ──> plan
 (autoría BIM)   (contrato)  (lectura)        (grilla)         (física)       (confiabilidad)
```

> **BIM ≠ solver ≠ visualizador.** El solver es Python normal y no importa Blender.

## E00 — Registro

| Campo | Valor |
|---|---|
| **Grupo** | 5 |
| **Sitio** | Pahuil / Chanco — Región del Maule (costero) |
| **Proyecto eólico** | Viento Pacífico Verde (en evaluación) |
| **Coordenadas** | -35.644721, -72.568332 (usar en todos los scripts de clima) |
| **Estación DMC de contraste** | Dunas de Chanco (Pahuil), id 350040 |
| **URL repositorio** | https://github.com/jlobos-alt/MCOC-proyecto-2 |
| **SHA inicial** | `f222414d01ed90b2d648077dc49701ad247c9907` |

## E01 — Estado

| Componente | Archivo | Estado |
|---|---|---|
| **Solver 1D** explícito (FTCS) Dirichlet / Neumann / Robin + fuente Q(t), chequeo de estabilidad | `src/mcplan/thermal1d.py` | ✅ verificado |
| **Modelo IFC4**: 5 vertidas `IfcFooting` + `Pset_HormigonMasivo`, guardado en **Blender 5.2 + Bonsai 0.9** | `geometry/foundation.ifc` | ✅ |
| Semilla reproducible del IFC (script) y validación en Bonsai | `geometry/make_foundation_ifc.py`, `bonsai_open_and_save.py`, `bonsai_report.txt` | ✅ |
| Lectura IFC (IfcOpenShell, con respaldo STEP) | `src/mcplan/bim.py`, `scripts/inspect_ifc.py` | ✅ |
| Tests: 12 solver 1D + 7 IFC + 5 solver 3D | `tests/` | ✅ 24/24 |
| Caso demo 1D con hidratación | `scripts/run_1d_demo.py` | ✅ (parámetros provisorios) |
| Avance: solver 3D por balance de celdas, plan YAML, hidratación, criterios, Monte Carlo | `src/mcplan/thermal.py`, `plan.py`, …, `scripts/run_case.py` | 🧪 adelanto para E04+ |
| Voxelización desde el IFC, clima real del sitio, hidratación calibrada | — | ⏳ |

## Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```
o con conda: `conda env create -f environment.yml && conda activate mcoc-p2`

## Uso

```bash
pytest -v                                    # 24 tests
python scripts/inspect_ifc.py                # vertidas, GUID y Pset del IFC
python scripts/run_1d_demo.py                # losa 1D con hidratación -> results/demo_1d.png
python scripts/run_case.py --plan datos/caso_fundacion.yaml   # caso 3D (avance)
python geometry/make_foundation_ifc.py       # regenera foundation_base.ifc
```

## Modelo BIM

`geometry/foundation.ifc` (IFC4): `IfcProject > IfcSite > IfcBuilding > IfcBuildingStorey` con 5 `IfcFooting`:

| Vertida | z [m] | Forma | V [m³] |
|---|---|---|---:|
| Vertida_01 | 0.00–0.55 | prisma octagonal (18 m entre caras) | 147.6 |
| Vertida_02 | 0.55–1.10 | prisma octagonal | 147.6 |
| Vertida_03 | 1.10–2.20 | tronco octagonal 18 → 12.5 m | 214.2 |
| Vertida_04 | 2.20–3.30 | tronco octagonal 12.5 → 7 m | 88.9 |
| Vertida_05 | 3.30–4.30 | cilindro Ø 7 m | 38.5 |

Cada vertida tiene `Pset_HormigonMasivo`: `VertidaID, TipoHormigon, InicioPlanificado,
TemperaturaColocacion_C, Moldaje, Aislacion, RetiroMoldaje_h, VolumenGeometrico_m3` (fechas y
temperaturas **provisorias**). Los GlobalId son deterministas.

Flujo: `course_geometry.json` → `make_foundation_ifc.py` → `foundation_base.ifc` → **Bonsai**
(`File > Open IFC Project` / `Save IFC Project`) → `foundation.ifc`. El paso por Bonsai se automatiza
con `geometry/bonsai_open_and_save.py` (consola Python de Blender), que valida los volúmenes desde la
geometría triangulada con IfcOpenShell: 636.9 m³, igual al cálculo analítico. La fuente de verdad es el `.ifc`.

## Solver 1D

Balance por volumen de control nodal: `C_i dT_i/dt = Σ G_ij (T_j − T_i) + Q_i V_i + Q_borde`,
con `C = ρ c_p V` y `G = k A / Δx`; los bordes son medias celdas. Estabilidad:
`Δt ≤ C_i / (Σ G_ij + G_borde)`, que da `Fo = αΔt/Δx² ≤ 1/2` en el interior (Robin la reduce).
Si `dt` excede el límite, el solver lanza `ValueError`.

Tests: modo sinusoidal exacto (Dirichlet) y orden 2, conservación de energía, fuente uniforme → subida
lineal, flujo Neumann → `ΔE = −q t`, estacionario Robin+Dirichlet analítico, h→∞ ≈ Dirichlet,
límite Fo = ½ y explosión con Fo = 0.6. El solver 3D se verifica además con convergencia 1D/2D,
energía, fuente uniforme y Robin contra capacidad agrupada.

## Estructura

```text
src/mcplan/        thermal1d.py (solver 1D E01), bim.py (lectura IFC),
                   thermal.py, grid.py, boundary.py, hydration.py, materials.py,
                   plan.py, criteria.py, reliability.py, weather.py (solver 3D y plan)
geometry/          foundation.ifc (Bonsai), foundation_base.ifc, course_geometry.json, scripts BIM
scripts/           inspect_ifc.py, run_1d_demo.py, run_case.py
tests/             test_thermal1d.py, test_ifc.py, test_verificacion_termica.py
datos/             caso_fundacion.yaml (plan declarativo)
validacion/        resultados del caso 3D
results/           figuras generadas
docs/              E01_preparacion_oral.md, respuestas E01, guía de revisión, guías G00–G08, referencias
calendario/        calendario del capstone (E00–E15)
```
