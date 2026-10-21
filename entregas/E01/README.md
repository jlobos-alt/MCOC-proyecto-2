# E01 - BIM, difusión térmica y solver 1D

Entrega de la Semana 1 (miércoles): revisión oral de BIM/IFC + física de difusión térmica + solver 1D.

## Contenido de la entrega

| Carpeta / archivo | Descripción |
|---|---|
| `docs/respuestas_E01.md` / `.docx` | Respuestas escritas a las preguntas de la E01 (BIM, IFC, difusión, CI/CC, discretización y estabilidad). El `.docx` incluye las ecuaciones renderizadas como imágenes. |
| `docs/guia_revision_grupo.md` | Guía de preguntas y respuestas para la revisión oral. |
| `modelo_ifc/foundation.ifc` | Modelo BIM del proyecto: 5 vertidas (`Vertida_01`..`Vertida_05`, `IfcFooting`) más el Property Set `UANDES_HormigonMasivo`. |
| `codigo_1d/*.py` | Códigos 1D de referencia (FTCS) para las distintas condiciones de borde. |
| `resultados/*` | Salidas del caso de fundación (series temporales, campo final y resumen). |

## Códigos 1D

| Archivo | Caso | Condición de borde |
|---|---|---|
| `01_dirichlet.py` | Difusión con perfil inicial sinusoidal | Dirichlet en ambos bordes |
| `03_neumann.py` | Barra con un extremo fijo y otro aislado | Dirichlet izq. + Neumann adiabático der. |
| `04_robin.py` | Losa con convección y ambiente oscilante | Robin en ambos bordes |
| `05_calor_interno.py` | Difusión con generación de calor | Dirichlet + término fuente |

En todos se usa el esquema explícito **FTCS**:

    T_i^{n+1} = T_i^n + Fo * (T_{i+1}^n - 2*T_i^n + T_{i-1}^n),    Fo = alpha * dt / dx^2

con paso `r = Fo <= 0.5` para garantizar estabilidad en conducción pura 1D.

## Solver del proyecto

La implementación integrada (grilla, materiales, hidratación, fronteras, criterios
y confiabilidad) vive en `scripts/mcplan/` del repositorio. El caso declarativo
está en `datos/caso_fundacion.yaml` y la verificación numérica en
`tests/test_verificacion_termica.py`. El pipeline usa el `.ifc` como fuente de
verdad (Blender + Bonsai -> IFC -> IfcOpenShell -> solver), por lo que corre por
CLI y en tests sin depender de Blender.

## Reproducir

    pip install -r requirements.txt
    python scripts/run_case.py datos/caso_fundacion.yaml
    python -m pytest tests/

## Modelo IFC

`Vertida_01`..`Vertida_05` como `IfcFooting`, con el Property Set
`UANDES_HormigonMasivo` (VertidaID, Inicio_h, TemperaturaColocacion_C,
TipoHormigon, Moldaje, Aislacion, RetiroMoldaje_h).

URL del repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
