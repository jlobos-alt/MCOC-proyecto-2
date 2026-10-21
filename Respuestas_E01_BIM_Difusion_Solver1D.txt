Respuestas E01 - BIM, difusión térmica y solver 1D

1) BIM / IFC

Pregunta: ¿Qué es BIM?
Respuesta: Es un proceso de modelado digital que integra geometría + información (materiales, propiedades, secuencia constructiva). No es solo un dibujo 3D, es una base de datos del proyecto.

Pregunta: ¿Qué es IFC?
Respuesta: Es un formato abierto (.ifc) estandarizado por buildingSMART (ISO 16739) para intercambiar información BIM entre distintos programas. Permite evitar la dependencia a un software propietario.

Pregunta: ¿Qué rol cumple Blender?
Respuesta: Es un modelador 3D. Sirve para crear y visualizar la geometría de la fundación.

Pregunta: ¿Qué agrega Bonsai?
Respuesta: Agrega la semántica IFC a Blender. Permite clasificar elementos (IfcFooting), crear la jerarquía espacial (IfcProject, IfcSite, IfcBuilding, IfcBuildingStorey), agregar Property Sets y exportar un .ifc correctamente.

Pregunta: ¿Por qué el solver no depende de Blender?
Respuesta: Porque la fuente de verdad es el archivo .ifc. El flujo es Blender + Bonsai → IFC → IfcOpenShell → geometría + propiedades → grilla → solver. Esto permite que corra por CLI, tests, HPC y sea reproducible. Si usáramos bpy, solo funcionaría dentro de Blender.

2) Física de difusión térmica

| Variable | Significado | Unidades (SI) |
|---|---|---|
| k | Conductividad térmica. Qué tan fácil transfiere calor por conducción. | W/(m·K) |
| rho | Densidad. Masa por unidad de volumen. | kg/m^3 |
| c_p | Calor específico a presión constante. Energía para subir 1 kg en 1 K. | J/(kg·K) |
| alpha | Difusividad térmica. alpha = k/(rho*c_p). Qué tan rápido se propaga un cambio de temperatura. | m^2/s |

Balance de energía: La variación de energía interna de un volumen es igual al calor neto que entra/sale por conducción, más la generación interna de calor.

Ecuación 1D con generación volumétrica (q_dot):

rho*c_p*∂T/∂t = k*∂^2T/∂x^2 + q_dot

En función de alpha:

∂T/∂t = alpha*∂^2T/∂x^2 + q_dot/(rho*c_p), alpha = k/(rho*c_p)

3) Condición Inicial y Condiciones de Borde

| Concepto | Fórmula | Explicación |
|---|---|---|
| Condición Inicial (CI) | T(x,0)=T0(x) | Temperatura de todo el dominio al inicio. Suele ser la temperatura de colocación. |
| Dirichlet | T(x_b,t)=T_fija | Se impone una temperatura fija en el borde. |
| Neumann | -k*∂T/∂x|_{x_b}=q''(t) | Se impone un flujo de calor. Si q''(t)=0, es un borde adiabático (sin intercambio). |
| Robin | -k*∂T/∂x|_{x_b}=h*(T_s(t)-T_inf(t)) | Representa convección entre la superficie (T_s) y el ambiente (T_inf). Es el más utilizado para intercambio con el aire. |

4) Discretización 1D y Estabilidad

Esquema Explícito FTCS (Forward Time, Centered Space):

T_i^{n+1} = T_i^n + Fo*(T_{i+1}^n - 2*T_i^n + T_{i-1}^n), Fo = alpha*Delta t/(Delta x)^2

Estabilidad: Es condicionalmente estable. Para conducción pura 1D, se debe cumplir:

Fo <= 0.5

Si Fo > 0.5, el esquema se vuelve inestable y genera oscilaciones numéricas que crecen exponencialmente.

Checklist:
- [ ] Tener URL del repo + commit SHA
- [ ] Mostrar modelo/foundation.ifc con Vertida_01-Vertida_05 (IfcFooting) + Property Set
- [ ] Saber explicar el solver 1D (loop, T_i^{n+1}, CCs, Fo)
- [ ] Tener README mínimo, requirements.txt y tests

