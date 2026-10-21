# Entrega 1 (E01) — BIM, difusión térmica y solver 1D

Revisión oral de la Semana 1. Esta carpeta es autocontenida: incluye el modelo
BIM, el solver, los tests y la documentación.

## Contenido

```
entregas/entrega1/
├── README.md                    ← este archivo
├── geometry/                    modelo BIM/IFC
│   ├── foundation.ifc           IFC4, 5 vertidas (IfcFooting) + Property Set (guardado en Bonsai)
│   ├── foundation_base.ifc      IFC base sin Property Set
│   ├── make_foundation_ifc.py   script que genera el IFC
│   ├── bonsai_open_and_save.py  abre/guarda el IFC en Bonsai
│   ├── bonsai_report.txt        validación en Bonsai
│   └── course_geometry.json     dimensiones docentes
├── src/mcplan/                  solver térmico (paquete)
│   ├── thermal1d.py             solver 1D FTCS (Dirichlet/Neumann/Robin + fuente)
│   ├── thermal.py               solver 3D
│   ├── boundary.py              condiciones de borde
│   ├── materials.py             k, rho, cp, alpha
│   ├── hydration.py             calor de hidratación
│   └── grid.py, criteria.py, reliability.py, weather.py, plan.py, bim.py
├── scripts/
│   ├── run_1d_demo.py           demo 1D
│   ├── run_case.py              runner del caso 3D
│   └── inspect_ifc.py           inspección del IFC
├── tests/                       tests de verificación (24/24)
├── docs/                        documentación E01
│   ├── E01_respuestas_bim_difusion_solver1d.md / .docx
│   ├── E01_guia_revision_grupo.md
│   └── E01_preparacion_oral.md
└── resultados/
    └── demo_1d.png              resultado de la demo 1D
```

## Reproducir

```bash
pip install -r requirements.txt
python scripts/run_1d_demo.py
python -m pytest tests/
```

## Modelo BIM

`geometry/foundation.ifc` (IFC4): 5 vertidas `Vertida_01`..`Vertida_05` como
`IfcFooting`, planta octagonal de 18 m entre caras, espesor central 3.30 m,
pedestal Ø7 m. Property Set: `UANDES_HormigonMasivo`.

## Solver 1D

Esquema explícito FTCS:

    T_i^{n+1} = T_i^n + Fo * (T_{i+1}^n - 2*T_i^n + T_{i-1}^n),    Fo = alpha * dt / dx^2

Condiciones de borde: Dirichlet, Neumann, Robin. Estabilidad: `Fo <= 0.5`.

## Verificación

`python -m pytest tests/` → 24 tests pasan.

URL del repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
