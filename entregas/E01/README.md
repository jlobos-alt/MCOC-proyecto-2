# E01 - Semana 1 / miércoles: BIM, difusión y solver 1D

Revisión oral (3 pts). Entrega en Canvas: repositorio + commit evaluado (+ nota
opcional de máximo 100 palabras sobre lo aún incompleto).

## Dónde está cada cosa (mapeo a la rúbrica)

### Comprensión física individual (1.0 pt)
- `docs/respuestas_E01.md` / `.docx` — k, rho, c_p, alpha; balance de energía; CI; Dirichlet/Neumann/Robin; discretización 1D; estabilidad (Fo <= 0.5).
- `docs/guia_revision_grupo.md` — guía de preguntas/respuestas para la oral.

### Comprensión BIM/IFC individual (0.7 pt)
- `docs/respuestas_E01.md` — qué es BIM, qué es IFC, rol de Blender, qué agrega Bonsai, por qué el solver no depende de Blender.
- `modelo_ifc/foundation.ifc` — modelo BIM: 5 vertidas (`Vertida_01`..`Vertida_05`, `IfcFooting`) + Property Set `UANDES_HormigonMasivo`.

### Capacidad de explicar el solver/código (0.8 pt)
- `solver/mcplan/thermal.py` — núcleo FTCS: `T_i^{n+1}`, balance de energía, criterio de estabilidad.
- `solver/mcplan/boundary.py` — condiciones Dirichlet / Neumann / Robin.
- `solver/mcplan/materials.py` — k, rho, c_p, alpha.
- `solver/mcplan/hydration.py` — fuente interna (calor de hidratación).
- `solver/mcplan/grid.py`, `criteria.py`, `reliability.py`, `weather.py`, `plan.py`.
- `codigo_1d/*.py` — casos 1D de referencia (Dirichlet, Neumann, Robin, calor interno), esquema FTCS con `r = Fo <= 0.5`.

### Estado real y reproducible del repositorio (0.5 pt)
- `solver/requirements.txt` — entorno reproducible.
- `solver/tests/test_verificacion_termica.py` — 5 tests (1D y 2D vs solución analítica, conservación de energía, fuente uniforme, Robin).
- `solver/run_case.py` + `solver/datos/caso_fundacion.yaml` — runner del caso.
- `resultados/` — salidas del caso base (series, campo final/peak, resumen).
- `README.md` (raíz del repo) — README mínimo + cómo ejecutar.

## Reproducir (desde esta carpeta)

    cd solver
    pip install -r requirements.txt
    python run_case.py --plan datos/caso_fundacion.yaml
    python -m pytest tests/

## Resultado del caso base

- T_maxima = 58.16 °C vs 70.0 °C -> OK (h = 103.0 h)
- diferencial_termico = 38.03 °C vs 20.0 °C -> NO CUMPLE (h = 143.0 h)

Caso base sin estrategia de control: cumple T_max pero no el diferencial.
Pendiente de mitigación (aislación, vertidas por capas, secuencia constructiva).

## Modelo IFC (BIM)

`Vertida_01`..`Vertida_05` como `IfcFooting`, con el Property Set
`UANDES_HormigonMasivo` (VertidaID, Inicio_h, TemperaturaColocacion_C,
TipoHormigon, Moldaje, Aislacion, RetiroMoldaje_h).

URL del repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
