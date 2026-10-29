# E05 — Lab: batería de verificación térmica (3 puntos)

**Fecha:** jueves 29 de octubre, 10:30–12:30 · **Sin texto**: se evalúa el repo en el SHA declarado.

Carpeta autocontenida: `src/` (copia de `src/mcplan` de la raíz), `scripts/`, `tests/`, `results/e05/`.
Todos los casos usan el **solver 3D del proyecto** (`src/mcplan/thermal.py`, balance por celda),
no el 1D de E01–E03.

## Cómo correr (desde esta carpeta)

```powershell
pip install -r requirements.txt
python -m pytest tests -q                       # 46 tests (29 de E05 + 17 de E01/E03)
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
