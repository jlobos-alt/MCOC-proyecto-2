# Guía de revisión — Proyecto 2: Hormigón masivo (MCOC)

Documento de preparación para la revisión grupo por grupo. Cada pregunta tiene
una **respuesta corta** (la que hay que saber decir de memoria) y una
**profundización** (para cuando preguntan más).

Grupo 1 · Caso: hormigón masivo con control de temperatura por fisuración térmica.
Flujo de trabajo: **BIM → IFC → solver → confiabilidad**.

---

## 1. ¿Qué es BIM?

**Respuesta corta.** BIM (*Building Information Modeling*) no es un programa: es una
forma estructurada de representar y gestionar la información del activo
construido —identidad, geometría, materiales, propiedades, relaciones
espaciales, fases y cantidades— de modo que esa información sea **interoperable y
consultable por otras herramientas**, no solo dibujable.

**Profundización.**

- BIM es un *modelo de información* (no un modelo geométrico). Un archivo BIM
  tipicamente tiene: geometría + **datos semánticos** (clase del elemento,
  material, propiedades) + **relaciones** (agregación, contención, conexión).
- En este proyecto el modelo BIM debe expresar, por cada vertida:

  ```text
  Fundación
  ├── Vertida_01
  │   ├── geometría
  │   ├── hormigón = M1
  │   ├── T_colocación = 18 °C
  │   ├── inicio = 0 h
  │   └── aislación / retiro de moldaje
  ├── Vertida_02 …
  ```

- La razón de ser del BIM aquí: el **plan de vertidas** es información, no
  geometría. Cambiar la hora de una vertida o agregar aislación es una
  modification del modelo, no del código.
- Frase útil: **BIM ≠ solver ≠ visualizador**. Cada capa resuelve una cosa.

---

## 2. ¿Qué es IFC?

**Respuesta corta.** IFC (*Industry Foundation Classes*) es un estándar abierto
internacional (buildingSMART) para escribir de forma estandarizada y neutral
respecto del proveedor la descripción digital del entorno construido: objetos,
GUIDs, clases, tipos, geometría, materiales, *property sets* y relaciones.

**Profundización.**

- Es un formato de intercambio **semántico**, no solo geométrico: por eso el
  solver no necesita saber con qué programa se	modeló.
- Lo que nos interesa de verdad no es la geometría, sino los **property sets**:
  en `foundation_props.ifc` cada `IfcFooting` (Vertida_01…05) tiene un pset
  `UANDES_HormigonMasivo` con `VertidaID`, `Inicio_h`,
  `TemperaturaColocacion_C`, `TipoHormigon`, `Moldaje`, `Aislacion`,
  `RetiroMoldaje_h`.
- Relación clave: `IfcRelDefinesByProperties` liga el producto con su pset.
- Lo que IFC **no** es:
  - un solver,
  - un motor de diferencias finitas,
  - una API meteorológica,
  - un formato adecuado para millones de valores de temperatura.
- Referencia: https://technical.buildingsmart.org/standards/IFC/

---

## 3. ¿Qué rol cumple Blender?

**Respuesta corta.** Blender es la **autoría visual/BIM**: el lugar donde se
modela la geometría de la fundación y de sus vertidas. Es un editor: produce
archivos y geometría. No calcula temperatura ni decide nada.

**Profundización.**

- En el pipeline es la capa de entrada: `Bonsai / Blender → IFC → IfcOpenShell →
  voxelización → solver → Monte Carlo → resultados`.
- Se usa como malla (moldaje de la geometría) y como editor de escena.
- Todo lo que se necesita de Blender es: geometría + metadatos (qué es cada
  elemento, de qué material, cuándo se coloca).
- Lo que **no** debe hacer: bucear en el solver. Nada de esto:
  `solver leyendo directamente botones/objetos de Blender` — es el mal ejemplo
  explícito de la arquitectura del proyecto.

---

## 4. ¿Qué agrega Bonsai?

**Respuesta corta.** Bonsai es un *add-on* de Blender (Hugin) para BIM/IFC: aporta
el flujo **IFC → geometría editable en Blender** (crear, mover, parametrizar
elementos y exportar), con soporte de *property sets* y relaciones.

**Profundización.**

- Diferencia clave frente a un exportador genérico: el resultado sigue siendo
  **parametricamente editable** dentro de Blender y reexportable, no una malla
  muerta.
- En este proyecto: se define la fundación y sus vertidas en Blender vía
  Bonsai, se le cargan las propiedades del plan de vertidas y se exporta a IFC.
- El instalador del proyecto (`install_bonsai2.py`) activa el acceso en línea y
  sincroniza el repositorio de extensiones para instalar el paquete `bonsai`.
- Lo que aporta y lo que no:
  - **Aporta**: clase IFC, GUID, relaciones, geometría paramétrica, property sets.
  - **No aporta**: cálculo térmico, discretización, confiabilidad.
- Si se pregunta: *¿por qué no modelar directo en un BIM comercial?* →
  costo/licencias, y porque necesitamos control fino del mallado por voxel y
  trazabilidad completa del flujo.

---

## 5. ¿Por qué el solver no depende de Blender?

**Respuesta corta.** Porque el solver es una capa de **cálculo**, y el cálculo
debe poder correr y verificarse en cualquier máquina, con cualquier fuente de
geometría, y ser reproducible bit a bit. La dependencia se invierte: el modelo
BIM entra al solver como **datos**, no el solver leyendo un archivo de escena.

**Profundización.**

- Principio de la arquitectura: **separar IO de física**.

  ```python
  project = load_project(...)   # IO
  grid = build_grid(project)    # geometría computacional
  result = solve(grid, ...)     # física
  save_result(result)           # IO
  ```

- Consecuencias concretas:
  - **Verificabilidad**: los tests (1D/2D exactos, conservación de energía,
    fuente uniforme, Neumann, Robin) corren sin Blender instalado.
  - **Reproducibilidad**: la misma entrada (YAML/IFC) da el mismo resultado.
    Cada figura final debe tener script, input, commit, unidades.
  - **Portabilidad**: el solver puede ir a un cluster para el Monte Carlo / HPC;
    Blender no escala.
  - **Testabilidad**: el modelo debe ser *sometible a prueba*: cambiar hora,
    temperatura de colocación, intervalo entre vertidas, aislación o retiro de
    moldaje debe poder hacerse sin reprogramar.
- Y al revés: el solver **no** importa nada de Blender. El único punto de
  contacto es el archivo IFC (propiedades) y la geometría voxelizada.

---

## 6. Significado físico de k, ρ, c_p y α

**Respuesta corta.**

| Símbolo | Nombre | Unidad | Significado físico |
|---|---|---|---|
| $k$ | conductividad térmica | W/(m·K) | **facilidad del material para conducir calor**: a mayor $k$, más flujo por gradiente. Hormigón ≈ 2,22 W/(m·K); acero ≈ 50 (unas 20 veces más) |
| $\rho$ | densidad | kg/m³ | masa por volumen: define la inercia térmica y el peso propio |
| $c_p$ | calor específico | J/(kg·K) | **energía necesaria para subir 1 kg 1 °C**: define la capacidad de almacenar calor |
| $\alpha$ | difusividad térmica | m²/s | **velocidad con que se propaga el calor**: $\alpha = k/(\rho c_p)$ |

**Profundización.**

- $\rho c_p$ es la **capacidad calorífica volumétrica** [J/(m³·K)]: cuánta energía
  hace falta para calentar 1 m³ de hormigón 1 °C. Con los valores de Ju y Lei
  (2019): $\rho c_p = 2400 \times 970 = 2{,}33\times10^6$ J/(m³·K).
- $\alpha$ es el parámetro que realmente importa en la PDE:

  $$\frac{\partial T}{\partial t}=\alpha\nabla^2 T+\frac{\dot Q}{\rho c_p}$$

  → el hormigón tiene $\alpha \approx 9{,}5\times10^{-7}$ m²/s: **el calor se
  propaga muy lento** (unas 30 veces más lento que el agua). Por eso una
  cimentación de 2 m puede estar 40 °C más caliente en el núcleo que en la
  superficie varios días después de la vertida.
- Lectura dimensional de $\alpha$: m²/s = distancia²/tiempo → "distancia
  recorrida por el calor en el tiempo $t$" ~ $\sqrt{\alpha t}$.
- $\alpha$ es también el parámetro del **número de Fourier** y del criterio de
  estabilidad del esquema explícito.
- Dato de sanity check del paper: $k$ del suelo ≈ 1,39 W/(m·K), $\rho$ = 1800
  kg/m³, $c_p$ = 1273 J/(kg·K).

---

## 7. Balance de energía

**Respuesta corta.** Cada celda tiene una capacidad calorífica $C_i=\rho_i c_{p,i} V_i$
que acumula energía. Esa energía se gana o pierde por conducción hacia las
celdas vecinas, por el calor generado en la hidratación y por el intercambio
con el medio en la frontera. El balance por celda es:

$$\rho_i c_{p,i} V_i \frac{dT_i}{dt} = \sum_j G_{ij}(T_j-T_i) + \dot{Q}_i V_i + Q_{\text{borde},i}$$

**Profundización.**

- $G_{ij}$ es la **conductancia** entre celdas vecinas [W/K]:
  $$G_{ij}=\frac{k_{ij}A_{ij}}{d_{ij}}$$
  y para dos celdas de materiales distintos se usa la **media armónica**
  (las dos medias celdas están en serie):
  $$k_{ij}=\frac{2k_ik_j}{k_i+k_j}$$
  Esto importa en las interfaces: hormigón–suelo, vertida nueva–vertida vieja,
  hormigón–moldaje, hormigón–aislación.
- $\dot Q_i$ es el **calor volumétrico de hidratación** [W/m³], que sale de la
  curva de elevación adiabática: $\dot Q = \rho c_p\,\dfrac{d\theta_{ad}}{dt}$.
  Ojo con las unidades: $\theta_{ad}$ es temperatura acumulada [°C], $\dot Q$ es
  potencia por volumen [W/m³].
- $Q_{\text{borde},i}$ es el intercambio con el medio; en la formulación de
  redes de resistencias se escribe $G_{\text{borde},i}(T_\infty - T_i)$, es
  decir, con el mismo signo que la conducción.
- La forma "balance por celda" (volumen finito) se eligió porque maneja de
  forma transparente: materiales distintos, interfaces, celdas activas/inactivas,
  y resistencias superficiales (moldaje/aislación).
- **Conservación de energía**: en un dominio adiabático sin fuente,
  $E(t)=\sum_i \rho_i c_{p,i}V_iT_i$ debe permanecer constante. Es el test más
  poderoso, porque detecta errores de borde que un gráfico de temperatura no
  revela.

---

## 8. Condición inicial

**Respuesta corta.** Al inicio de cada vertida, la celda de hormigón vale la
**temperatura de colocación** $T_{col}$ (18 °C en nuestro caso); el resto del
dominio (suelo) tiene su temperatura propia. No hay una historia previa: la
simulación arranca con la geometría ya en su estado final, y cada vertida se
"activa" a su hora.

**Profundización.**

- Formalmente, para la celda $i$ de la vertida $v$:

  $$T_i(0^+)=T_{\text{col},v}\quad \text{si } i \in v, \qquad
  T_i(0)=T_{\text{suelo}}\quad \text{si no}$$

  y la celda no existe (no tiene capacidad ni fuente) antes de
  $t_v = \text{Inicio}_h(v)$; se activa a esa hora con $T_{col,v}$.

- Esto es lo que permite modelar la **secuencia constructiva**: las vertidas no
  se colocan todas a la vez. Una vertida solo existe a partir de su hora: el
  balance empieza cuando
  se coloca, y el calor se acumula desde ese instante.
- El perfil inicial no uniforme es lo que se necesita para verificar: en los
  tests se usa $T(x,0)=T_0+A\sin(\pi x/L)$, que tiene solución analítica.
- Consecuencia práctica: la temperatura de colocación es un **parámetro de
  diseño** (está en el IFC como `TemperaturaColocacion_C`) y una variable
  incierta en el análisis de confiabilidad.

---

## 9. Dirichlet, Neumann y Robin

**Respuesta corta.** Son las tres formas de cerrar el problema: la frontera es
donde la física entra al modelo.

- **Dirichlet**: se impone la temperatura en la frontera. $T=T_b$. Es la
  condición más fuerte y la más fácil de programar, pero también la menos
  realista para una superficie real.
- **Neumann**: se impone el flujo. $-k\nabla T\cdot\mathbf n = q''_n$. El caso
  importante es el **adiabático** ($q''_n=0$): la superficie no pierde calor
  (contacto con roca, o un plano de simetría).
- **Robin**: se impone el coeficiente de transferencia. $-k\nabla T\cdot\mathbf n
  = h(T_s-T_\infty)$. Es el modelo correcto para una superficie expuesta al
  aire: la superficie **puede estar bastante más caliente que el aire**.

**Profundización.**

| Condición | Significado | Uso en el proyecto | Riesgo |
|---|---|---|---|
| Dirichlet | $T$ impuesta | benchmark matemático, verificación 1D/2D/3D | transferencia superficial infinitamente eficiente |
| Neumann | flujo impuesto | adiabático, contacto con suelo rocoso | puede dar temperaturas irreales |
| Robin | $h$ dado | superficie expuesta, convección | subestima o sobrestima según $h$ |

- La forma de modelar moldaje y aislación en este proyecto es **Robin con
  resistencias en serie**:

  $$R_{tot}=\frac{\Delta x/2}{k_hA}+R_{\text{moldaje}}+R_{\text{aislación}}+\frac{1}{hA},
  \qquad Q=\frac{T_\infty-T_i}{R_{tot}}$$

  Es decir, cada capa (medio celda de hormigón, moldaje, aislación, convección)
  aporta una resistencia y las resistencias van **en serie**.
- Al retirar el moldaje **cambia la condición de frontera en el tiempo**: por
  eso el plan de vertidas necesita `RetiroMoldaje_h`. Es exactamente el tipo de
  decisión que el planificador debe representar.
- Pregunta de control que conviene hacer siempre: *¿qué mecanismo representa
  esta condición? ¿qué parámetro lo controla? ¿qué unidad tiene? ¿qué
  incertidumbre posee? ¿el resultado es sensible a esa hipótesis?* En hormigón
  masivo, las condiciones superficiales **controlan fuertemente** el diferencial
  térmico.

---

## 10. Discretización 1D

**Respuesta corta.** Se parte la barra en celdas de ancho $\Delta x$ con nodos en
$x_i=i\Delta x$ y tiempos $t^n=n\Delta t$, y se aproximan las derivadas con
diferencias centradas y primer orden en el tiempo (FTCS: *forward-time,
centered-space*):

$$\frac{\partial T}{\partial t}\approx\frac{T_i^{n+1}-T_i^n}{\Delta t},
\qquad
\frac{\partial^2T}{\partial x^2}\approx\frac{T_{i+1}^n-2T_i^n+T_{i-1}^n}{\Delta x^2}$$

que, para $\dot Q=0$, da la recurrencia

$$T_i^{n+1}=T_i^n+r\left(T_{i+1}^n-2T_i^n+T_{i-1}^n\right),
\qquad r=\frac{\alpha\Delta t}{\Delta x^2}$$

**Profundización.**

- El paso de tiempo es **explícito**: el nuevo valor depende solo de valores
  conocidos. Ventaja: simple, sin sistema lineal. Desventaja: condicional
  (ver §11).
- Para el caso no estacionario con fuente:

  $$T_i^{n+1}=T_i^n+r\left(T_{i+1}^n-2T_i^n+T_{i-1}^n\right)+\frac{\Delta t}{\rho c_p}\dot Q$$

- En el proyecto la forma usada en 3D es la de **balance por celda**
  (volumen finito), que en grilla uniforme y material homogéneo **coincide**
  con el stencil FTCS:

  $$\frac{G(T_j-T_i)}{C}=\frac{k\,\Delta y\Delta z/\Delta x}{\rho c_p\,\Delta x\Delta y\Delta z}(T_j-T_i)
  =\frac{\alpha}{\Delta x^2}(T_j-T_i)$$

  Es decir: mismo stencil, pero con la física (materiales, interfaces,
  fronteras) escrita de forma transparente.
- Verificación: con $T(x,0)=T_0+A\sin(\pi x/L)$ y $T(0,t)=T(L,t)=T_0$, la
  solución exacta es

  $$T(x,t)=T_0+A\sin\left(\frac{\pi x}{L}\right)e^{-\alpha(\pi/L)^2t}$$

  y el error $L_\infty$ debe **bajar al refinar $\Delta x$** con pendiente
  ≈ 2 (segundo orden en el espacio) → convección de segundo orden.
- Consecuencia del refinamiento: si $\Delta x$ se divide a la mitad, el paso de
  tiempo estable baja ~4 veces (ver §11). Es el costo real de la discretización.

---

## 11. Estabilidad del esquema explícito

**Respuesta corta.** Un esquema explícito es estable solo si el paso de tiempo
es suficientemente pequeño frente a la difusividad. En 1D: $r=\alpha\Delta
t/\Delta x^2 \le 1/2$, es decir

$$\Delta t \le \frac{\Delta x^2}{2\alpha}$$

En 2D: $r_x+r_y\le 1/2$ (y $\le 1/4$ si $\Delta x=\Delta y$). En 3D:
$r_x+r_y+r_z\le 1/2$ (y $\le 1/6$ si la grilla es cúbica).

**Profundización.**

- **Por qué**: si $r>1/2$ aparece un modo de oscilación no físico (patrón de
  "dientes de sierra" / *checkerboard*) cuya amplitud crece como $|1-4r|^n$. No
  es que la solución "explote" de inmediato: primero **oscila**, y por eso es
  más peligroso (pasa desapercibido en un gráfico).
- **Forma general** (grilla no uniforme):

  $$\alpha\Delta t\left(\frac{1}{\Delta x^2}+\frac{1}{\Delta y^2}+\frac{1}{\Delta z^2}\right)\le\frac12$$

- **Criterio derivado del balance de energía** (el que usa el solver, porque
  generaliza a materiales heterogéneos, convección, suelo y resistencias
  superficiales):

  $$\Delta t \lesssim \frac{C_i}{\sum_j G_{ij}+G_{\text{borde},i}}$$

  con $C_i=\rho_i c_{p,i}V_i$. Para grilla uniforme y un solo material, esto se
  reduce exactamente al criterio de Fourier.
- Es el **único** criterio que cubre el caso completo: $G_{\text{borde}}$ incluye
  convección, moldaje y aislación; $\sum_j G_{ij}$ incluye las interfaces
  entre materiales.
- Verificación: el test de conservación de energía en dominio adiabático detecta
  unstablez (se rompe la conservación) mucho antes que un test gráfico.
- En la práctica: con $\Delta x=0{,}3$ m y $\alpha\approx9{,}5\times10^{-7}$
  m²/s, $\Delta t \le \Delta x^2/(6\alpha)\approx 4{,}7$ h para 3D; el solver
  calcula el límite real desde el balance y aplica un factor de seguridad
  (0,8).
- Regla práctica de la guía: *"La implementación debe verificar estabilidad
  empírica y convergencia; no basta con copiar una fórmula."*

---

## Chuletario numérico (para responder de memoria)

| Magnitud | Valor |
|---|---|
| $k$ hormigón (Ju y Lei 2019) | 8,0 kJ/(m·h·°C) ≈ **2,22 W/(m·K)** |
| $c_p$ hormigón | 0,97 kJ/(kg·°C) = **970 J/(kg·K)** |
| $\rho$ hormigón | **2400 kg/m³** |
| $\alpha$ hormigón | **≈ 9,5×10⁻⁷ m²/s** |
| $k$ suelo | 5,0 kJ/(m·h·°C) ≈ **1,39 W/(m·K)** |
| Límite de temperatura máxima | $T_{max}\le$ **70 °C** |
| Límite de diferencial térmico | $\Delta T\le$ **20 °C** |
| Diferencial operacional | $\Delta T(t)=T_{max,\Omega}(t)-T_{min,S25}(t)$ |

Referencias del proyecto: ICH (Chile), *Especificación para Hormigón Masivo
Estructural* (2019) — Anexo 4, Método de Schmidt; Ju, Y. & Lei, H. (2019),
*Actual Temperature Evolution of Thick Raft Concrete Foundations and Cracking Risk
Analysis*, AMSE 7029671; Incropera et al., *Fundamentals of Heat and Mass
Transfer*.
