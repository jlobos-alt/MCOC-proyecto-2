# E04 — Revisión oral: 2D/3D, condiciones de borde y fuentes (4 puntos)

**Fecha:** Miércoles 28 de octubre, 10:30–13:20  
**Modalidad:** Revisión oral (sin informe)  
**Puntaje:** 4 puntos

## Objetivo
Demostrar dominio del solver térmico general antes de introducir hidratación y clima real.

## Avance mostrado en el repo

| Requisito | Ubicación | Comentario |
|---|---|---|
| 2D / 3D | `src/mcplan/thermal.py` | Solver explícito para malla 2D/3D |
| Dirichlet | `src/mcplan/boundary.py` | Temperatura impuesta |
| Neumann | `src/mcplan/boundary.py` | Flujo impuesto / adiabático ($q_n=0$) |
| Robin | `src/mcplan/boundary.py` | Convección $-k\frac{\partial T}{\partial n}=h(T_s-T_\infty)$ |
| Fuente volumétrica $\dot{Q}\,[W/m^3]$ | `src/mcplan/thermal.py` | Término fuente dentro del dominio |
| Modelo BIM del caso base | `geometry/foundation.ifc`, `evidencia/foundation.ifc` | 5 vertidas `IfcFooting` (`Vertida_01..05`) |

## Fórmulas clave (repaso oral)
- Balance (voxel): $\rho c_p \frac{\Delta T}{\Delta t} = \sum q_{in} - \sum q_{out} + \dot{Q}\,\Delta V$
- Conducción (Fourier): $q'' = -k\nabla T$
- Estabilidad FTCS (explícito): $\mathrm{Fo}=\alpha \frac{\Delta t}{\Delta x^2} \le \frac{1}{2d},\quad d\in\{1,2,3\}$
- Neumann (adiabático): $q_n=0 \implies \frac{\partial T}{\partial n}=0$
- Robin (convección): $-k\frac{\partial T}{\partial n}=h(T_s - T_\infty)$

## Evidencia / entrega (Canvas)
```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: (actual)
```

## Notas
El ICH (Anexo 4, método de Schmidt) fue revisado como referencia para el esquema explícito.
