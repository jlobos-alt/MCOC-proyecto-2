# MCOC — Proyecto 2: Hormigón masivo

## E00 — Kickoff y registro de repositorio

| Campo | Valor |
|---|---|
| **Grupo** | 5 |
| **Sitio** | Pahuil / Chanco — Región del Maule |
| **Proyecto eólico** | Viento Pacífico Verde (en evaluación) |
| **Coordenadas** | -35.644721, -72.568332 |
| **URL repositorio** | https://github.com/jlobos-alt/MCOC-proyecto-2 |
| **SHA inicial** | `f222414d01ed90b2d648077dc49701ad247c9907` |

## E01 — Semana 1 / miércoles: BIM, difusión y solver 1D

Preparación y evidencia para la revisión oral (BIM/IFC + física de difusión térmica + solver 1D).

- **Entregable E01 (todo junto):** [`entregas/E01/`](entregas/E01/) — respuestas, guía, IFC, códigos 1D y resultados.
- **Respuestas E01:** [`docs/E01_respuestas_bim_difusion_solver1d.md`](docs/E01_respuestas_bim_difusion_solver1d.md) · [`.docx`](docs/E01_respuestas_bim_difusion_solver1d.docx)
- **Guía de revisión:** [`docs/E01_guia_revision_grupo.md`](docs/E01_guia_revision_grupo.md)
- **Guías del curso (G00–G08):** [`docs/guias/`](docs/guias/)
- **Modelo IFC (BIM):** [`modelo/foundation.ifc`](modelo/foundation.ifc) (5 vertidas `IfcFooting` + Property Set `UANDES_HormigonMasivo`)
- **Solver / utilidades:** [`scripts/mcplan/`](scripts/mcplan/)
- **Utilidades IFC:** [`scripts/ifc/`](scripts/ifc/)
- **Tests:** [`tests/`](tests/)

### Cómo ejecutar

```bash
pip install -r requirements.txt
python -m pytest tests/
python scripts/run_case.py --plan datos/caso_fundacion.yaml
```

### Entorno

- Python 3.12
- ifcopenshell, numpy, pytest
- Blender 5.2 + Bonsai (para modelado BIM/IFC)

## Contexto del proyecto

- Caso: hormigón masivo (control de temperatura por fisuración térmica).
- Límites de diseño: 70 °C (máx. temperatura interna) y 20 °C (diferencial máx. superficie–núcleo).
- Referencias: paper de Ju y Lei, especificación ICH.
- Flujo de trabajo: BIM → IFC → solver → confiabilidad.

## Sitio asignado (Grupo 5)

- **Sitio:** Pahuil / Chanco (Región del Maule), sitio costero.
- **Proyecto eólico de referencia:** Viento Pacífico Verde (en evaluación).
- **Coordenadas meteorológicas del caso docente:** `-35.644721, -72.568332`. Todos los scripts de clima deben usar estas coordenadas.
- **Estación DMC de contraste:** Dunas de Chanco (Pahuil) — https://climatologia.meteochile.gob.cl/application/informacion/fichaDeEstacion/350040
- **Fuente SEA:** https://www.sea.gob.cl/portal-de-participacion-ciudadana-y-consulta-indigena/proyecto/parque-eolico-viento-pacifico-verde

## Estructura del repositorio

```
.
├── datos/             # Datos de entrada y casos declarativos (plan.yaml)
├── docs/              # Documentación (respuestas E01, guías G00–G08)
│   └── guias/         # Guías del curso
├── entregas/          # Entregables por semana (E01, ...)
│   └── E01/           # Entrega 1: BIM + difusión + solver 1D
├── issues/            # Registro de issues / seguimiento de tareas
├── modelo/            # Modelos BIM/IFC (foundation.ifc)
├── plantas_por_piso/  # Plantas y geometría por piso
├── scripts/           # Código: solver (mcplan), utilidades IFC, demos
│   ├── mcplan/        # Solver térmico y confiabilidad
│   ├── ifc/           # Lectura/verificación IFC
│   └── demos/         # Scripts de prueba/demo
├── tests/             # Tests de verificación
├── validacion/        # Casos y resultados de validación (Ju y Lei, ICH)
├── requirements.txt
├── README.md
└── .gitignore
```

