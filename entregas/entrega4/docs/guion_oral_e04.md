# Guion oral E04 — Revisión oral 2D/3D, CC, fuentes

## Posibles preguntas y respuestas

| Pregunta | Respuesta sugerida |
|---|---|
| **1) Escriba el balance de energía para un voxel** | $\rho c_p \frac{\partial T}{\partial t}\Delta V = \sum (q'' A)_{entrante} - \sum (q'' A)_{saliente} + \dot{Q}\Delta V$. Discretizado con FTCS se obtiene la actualización explícita. |
| **2) ¿Qué es $\mathrm{Fo}$ y qué condición exige?** | $\mathrm{Fo}=\frac{\alpha \Delta t}{\Delta x^2}$, $\alpha=k/(\rho c_p)$. Para FTCS explícito se requiere $\mathrm{Fo}\le 1/(2d)$ para estabilidad. |
| **3) Explique flujo y signos (Fourier)** | $q'' = -k\nabla T$. El calor fluye en dirección opuesta al gradiente de temperatura (hacia regiones más frías). |
| **4) ¿Qué es una superficie adiabática?** | Condición Neumann $q_n=0 \implies \partial T/\partial n=0$. No hay flujo de calor a través de la superficie. |
| **5) ¿Cómo se modela convección?** | Condición Robin: $-k\frac{\partial T}{\partial n}=h(T_s - T_\infty)$. Relaciona flujo conductivo en la pared con convección al fluido. |
| **6) Fuente volumétrica vs flujo superficial** | $\dot{Q}\,[W/m^3]$: generado/absorbido **dentro** del volumen (ej. hidratación). $q''\,[W/m^2]$: intercambia **por la superficie** (convección/radiación). |
| **7) ¿Cómo tratar dos materiales distintos?** | Cada voxel con sus $(k,\rho,c_p)$. En interfaz: continuidad de $T$ y continuidad de flujo $k_1 \partial T/\partial n_1 = k_2 \partial T/\partial n_2$. |
| **8) ¿Por qué las CC pueden dominar el resultado?** | Las CC controlan el intercambio con el exterior. Incluso con fuente volumétrica, $T_{max}$ y gradientes dependen de si hay adiabático, convección o temperatura impuesta. |
| **9) Muestre avance BIM** | Abrir `geometry/foundation.ifc` en Blender+Bonsai. Mostrar `Vertida_01..Vertida_05` tipo `IfcFooting`. |

## Archivos a tener abiertos
- `src/mcplan/thermal.py`
- `src/mcplan/boundary.py`
- `src/mcplan/thermal1d.py`
- `geometry/foundation.ifc` (en Blender+Bonsai)
