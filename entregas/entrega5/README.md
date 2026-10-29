# E05 — Lab: batería de verificación térmica (3 puntos)

**Fecha:** jueves 29 de octubre, 10:30–12:30 · **Sin texto**: se evalúa el repo en el SHA declarado.

Carpeta autocontenida: `src/` (copia de `src/mcplan` de la raíz), `scripts/`, `tests/`, `results/e05/`.
Todos los casos usan el **solver 3D del proyecto** (`src/mcplan/thermal.py`, balance por celda),
no el 1D de E01–E03.

## Cómo correr (desde esta carpeta)

```powershell
pip install -r requirements.txt
python -m pytest tests -q                       # 52 tests (29 batería E05 + 6 bloque + 17 de E01/E03)
python -m pytest tests/test_bateria_e05.py -v   # solo la batería E05
python scripts/bateria_e05.py                   # tabla PASA/FALLA de los 13 casos
python scripts/bateria_e05.py --figuras         # + figuras en results/e05/
```

### Cambiar parámetros en vivo (lo que pedirá el ayudante)

| Caso | Comando de ejemplo |
|---|---|
| 1D exacta | `python scripts/bateria_e05.py 1d --Lx 2 --n 40 --t_h 48` |
| 2D sinusoidal | `python scripts/bateria_e05.py 2d --Lx 1 --Ly 0.6 --n 30` |
| 3D sinusoidal | `python scripts/bateria_e05.py 3d --Lx 1.2 --Ly 0.8 --Lz 0.5 --A 15` |
| Orden de convergencia | `python scripts/bateria_e05.py convergencia --dim 3` |
| Energía adiabática (± fuente) | `python scripts/bateria_e05.py energia --q0 2000` |
| Fuente uniforme | `python scripts/bateria_e05.py fuente --q0 500 --t_h 72` |
| Neumann | `python scripts/bateria_e05.py neumann --qn -200` |
| Robin | `python scripts/bateria_e05.py robin --h 25 --TD 60 --Tinf 10` |
| Otro material | `... --k 1.39 --rho 1800 --cp 1273` (suelo de Ju & Lei) |

Por defecto el material es el hormigón de Ju & Lei: k = 2,22 W/(m·K), ρ = 2400 kg/m³,
cp = 970 J/(kg·K), α ≈ 9,5·10⁻⁷ m²/s.

## Batería y mapeo a la rúbrica

| Criterio (pts) | Caso | Solución exacta | Resultado (por defecto) |
|---|---|---|---|
| **Batería funcionando (1,2)** | 1D exacta, Dirichlet | T₀ + A sin(πx/L) e^(−αλt), λ = (π/L)² | error rel. 1,0·10⁻³ |
| | 2D sinusoidal | λ = (π/Lx)² + (π/Ly)² | 2,0·10⁻³ |
| | 3D sinusoidal | λ = (π/Lx)² + (π/Ly)² + (π/Lz)² | 3,0·10⁻³ |
| | Orden de convergencia 1D/2D/3D | p = log(e_n/e_2n)/log 2 | p = 1,99 / 1,98 / 1,98 |
| | Δt inestable diverge | Fo sobre el límite → explota | `test_dt_inestable_diverge` |
| **Conservación / fuente (0,6)** | Caja adiabática, campo inicial aleatorio | Σ ρcpV T = cte | error rel. ~10⁻¹⁶ |
| | Caja adiabática + fuente q₀ | E(t) = E₀ + q₀ V t | ~10⁻¹⁶ |
| | Fuente uniforme | dT/dt = q₀/(ρcp) → T = T₀ + q₀t/(ρcp) | 3·10⁻¹⁴ °C |
| **Condiciones de borde (0,6)** | Neumann, balance | ΔE = −q_n A t | ~10⁻¹⁶ |
| | Neumann + Dirichlet, permanente | T(x) = T_D − q_n (L − x)/k | 10⁻⁷ °C |
| | Robin + Dirichlet, permanente | q = (T_D − T∞)/(L/k + 1/h) | 5·10⁻¹³ °C |
| | Robin con h → ∞ | tiende a Dirichlet | `test_robin_h_grande_tiende_a_dirichlet` |
| | Robin transitorio (Bi ≪ 1) | capacidad agrupada, τ = ρcpL/(2h) | 2,7·10⁻³ |
| **Oral / modificar casos (0,6)** | ver [docs/guion_oral_e05.md](docs/guion_oral_e05.md) y la tabla de comandos | | |

El error de los casos sinusoidales es max|T − T_exacta| dividido por la amplitud que queda,
A·e^(−αλt). Así, un tiempo largo (con el seno ya apagado) no hace pasar el test por tener todo cerca
de T₀. La tolerancia es 2 %. Con una malla gruesa el test **sí falla** (por ejemplo `1d --n 4`), que
es justo lo que debe pasar.

## Figuras (`results/e05/`)

`e05_sinusoidal_{1d,2d,3d}.png` (numérica vs exacta + error), `e05_convergencia.png` (pendiente 2),
`e05_energia.png`, `e05_fuente.png`, `e05_neumann.png`, `e05_robin.png`, `e05_robin_t.png`.

## Visualizador térmico interactivo

```powershell
python scripts/visualizador_termico.py          # abre la ventana
python scripts/verificar_visualizador.py        # verificación completa (~1 min, termina en TODO OK)
```

Archivo: [`scripts/visualizador_termico.py`](scripts/visualizador_termico.py) (también en
`scripts/` de la raíz del repo). Usa el mismo solver 3D (`build_model` + `solve`), con matplotlib;
no requiere instalar nada más.

- **8 casos:** seno 1D, 2D y 3D; Dirichlet base/techo; adiabático dT/dn = 0; Robin
  −k dT/dn = h(T − T_aire) con h = k·β; fuente q₀; Neumann q_n. Los casos de borde usan el bloque de
  3 × 3 × 0,6 m con caras laterales adiabáticas.
- **Paneles:**
  - Mapa térmico: barra en 1D, placa en 2D y voxels con un corte en 3D.
  - Perfil por el centro: solver vs solución exacta.
  - Curva de calor T(t) en puntos de control.
  - Slider de tiempo y botón **Animar**.
- **Sliders:** n, t final, Lx, Ly, Lz, y los parámetros propios de cada caso (T, A, β, q₀, q_n).
  Cada caso conserva sus valores. La escala de colores es fija por caso, así que un cambio de β o
  q_n se ve en el color.
- **Solución exacta en cada instante:**
  - Senos: el modo propio que decae.
  - Dirichlet y adiabático: series de Fourier.
  - Robin: autovalores de tan(μH) = −μk/h.
  - Neumann: cos((m−½)πz/H).
  - Fuente: recta.
- **Protección:** si la combinación de sliders exige más de 100 000 pasos (Δt ∝ Δx²), avisa en vez
  de congelarse.

`verificar_visualizador.py` hace 112 chequeos:
- Barre cada parámetro hasta los extremos del slider y compara con la exacta en los 40 instantes.
  El error es ≤ 0,3 % del rango con n ≥ 8.
- Revisa Δt estable, principio del máximo y energía.
- Revisa tendencias físicas: más β da un techo más frío; duplicar q₀ duplica la subida; el signo de
  q_n decide si entra o sale calor; el seno 3D se enfría antes que el 2D, y el 2D antes que el 1D.
- Revisa la interfaz.

El único caso que no cumple ≤ 2 % es Dirichlet con t = 1 h y n = 12, porque el calor todavía no
cruza una celda. Ahí se verifica que el error **converja al refinar** (0,21 → 0,025 → 0,005 °C).

**Tres condiciones de borde en el bloque 3 × 3 × 0,6 m**, sin ventana:
`python scripts/casos_borde_bloque.py --figura` (Dirichlet 20/30 °C, dT/dn = 0, Robin β), con sus
tests en `tests/test_casos_borde_bloque.py` y la figura en `results/casos_borde/perfiles.png`.

## Cambios al solver hechos para esta entrega

1. **Neumann con flujo impuesto en 3D** (`tipo: neumann`, `flujo_W_m2`). Antes solo existía el
   caso adiabático. La cara aporta Q = −q_n·A al balance de su celda (n hacia afuera, q_n > 0 sale
   calor). No agrega conductancia, así que no cambia el Δt estable.
2. **Fuente volumétrica constante** `solve(..., fuente_W_m3=q0)`, que se suma al calor de hidratación.
3. **Celdas no cúbicas** (`geometria.dy`, `geometria.dz` opcionales). Permite cualquier Lx, Ly, Lz
   con n celdas por eje.
4. **Bug corregido: un paso de más.** `ceil(86400/dt)` daba a veces 496 en vez de 495 por redondeo,
   y el campo final quedaba un Δt después del tiempo pedido. Se detectó porque la convergencia 1D
   salía no monótona (el error con n=40 era mayor que con n=20).

## Evidencia (Canvas)

```
Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2
Commit evaluado: <SHA completo de git rev-parse HEAD>
```
