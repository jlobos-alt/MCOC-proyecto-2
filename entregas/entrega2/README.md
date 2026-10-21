# Entrega 2 (E02) — Lab: round-trip IFC y demo 1D

**Fecha:** Jueves 22 de octubre, 10:30–12:30 · **Puntaje:** 3 puntos

Demostración de un flujo mínimo **Bonsai → IFC → Python** y un **solver 1D**
funcionando. Carpeta autocontenida: incluye IFC, scripts, solver, tests y datos.

## Contenido

```
entregas/entrega2/
├── README.md                        ← este archivo
├── docs/
│   └── E02_guion_actividad.md       guion paso a paso de lo que pide el ayudante
├── geometry/                        modelo IFC (fuente de verdad)
│   ├── foundation.ifc               5 vertidas IfcFooting + Pset_HormigonMasivo
│   └── foundation_base.ifc          semilla determinista
├── src/mcplan/                      solver (paquete)
│   ├── thermal1d.py                 solver 1D FTCS (Dirichlet/Neumann/Robin)
│   └── bim.py                       lectura del IFC (IfcOpenShell o STEP)
├── scripts/
│   ├── roundtrip_ifc.py             listar / modificar propiedad / verificar
│   └── demo_1d_dx_dt.py             demo 1D con Δx y Δt configurables
├── tests/                           36 tests (round-trip + efecto Δx/Δt)
├── resultados/
│   └── demo_1d.png                  figura del caso 1D
└── requirements.txt / pyproject.toml / environment.yml
```

## Reproducir

```bash
pip install -r requirements.txt

# Round-trip IFC
python scripts/roundtrip_ifc.py --list
python scripts/roundtrip_ifc.py --set TemperaturaColocacion_C 21.5 --vertida Vertida_03

# Demo 1D y efecto de Δx / Δt
python scripts/demo_1d_dx_dt.py --sweep
python scripts/demo_1d_dx_dt.py --nx 21      # Δx grueso
python scripts/demo_1d_dx_dt.py --nx 161     # Δx fino

# Tests
python -m pytest tests/ -q                    # 36 passed
```

## Mapeo a la rúbrica de la actividad

| Requisito (antes) | Dónde |
|---|---|
| IFC con ≥ 3 objetos identificables | `geometry/foundation.ifc` — 5 `IfcFooting` `Vertida_01..05` |
| Script que lea el IFC | `scripts/roundtrip_ifc.py --list` (usa `mcplan.bim`) |
| Solver 1D ejecutable | `scripts/demo_1d_dx_dt.py` → `src/mcplan/thermal1d.py` |
| ≥ 1 test automatizado | `tests/` → 36 tests |

| Paso de la actividad | Cómo se demuestra |
|---|---|
| 1. Abrir el IFC en Bonsai | `geometry/foundation.ifc` (File > Open IFC Project) |
| 2. Identificar los objetos | `python scripts/roundtrip_ifc.py --list` |
| 3. Modificar geometría o propiedad | `--set TemperaturaColocacion_C 21.5 --vertida Vertida_03` (o editar en Bonsai) |
| 4. Guardar | el script escribe `geometry/foundation_editado.ifc` (Bonsai: Ctrl+S) |
| 5. Python detecta la modificación | paso `[6] Verificacion` del script / `tests/test_roundtrip.py` |
| 6. Ejecutar el solver 1D | `python scripts/demo_1d_dx_dt.py` |
| 7. Modificar Δx o Δt | `--nx 21/161` y `--dt ...` |
| 8. Explicar el efecto | ver `docs/E02_guion_actividad.md` |

## Efecto de Δx y Δt (resumen)

- **Δx = L/(nx−1).** Al refinar la malla (nx↑) el error de discretización baja
  como O(Δx²) y el perfil converge a la solución de referencia.
- **Δt.** El esquema es explícito (FTCS). Es estable solo si
  `Fo = α·Δt/Δx² ≤ 0.5`, es decir `Δt ≤ Δx²/(2α)`. Sobre ese límite la
  solución **diverge**. Reducir Δx obliga a reducir Δt proporcionalmente.

## Criterios del proyecto

T_max ≤ 70 °C · ΔT ≤ 20 °C (14 días). Caso demo: T_max ≈ 63 °C (cumple),
ΔT ≈ 43 °C (no cumple con este Q provisorio).

URL del repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
