# Guion oral E05 — Batería de verificación térmica

Código: `src/mcplan/verificacion.py` (casos), `tests/test_bateria_e05.py` (tests),
`scripts/bateria_e05.py` (demo con parámetros).

## Idea general (30 s)

"Cada test arma una caja pequeña, la resuelve con **el mismo solver 3D** que usaremos para la
fundación y la compara con una solución exacta. Si el ayudante cambia L, n, el material, q₀, q_n o
h, el script recalcula la solución exacta con esos valores y vuelve a comparar."

## Por caso: qué decir

**Sinusoidal 1D/2D/3D.** Con bordes Dirichlet T₀, el seno es un modo propio del laplaciano:
∇²(sin sin sin) = −λ·(sin sin sin), con λ = Σ(π/Lᵢ)². Por eso solo decae como e^(−αλt) sin cambiar
de forma. Los ejes que no se usan tienen una celda y caras adiabáticas (así 1D y 2D salen del solver
3D). El error es de orden 2: el espacial es O(Δx²) y el temporal O(Δt), pero Δt ∝ Δx² por
estabilidad, así que todo escala como Δx². Por eso la convergencia da p ≈ 2.

**Energía adiabática.** En cada cara interior el flujo G(Tⱼ − Tᵢ) se suma a una celda y se resta
exactamente a la vecina. En la suma total se cancela, y si no hay bordes ni fuente, Σ CᵢTᵢ queda
constante hasta el redondeo (10⁻¹⁶). El campo inicial es aleatorio a propósito: se mezcla (el rango
baja de 30 °C a ~2 °C) pero la energía no cambia. Con fuente: E = E₀ + q₀·V·t.

**Fuente uniforme.** Si T es uniforme y todo es adiabático, no hay flujos y cada celda cumple
ρcp dT/dt = q₀. La subida es lineal, y Euler explícito integra una recta exactamente: error 10⁻¹⁴.
Unidades: q₀ [W/m³] / ρcp [J/(m³K)] = K/s. Con 1000 W/m³ en hormigón, 1,55 °C/h.

**Neumann.** −k ∂T/∂n = q_n, con n hacia afuera: q_n > 0 sale calor, q_n < 0 entra y q_n = 0 es
adiabático. En el balance de la celda de borde se suma −q_n·A. Hay dos chequeos:
- Balance: ΔE = −q_n·A·t exacto.
- Permanente con Dirichlet al otro lado: el flujo es constante, así que T es lineal,
  T = T_D − q_n(L − x)/k. Volúmenes finitos reproducen un perfil lineal exacto (error 10⁻⁷, que es lo
  que queda del transitorio).

**Robin.** −k ∂T/∂n = h(T − T∞). Se implementa como resistencias en serie desde el centro de la
celda: R = (Δx/2)/k + R_capas + 1/h, y G = A/R. En régimen permanente con Dirichlet en el otro
extremo, q = (T_D − T∞)/(L/k + 1/h), y el error es 10⁻¹³. Si h → ∞, 1/h → 0 y se recupera
Dirichlet. Con Bi ≪ 1 se cumple la capacidad agrupada, T∞ + (T₀ − T∞)e^(−t/τ) con τ = ρcpL/(2h).

**Estabilidad.** Δt ≤ Cᵢ/(ΣGᵢⱼ + G_b). En grilla uniforme eso es Fo ≤ 1/2, 1/4 o 1/6. Un borde
Dirichlet o Robin con h alto agrega G_b y achica el Δt. El test `test_dt_inestable_diverge` usa 3
veces el límite y la solución explota.

## Si piden modificar un caso en vivo

- Cambiar parámetros: ver la tabla del README (`python scripts/bateria_e05.py 2d --Ly 0.6 ...`).
- Hacer fallar a propósito: `python scripts/bateria_e05.py 1d --n 4` (malla gruesa → error > 2 %).
- Nuevo caso en pytest: copiar un test y cambiar los argumentos, por ejemplo
  `v.caso_robin_permanente(h=50, L=0.5)`.

## Bug encontrado al verificar (vale la pena contarlo)

La convergencia 1D salía con el error de n=40 mayor que el de n=20. La causa era que
`ceil(86400/174.5)` daba 496 en vez de 495 por redondeo en coma flotante, así que el solver hacía un
paso de más. Se corrigió con una tolerancia en el `ceil`. Es un buen ejemplo de para qué sirve
verificar.
