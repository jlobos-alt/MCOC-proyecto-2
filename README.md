# MCOC — Proyecto 2: Hormigón masivo

## E00 — Kickoff y registro de repositorio

| Campo | Valor |
|---|---|
| **Grupo** | 1 |
| **Integrantes** | Clemente Sánchez, Matías Campos |
| **URL repositorio** | https://github.com/jlobos-alt/MCOC-proyecto-2 |
| **SHA inicial** | `f222414d01ed90b2d648077dc49701ad247c9907` |

## E01 — Semana 1 / miércoles: BIM, difusión y solver 1D

Preparación y evidencia para la revisión oral (BIM/IFC + física de difusión térmica + solver 1D).

- **Respuestas E01:** [`Respuestas_E01_BIM_Difusion_Solver1D.md`](Respuestas_E01_BIM_Difusion_Solver1D.md)
- **Documento Word:** `Respuestas_E01_BIM_Difusion_Solver1D.docx`
- **Guía de revisión:** [`docs/guia_revision_grupo.md`](docs/guia_revision_grupo.md)
- **Modelo IFC (BIM):** `modelo/foundation.ifc` (5 vertidas `IfcFooting` + Property Set `UANDES_HormigonMasivo`)
- **Solver / utilidades:** [`scripts/mcplan/`](scripts/mcplan/)
- **Tests:** [`tests/`](tests/)

### Cómo ejecutar

```bash
pip install -r requirements.txt
python -m pytest tests/
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

## Estructura del repositorio

```
.
├── datos/             # Datos climáticos / de entrada
├── docs/              # Documentación (guía de exposición, apuntes)
├── issues/            # Registro de issues / seguimiento de tareas
├── modelo/            # Modelos BIM/IFC y geometría de referencia
├── plantas_por_piso/  # Plantas y geometría por piso
├── scripts/           # Código: solver, simulación y utilidades
├── validacion/        # Casos y resultados de validación (Ju y Lei, ICH)
├── README.md
└── .gitignore
```

