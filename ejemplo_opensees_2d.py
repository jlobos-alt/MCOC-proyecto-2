"""
Ejemplo minimo 2D de OpenSeesPy
================================
Viga en voladizo (cantilever) con carga puntual en el extremo libre.

Modelo: 2 nodos, 1 elemento tipo "elasticBeamColumn" (viga Euler-Bernoulli).
Material: elastico lineal (E = 200 GPa, nu = 0.3).
Seccion:  rectangular 0.30 x 0.50 m.
Longitud: L = 3.0 m.
Carga:    P = -10 kN (hacia abajo) en el extremo libre.

Se compara el desplazamiento vertical del extremo libre con la solucion
analitica: delta = P*L^3 / (3*E*I)
"""

import openseespy.opensees as ops
import math

# ============================================================
# 1) PROPIEDADES DEL PROBLEMA
# ============================================================
E   = 200e6       # Modulo elastico [kN/m^2] (200 GPa = 200e6 kN/m^2)
nu  = 0.3         # Coeficiente de Poisson
A   = 0.30 * 0.50 # Area de la seccion transversal [m^2]
b   = 0.30        # Ancho [m]
h   = 0.50        # Altura [m]
Iy  = b * h**3 / 12.0  # Momento de inercia [m^4]
L   = 3.0         # Longitud de la viga [m]
P   = -10.0       # Carga puntual en el extremo libre [kN] (negativo = hacia abajo)

# Solucion analitica
delta_analitico = P * L**3 / (3.0 * E * Iy)

print("=" * 60)
print("  EJEMPLO MINIMO 2D - OpenSeesPy")
print("  Viga en voladizo con carga puntual")
print("=" * 60)
print(f"\nPropiedades:")
print(f"  E  = {E/1e6:.0f} GPa  |  A  = {A:.4f} m^2")
print(f"  Iy = {Iy:.6f} m^4  |  L  = {L:.1f} m")
print(f"  P  = {P:.1f} kN")
print(f"\nDesplazamiento analitico (extremo libre):")
print(f"  delta = P*L^3 / (3*E*I) = {delta_analitico*1000:.4f} mm")

# ============================================================
# 2) DEFINICION DEL MODELO EN OPENSEES
# ============================================================

# 2a) Inicializar el modelo: 2 dimensiones, 3 DOF por nodo (ux, uy, rz)
ops.wipe()
ops.model("basic", "-ndm", 2, "-ndf", 3)

# 2b) Nodos
#     Nodo 1 en el empotramiento (0, 0) - fijo
#     Nodo 2 en el extremo libre (L, 0) - libre
ops.node(1, 0.0, 0.0)
ops.node(2, L, 0.0)

# 2c) Condiciones de frontera (restricciones)
#     Nodo 1: empotrado (ux=0, uy=0, rz=0)
#     Nodo 2: libre (sin restricciones)
ops.fix(1, 1, 1, 1)  # 1 = restringido, 0 = libre
ops.fix(2, 0, 0, 0)

# 2d) Material elastico lineal
matTag = 1
ops.uniaxialMaterial("Elastic", matTag, E)

# 2e) Geometria de seccion (rectangular)
secTag = 1
G = E / (2.0 * (1.0 + nu))
J = 0.0
ops.section("Elastic", secTag, E, A, Iy, G, J)

# 2f) Grupo de integracion (1 punto de Gauss es suficiente para elastico)
geomTransfTag = 1
ops.geomTransf("Linear", geomTransfTag)

# 2g) Elemento viga elástica
eleTag = 1
ops.element("elasticBeamColumn", eleTag, 1, 2, A, E, Iy, geomTransfTag)

# ============================================================
# 3) CARGA Y ANALISIS
# ============================================================

# 3a) Carga puntual en el nodo 2 (extremo libre)
ops.timeSeries("Linear", 1)
ops.pattern("Plain", 1, 1)
ops.load(2, 0.0, P, 0.0)  # Fx=0, Fy=P, Mz=0

# 3b) Configurar el analisis (estatico lineal)
ops.system("BandGeneral")
ops.numberer("RCM")
ops.constraints("Plain")
ops.integrator("LoadControl", 1.0)
ops.algorithm("Linear")
ops.analysis("Static")
ops.analyze(1)

# ============================================================
# 4) RESULTADOS
# ============================================================
ux_nodo2 = ops.nodeDisp(2, 1)  # Desplazamiento horizontal
uy_nodo2 = ops.nodeDisp(2, 2)  # Desplazamiento vertical
rz_nodo2 = ops.nodeDisp(2, 3)  # Rotacion

print(f"\nResultados del modelo OpenSees:")
print(f"  Nodo 2 - ux = {ux_nodo2*1000:.4f} mm")
print(f"  Nodo 2 - uy = {uy_nodo2*1000:.4f} mm  (desplazamiento vertical)")
print(f"  Nodo 2 - rz = {rz_nodo2:.6f} rad  (rotacion)")

# ============================================================
# 5) VALIDACION: COMPARACION CON SOLUCION ANALITICA
# ============================================================
error_pct = abs((uy_nodo2 - delta_analitico) / delta_analitico) * 100

print(f"\n{'=' * 60}")
print(f"  VALIDACION")
print(f"{'=' * 60}")
print(f"  Analitico : {delta_analitico*1000:.6f} mm")
print(f"  OpenSees  : {uy_nodo2*1000:.6f} mm")
print(f"  Error     : {error_pct:.2e} %")
print(f"{'=' * 60}")

if error_pct < 1e-10:
    print("  RESULTADO: Los valores coinciden perfectamente.")
else:
    print("  RESULTADO: Hay una diferencia significativa - revisar el modelo.")

# Limpiar el modelo
ops.wipe()
