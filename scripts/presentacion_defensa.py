"""Presentación de la defensa F02 (Grupo 5): poco texto, figuras reales y guion en las notas.

    python scripts/figuras_presentacion.py      # figuras nuevas (escenarios, MΔ(t))
    python scripts/presentacion_defensa.py      # escribe entregas/defensa/Presentacion_Defensa_G5.pptx
"""
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "entregas" / "defensa" / "Presentacion_Defensa_G5.pptx"
FIG = ROOT / "results" / "defensa"

INK = RGBColor(0x1D, 0x2D, 0x35)
MUTED = RGBColor(0x5B, 0x6B, 0x73)
LIGHT = RGBColor(0xF1, 0xF4, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ORANGE = RGBColor(0xE7, 0x6F, 0x51)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
SAND = RGBColor(0xE9, 0xC4, 0x6A)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREEN_BG = RGBColor(0xDC, 0xEF, 0xE3)
RED_BG = RGBColor(0xF6, 0xDF, 0xDB)
CONCRETE = RGBColor(0xC9, 0xC2, 0xB6)
FONT = "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = 13.333, 7.5


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False):
    """runs: str, o lista de párrafos; cada párrafo str o lista de (texto, {opciones})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        partes = p if isinstance(p, list) else [(p, {})]
        for t, o in partes:
            r = para.add_run()
            r.text = t
            r.font.name = FONT
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", italic)
            r.font.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill, line=None, radius=True):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.5)
    s.shadow.inherit = False
    return s


def image(slide, path, x, y, w=None, h=None):
    im = Image.open(path)
    ar = im.size[1] / im.size[0]
    if w is not None and h is not None:
        if w * ar > h:
            w = h / ar
        else:
            h = w * ar
    elif w is not None:
        h = w * ar
    else:
        w = h / ar
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    return w, h


def title(slide, t, sub=None, dark=False):
    text(slide, 0.6, 0.35, 12.1, 0.8, t, size=32, bold=True, color=WHITE if dark else INK)
    if sub:
        text(slide, 0.6, 1.08, 12.1, 0.45, sub, size=16, color=SAND if dark else MUTED)


def footer(slide, n, dark=False):
    c = RGBColor(0x9A, 0xA5, 0xAB)
    text(slide, 0.6, 7.05, 6, 0.3, "Grupo 5 · Defensa F02 · 19-nov-2026", size=10, color=c)
    text(slide, 11.73, 7.05, 1.0, 0.3, str(n), size=10, color=c, align=PP_ALIGN.RIGHT)


def chip(slide, x, y, w, t, fill=LIGHT, color=INK, size=14, h=0.45, bold=False):
    s = box(slide, x, y, w, h, fill)
    s.adjustments[0] = 0.5
    text(slide, x + 0.15, y, w - 0.3, h, t, size=size, color=color, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, bold=bold)


def stat(slide, x, y, w, h, valor, etiqueta, limite, color, fill=LIGHT):
    box(slide, x, y, w, h, fill)
    text(slide, x + 0.3, y + 0.25, w - 0.6, 1.0, valor, size=44, bold=True, color=color)
    text(slide, x + 0.3, y + 1.25, w - 0.6, 0.4, etiqueta, size=16, bold=True, color=INK)
    text(slide, x + 0.3, y + 1.65, w - 0.6, 0.4, limite, size=13, color=MUTED)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def table(slide, x, y, w, rows, col_w, size=13, header_fill=INK, row_h=0.42, fills=None):
    nr, nc = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
    t = gt.table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, fila in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, val in enumerate(fila):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame
            tf.text = ""
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(val)
            r.font.name = FONT
            r.font.size = Pt(size)
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = header_fill
                r.font.color.rgb = WHITE
                r.font.bold = True
            else:
                f = fills(i, j) if fills else None
                c.fill.fore_color.rgb = f or (WHITE if i % 2 else LIGHT)
                r.font.color.rgb = INK
    return t


def bold_row(t, i):
    for c in t.rows[i].cells:
        for p in c.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True


# ---------------------------------------------------------------- 1. Portada
s = prs.slides.add_slide(BLANK)
bg(s, INK)
text(s, 0.7, 1.5, 6.6, 0.5, "MCOC · PROYECTO 2 · HORMIGÓN MASIVO", size=14, bold=True, color=SAND)
text(s, 0.7, 2.05, 6.6, 2.0, "Plan de vertidas para la fundación del aerogenerador", size=40, bold=True, color=WHITE)
text(s, 0.7, 4.35, 6.6, 0.5, "Grupo 5 · José Lobos · Clemente Sánchez · Matías Campos", size=18, color=WHITE)
text(s, 0.7, 4.85, 6.6, 0.5, "Defensa F02 · jueves 19 de noviembre de 2026", size=16, color=RGBColor(0xB8, 0xC4, 0xC9))
box(s, 7.6, 1.2, 5.1, 3.85, WHITE)
image(s, ROOT / "results/e06/bim_base_3d.png", 7.75, 1.3, w=4.8, h=3.6)
text(s, 7.6, 5.2, 5.1, 0.4, "IFC (Bonsai): 5 sólidos · 636,9 m³ · Pahuil / Chanco", size=13,
     color=RGBColor(0xB8, 0xC4, 0xC9), align=PP_ALIGN.CENTER)
notes(s, "MATÍAS (0:10). Buenos días. Somos el Grupo 5 y vamos a defender nuestro plan de vertidas para la "
         "fundación de hormigón masivo del aerogenerador.")

# ---------------------------------------------------------------- 2. La decisión
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Colocar todo en una sola vertida continua de 15,9 h")
chip(s, 0.6, 1.25, 3.0, "Bomba 40 m³/h, por capas")
chip(s, 3.8, 1.25, 2.6, "Hormigón a 10 °C")
chip(s, 6.6, 1.25, 4.1, "EPS 150 mm: laterales + manta superior")
w = 2.85
for i, (v, e, l, c, f) in enumerate([
        ("15,9 h", "Duración D", "mínimo posible con una bomba", INK, LIGHT),
        ("0 %", "Probabilidad de falla", "límite 5 % · 24 escenarios", TEAL, GREEN_BG),
        ("17,6 °C", "MΔ peor escenario", "límite 20 °C · malla fina", ORANGE, LIGHT),
        ("49,5 °C", "MT máxima", "límite 70 °C", ORANGE, LIGHT)]):
    stat(s, 0.6 + i * (w + 0.25), 2.25, w, 2.3, v, e, l, c, f)
box(s, 0.6, 4.95, 12.15, 1.55, INK)
text(s, 0.95, 4.95, 11.5, 1.55,
     [[("Es el plan más rápido posible con los recursos declarados ", {"color": WHITE}),
       ("y cumple en los 24 escenarios ", {"color": SAND, "bold": True}),
       ("(8 curvas × 3 climas).", {"color": WHITE})]], size=22, anchor=MSO_ANCHOR.MIDDLE)
footer(s, 2)
notes(s, "MATÍAS (0:35). Nuestra recomendación es colocar toda la fundación en una sola vertida continua, por capas, "
         "con una bomba de 40 m3/h, hormigón a 10 °C y 150 mm de EPS en los laterales y como manta superior. Termina "
         "en 15,9 horas, que es el mínimo posible con esa bomba. Bajo las 8 curvas del profesor y 3 climas, la "
         "probabilidad de falla es 0, frente al límite de 5 %. En el peor escenario, el diferencial llega a 17,6 °C "
         "con la malla fina, bajo los 20 °C, y la temperatura máxima es 49,5 °C. Ahora explicamos cómo llegamos aquí.\n\n"
         "Para saber: MΔ es la diferencia, en cada instante, entre la T máxima del hormigón y la mínima a 25 mm bajo "
         "las caras expuestas; se toma su máximo en los 14 días. 17,6 °C = peor escenario (M4_SS, clima medio) con "
         "malla de 0,125 m; con 0,5 m da 15,96 °C.")

# ---------------------------------------------------------------- 3. Problema de decisión
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "48 planes evaluados: solo cumple colocar sin pausas")
chip(s, 0.6, 1.25, 4.4, "t₀ = 19-nov 08:00 · America/Santiago")
chip(s, 5.2, 1.25, 3.4, "1 bomba → D ≥ 636,9 / 40 = 15,9 h")
chip(s, 8.8, 1.25, 3.95, "2 × 5 × 4 × 2 = 48 planes × 24 esc.")
image(s, FIG / "defensa_D_vs_Pf.png", 0.6, 2.0, w=12.15)
text(s, 0.6, 6.6, 12.15, 0.4, "Partición {5 vertidas, única} × espera {0, 6, 12, 24, 48 h} × protección {ninguna, EPS 50, 100, 150} "
     "× T_col {18, 10 °C}. Círculo = plan elegido.", size=12, color=MUTED)
footer(s, 3)
notes(s, "MATÍAS (0:45). La duración se mide desde un mismo inicio para todos los planes: el jueves 19 a las 8 de la "
         "mañana, hora de Chile. Con una bomba de 40 m3/h y sin vertidas simultáneas, colocar los 636,9 m3 toma como "
         "mínimo 15,9 horas. Evaluamos 48 planes: 5 vertidas o una sola, 5 tiempos de espera, 4 protecciones y 2 "
         "temperaturas de colocación, cada uno en 24 escenarios. En el gráfico de la izquierda, cada punto es un plan: "
         "su duración y su probabilidad de falla. Solo cumplen los de colocación continua, abajo a la izquierda, y el "
         "círculo es el nuestro. A la derecha se ve por qué: esperar entre vertidas sube el diferencial. Nuestra "
         "optimalidad vale dentro de esta familia. Criterio: el más rápido con P_f <= 5 %, desempate por mayor margen.")

# ---------------------------------------------------------------- 4. Datos
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Tres datos reales conectados al solver")
box(s, 0.6, 1.35, 4.3, 5.4, LIGHT)
text(s, 0.85, 1.5, 3.9, 0.4, "1 · Geometría (IFC)", size=18, bold=True)
image(s, ROOT / "results/e06/bim_base_3d.png", 0.85, 2.0, w=3.8)
text(s, 0.85, 5.0, 3.9, 1.6, ["636,9 m³ · 5 sólidos", "Voxeles 0,5 m → 4 656 celdas", "Error de volumen 0,52 %"],
     size=15, color=INK)
text(s, 5.2, 1.4, 7.5, 0.4, "2 · Ocho curvas de calor Q(t) [W/m³] · misma mezcla, campañas SS y 22A", size=17, bold=True)
image(s, FIG / "defensa_curvas.png", 5.2, 1.85, w=7.55)
text(s, 5.2, 4.35, 7.5, 0.4, "3 · Clima: ensemble GFS del 17-nov (31 miembros) → 3 historias", size=17, bold=True)
image(s, FIG / "defensa_clima.png", 5.2, 4.75, h=2.15)
footer(s, 4)
notes(s, "MATÍAS (0:45). Los tres insumos reales están conectados al solver. La geometría sale del IFC guardado con "
         "Bonsai y se pasa a cubitos de medio metro, con 0,5 % de error de volumen. Las 8 curvas del profesor son "
         "fuentes de calor en W/m3, de cuatro probetas de una misma mezcla en dos campañas; la 22A es de menor "
         "confianza según el propio archivo. El clima es el ensemble GFS del 17 de noviembre: de 31 miembros armamos "
         "tres historias completas con su peso (35,5 / 32,3 / 32,3 %), y las horas que no cubre se completan con ERA5. "
         "Todo queda guardado con su hash. Le paso a José.")

# ---------------------------------------------------------------- 5. Modelo físico
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Modelo: balance de calor con fuente por edad")
box(s, 0.6, 1.3, 12.15, 0.85, INK)
text(s, 0.6, 1.3, 12.15, 0.85, [[("ρ·cp·∂T/∂t = ∇·(k∇T) + q_h(a)", {"bold": True, "color": WHITE, "size": 26}),
                                  ("      a = edad de cada celda, desde que llega el hormigón", {"color": SAND, "size": 16})]],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
# corte esquemático de la fundación (escala horizontal 0,36"/m, vertical exagerada 0,6"/m)
ox, oz, sc, sz = 6.65, 6.0, 0.36, 0.6
pts = [(-9, 0), (9, 0), (9, 1.1), (3.5, 3.3), (3.5, 4.3), (-3.5, 4.3), (-3.5, 3.3), (-9, 1.1)]
ff = s.shapes.build_freeform(Inches(ox + pts[0][0] * sc), Inches(oz - pts[0][1] * sz), scale=1.0)
ff.add_line_segments([(Inches(ox + x * sc), Inches(oz - z * sz)) for x, z in pts[1:]], close=True)
sh = ff.convert_to_shape()
sh.fill.solid()
sh.fill.fore_color.rgb = ORANGE
sh.line.fill.background()
# aislación (laterales + techo) como contorno
ext = [(-9.3, 0), (-9.3, 1.18), (-3.8, 3.4), (-3.8, 4.45), (3.8, 4.45), (3.8, 3.4), (9.3, 1.18), (9.3, 0)]
ff = s.shapes.build_freeform(Inches(ox + ext[0][0] * sc), Inches(oz - ext[0][1] * sz), scale=1.0)
ff.add_line_segments([(Inches(ox + x * sc), Inches(oz - z * sz)) for x, z in ext[1:]], close=False)
sh = ff.convert_to_shape()
sh.fill.background()
sh.line.color.rgb = TEAL
sh.line.width = Pt(6)
box(s, ox - 10.5 * sc, oz, 21 * sc, 0.5, CONCRETE, radius=False)
text(s, ox - 10.5 * sc, oz, 21 * sc, 0.5, "Base: suelo 1D · R = e/k hacia T del suelo a 1 m", size=14, color=INK,
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, ox - 1.9, oz - 1.55, 3.8, 0.9, ["Cada celda nace a 10 °C", "y genera q_h(a) de su curva"], size=15,
     color=WHITE, bold=True, align=PP_ALIGN.CENTER)
# rótulos
text(s, ox - 2.5, 2.4, 5.0, 0.8, [[("Techo: ", {"bold": True, "color": TEAL}), ("manta EPS 150 mm", {})],
                                  [("también sobre los techos temporales", {"color": MUTED, "size": 13})]], size=15,
     align=PP_ALIGN.CENTER)
text(s, 0.6, 4.75, 2.7, 1.0, [[("Laterales", {"bold": True, "color": TEAL})], "Moldaje 72 h + EPS 150 mm"], size=15)
text(s, 10.0, 2.55, 2.75, 1.5, [[("Clima (Robin)", {"bold": True, "color": TEAL})], "h = 5,7 + 3,8·v + h_rad",
                                 "T∞ = T sol-aire"], size=15)
text(s, 10.0, 4.1, 2.75, 1.5, [[("Propiedades", {"bold": True, "color": TEAL})], "k = 2,22 W/(m·K)",
                                "ρ = 2476 · cp = 1023"], size=15)
footer(s, 5)
notes(s, "JOSÉ (1:00). El modelo es el balance de energía continuo: lo que se acumula es lo que llega por conducción "
         "más el calor del cemento, en W/m3. Cada celda tiene su propia edad, que parte en cero cuando el hormigón "
         "llega a su altura, y nace a la temperatura de colocación. La fuente es cada curva entera según la edad, con "
         "las propiedades de sus probetas. Los bordes cambian por etapa: laterales con moldaje y EPS, la superficie con "
         "manta incluso en los techos temporales, y la base contra el suelo con una resistencia equivalente. El clima "
         "entra por el coeficiente h y la temperatura sol-aire, sin contar la radiación dos veces.\n\n"
         "Robin con normal saliente: -k dT/dn = (T - Tinf)/R, con R la suma en serie de convección, moldaje y "
         "aislación. k de Ju & Lei; rho y cp de las probetas de las curvas.")

# ---------------------------------------------------------------- 6. Solver y verificación
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "El solver está verificado; la malla es lo que más pesa")
box(s, 0.6, 1.3, 12.15, 0.75, LIGHT)
text(s, 0.6, 1.3, 12.15, 0.75, "C·dT/dt = Σ G·(T_j − T_i) + (A/R)·(T∞ − T_i) + q·V      G = k·A/d · Euler explícito · Δt ≤ C/ΣG",
     size=19, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.6, 2.3, 5.8, 0.4, "Contra solución exacta: el error cae 4× al dividir Δx por 2", size=16, bold=True)
image(s, ROOT / "results/e06/convergencia_espacial.png", 0.6, 2.75, w=5.7)
cd = CategoryChartData()
cd.categories = ["0,5 m", "0,25 m", "0,125 m"]
cd.add_series("MΔ peor escenario", (15.96, 16.99, 17.60))
cd.add_series("Límite 20 °C", (20, 20, 20))
gf = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(6.9), Inches(2.3), Inches(5.85), Inches(3.3), cd)
ch = gf.chart
ch.has_title = True
ch.chart_title.text_frame.text = "Malla: MΔ [°C] al refinar"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.BOTTOM
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
va = ch.value_axis
va.minimum_scale, va.maximum_scale = 14, 21
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE7, 0xE9)
va.tick_labels.font.size = Pt(12)
ch.category_axis.tick_labels.font.size = Pt(13)
s1, s2 = ch.plots[0].series
s1.format.line.color.rgb = ORANGE
s1.format.line.width = Pt(3)
s1.marker.format.fill.solid()
s1.marker.format.fill.fore_color.rgb = ORANGE
s1.data_labels.show_value = True
s1.data_labels.number_format = "0.00"
s1.data_labels.number_format_is_linked = False
s1.data_labels.position = XL_LABEL_POSITION.ABOVE
s1.data_labels.font.size = Pt(13)
s1.data_labels.font.bold = True
s2.format.line.color.rgb = RED
s2.format.line.dash_style = 4
s2.format.line.width = Pt(2)
s2.marker.style = None
from pptx.enum.chart import XL_MARKER_STYLE
s2.marker.style = XL_MARKER_STYLE.NONE
for i, (v, e) in enumerate([("orden 2", "espacio · 1D/2D/3D"), ("2,8·10⁻⁴", "error de energía, caso real"),
                            ("0,02 °C", "cambio por Δt 1 h → 15 min")]):
    x = 6.9 + i * 1.98
    box(s, x, 5.8, 1.85, 1.1, GREEN_BG)
    text(s, x + 0.1, 5.85, 1.65, 0.5, v, size=20, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    text(s, x + 0.1, 6.35, 1.65, 0.5, e, size=11, color=INK, align=PP_ALIGN.CENTER)
text(s, 0.6, 6.55, 5.8, 0.4, "Convergido ≈ 18,5 °C · Verificado ≠ validado (no hay mediciones de la obra)", size=13,
     color=MUTED)
footer(s, 6)
notes(s, "JOSÉ (1:05). El solver discretiza ese balance en celdas: cada una intercambia calor con sus vecinas por "
         "conductancias k·A/d y con el exterior por la resistencia de los bordes. Avanza con Euler explícito, bajo el "
         "límite de estabilidad. Lo verificamos contra soluciones exactas: orden 2 en espacio y 1 en tiempo. En el caso "
         "real, aislado, el calor almacenado es igual al generado, con un error de 3 en 10 mil que baja con el paso de "
         "tiempo. Lo que más mueve el resultado es la malla: el diferencial pasa de 16 a 17,6 °C al refinar, y "
         "estimamos unos 18,5 convergido. El paso temporal casi no influye. Ninguna de las dos cambia la "
         "clasificación del plan. El solver está verificado, pero el modelo no está validado contra mediciones de la "
         "obra. Le paso a Clemente.\n\nDatos: orden 2,00 / 1,99 / 1,99; S25 contra perfil exacto < 1e-6 °C; "
         "Δt 3600/1800/900 s: MΔ 15,964 / 15,982 / 15,986 °C.")

# ---------------------------------------------------------------- 7. Probabilidad
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "P_f = suma de los pesos de los escenarios que fallan")
image(s, FIG / "presentacion/escenarios_24.png", 0.6, 1.35, h=5.25)
x0 = 10.15
box(s, x0, 1.3, 2.6, 2.05, INK)
text(s, x0 + 0.2, 1.4, 2.2, 1.9, [[("Falla si", {"color": SAND, "bold": True})],
                                   [("MT > 70 °C", {"color": WHITE})], [("o MΔ > 20 °C", {"color": WHITE})],
                                   [("(se cuenta una vez)", {"color": RGBColor(0xB8, 0xC4, 0xC9), "size": 13})]],
     size=18, anchor=MSO_ANCHOR.MIDDLE)
box(s, x0, 3.5, 2.6, 1.55, LIGHT)
text(s, x0 + 0.2, 3.55, 2.2, 1.45, [[("w = 1/8 × q_clima", {"bold": True})], "≈ 4 % por escenario",
                                    [("1 falla podría cumplir; 2 no", {"color": MUTED, "size": 13})]], size=16,
     anchor=MSO_ANCHOR.MIDDLE)
box(s, x0, 5.2, 2.6, 1.65, RED_BG)
text(s, x0 + 0.2, 5.25, 2.2, 1.55, [[("Ejemplo de fila", {"bold": True, "color": RED})],
                                    "Espera 6 h · M4_SS · medio", "w = 0,0403 · MΔ = 20,69",
                                    [("I_T = 0 · I_Δ = 1 · I_F = 1", {"bold": True})]], size=13, anchor=MSO_ANCHOR.MIDDLE)
footer(s, 7)
notes(s, "CLEMENTE (0:50). La falla es la unión de los dos criterios: pasar 70 °C o pasar 20 °C de diferencial. "
         "Cada una de las 24 corridas da su máximo, y la probabilidad de falla suma los pesos de los escenarios que "
         "fallan; como es una unión, cada escenario se cuenta una sola vez. Por ejemplo, con 6 horas de espera, la "
         "curva M4_SS con clima medio falla por diferencial y suma su 4 %; ahí fallan 6 escenarios y P_f llega a 25 %. "
         "Los pesos son 1/8 por curva, como réplicas, por el peso de cada historia de clima. Nuestro plan no falla en "
         "ninguno. Ojo con la resolución: cada escenario pesa cerca de 4 %, así que una falla podría cumplir y dos no. "
         "Probamos cambiar los pesos, usar solo la campaña de mayor confianza y los 31 miembros: sigue en 0. Lo frágil "
         "es el calor total de las curvas: con beta = 3 el diferencial llega a 19,7 °C.\n\n"
         "Alcance: 'la probabilidad de excedencia conjunta es 0 % bajo estos escenarios y pesos'. No es 95 % de "
         "confianza ni ausencia de grietas.")

# ---------------------------------------------------------------- 8. Comparación
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Esperar no ayuda: cada vertida nueva es un techo frío")
rows = [["Plan", "D [h]", "P_T", "P_Δ", "P_f", "¿Cumple?"],
        ["Una vertida sin protección, 18 °C", "15,9", "0 %", "100 %", "100 %", "No"],
        ["Propuesta: una vertida, EPS 150, 10 °C", "15,9", "0 %", "0 %", "0 %", "Sí"],
        ["Más rápida", "—", "—", "—", "—", "No existe"],
        ["5 vertidas, espera 6 h", "39,9", "0 %", "25 %", "25 %", "No"],
        ["5 vertidas, espera 48 h", "207,9", "0 %", "100 %", "100 %", "No"]]


def relleno(i, j):
    if i == 2:
        return GREEN_BG
    if j == 5 and rows[i][5] == "No":
        return RED_BG
    return None


t = table(s, 0.6, 1.3, 12.15, rows, [4.95, 1.2, 1.2, 1.2, 1.2, 2.4], size=14, row_h=0.38, fills=relleno)
bold_row(t, 2)
image(s, FIG / "presentacion/mdelta_4casos.png", 0.6, 3.75, h=3.2)
image(s, FIG / "presentacion/corte_espera6h.png", 6.95, 3.85, w=3.3)
box(s, 10.45, 3.85, 2.3, 2.08, LIGHT)
text(s, 10.6, 3.9, 2.0, 2.0, [[("Espera 6 h, t = 42 h", {"bold": True})], "La última vertida entra a 10 °C:",
                              [("techo frío sobre un núcleo caliente", {"bold": True, "color": RED})]], size=13,
     anchor=MSO_ANCHOR.MIDDLE)
box(s, 6.95, 6.1, 5.8, 0.8, GREEN_BG)
text(s, 7.1, 6.1, 5.5, 0.8, [[("No hay variante más rápida: ", {"bold": True, "color": TEAL}),
                              ("1 bomba → 636,9 / 40 = 15,9 h mínimo", {})]], size=15, anchor=MSO_ANCHOR.MIDDLE)
footer(s, 8)
notes(s, "CLEMENTE (1:00). Comparamos con los mismos datos y recursos. La vertida única sin protección es igual de "
         "rápida, pero falla siempre por diferencial: la superficie sigue el ciclo diario. Ningún plan falla por "
         "temperatura máxima: el problema es el diferencial. Las variantes con 5 vertidas son peores además de lentas: "
         "con 6 horas de espera, el diferencial salta a 20,7 °C justo al terminar de colocar, a las 42 horas, porque la "
         "última vertida entra a 10 °C como un techo frío sobre un núcleo que ya se calentó; fallan 6 de 24 escenarios "
         "y P_f llega a 25 %. Con 48 horas, el salto se repite en cada vertida, hasta 40 °C. Y no hay una variante más "
         "rápida: con una bomba, 15,9 h es el mínimo.\n\nGráfico: un solo escenario (M4_SS, clima medio) para los 4 "
         "casos. En la tabla, P sobre los 24 escenarios. MΔ peor: 41,8 / 16,0 / 21,4 / 40,1 °C.")

# ---------------------------------------------------------------- 9. Recomendación y límites
s = prs.slides.add_slide(BLANK)
bg(s, INK)
title(s, "Recomendación: una vertida continua, 10 °C y EPS 150 mm", "D = 15,9 h · P_f = 0 % bajo 8 curvas × 3 climas",
      dark=True)
cards = [("Cumple", "Margen 1,5–2,4 °C", "17,6 °C malla fina · ~18,5 convergido", TEAL),
         ("Es frágil si", "El cemento libera más calor", "β = 3,0 (+20 %) → MΔ 19,7 °C", ORANGE),
         ("Después del día 14", "MΔ sigue subiendo: 19,8 °C al día 30", "Retiro gradual de la aislación (no simulado)", SAND),
         ("Supuestos", "Bomba 40 m³/h · 10 °C · suelo 1D", "Solver verificado, modelo no validado", RGBColor(0xB8, 0xC4, 0xC9))]
for i, (h_, a, b, c) in enumerate(cards):
    x = 0.6 + (i % 2) * 6.2
    y = 1.85 + (i // 2) * 1.75
    box(s, x, y, 5.95, 1.55, RGBColor(0x26, 0x3A, 0x44))
    text(s, x + 0.3, y + 0.15, 5.4, 0.45, h_, size=18, bold=True, color=c)
    text(s, x + 0.3, y + 0.6, 5.4, 0.45, a, size=17, color=WHITE)
    text(s, x + 0.3, y + 1.03, 5.4, 0.4, b, size=13, color=RGBColor(0xB8, 0xC4, 0xC9))
text(s, 0.6, 5.5, 12.1, 0.4, "Sensores y contingencia", size=16, bold=True, color=SAND)
for i, (a, b) in enumerate([("Núcleo", "si sube más rápido que el modelo → aislación más tiempo"),
                            ("Piel a 25 mm", "si ΔT medido > 18 °C → mantener o reforzar manta"),
                            ("Cada camión", "si llega > 12 °C → rechazar o agregar hielo")]):
    x = 0.6 + i * 4.1
    box(s, x, 5.95, 3.95, 0.95, RGBColor(0x26, 0x3A, 0x44))
    text(s, x + 0.2, 6.0, 3.6, 0.85, [[(a, {"bold": True, "color": WHITE})], [(b, {"color": RGBColor(0xB8, 0xC4, 0xC9)})]],
         size=13, anchor=MSO_ANCHOR.MIDDLE)
footer(s, 9, dark=True)
notes(s, "CLEMENTE (0:50). Recomendamos la vertida única continua, a 10 °C y con 150 mm de EPS: termina en 15,9 horas "
         "y cumple en los 24 escenarios. El margen real es de 1,5 a 2,4 °C. Su debilidad es el calor total de las "
         "curvas: si la inversión lo subestima, quedamos en el límite. Además, después de los 14 días el diferencial "
         "sigue subiendo con la aislación puesta, así que la aislación se retira de forma gradual, guiada por sensores "
         "en el núcleo y a 25 mm de las caras; ese retiro no lo simulamos y es el siguiente cálculo. Lo que cambiaría "
         "la decisión: que no se pueda colocar a 10 °C o que el cemento libere más calor. El solver está verificado, "
         "pero el modelo no está validado contra mediciones de la obra. Gracias, quedamos atentos a sus preguntas.")

# ---------------------------------------------------------------- Anexos
def anexo(letra, titulo_, n):
    s = prs.slides.add_slide(BLANK)
    bg(s, WHITE)
    text(s, 0.6, 0.3, 6, 0.35, f"ANEXO {letra} · SOLO PARA PREGUNTAS", size=12, bold=True, color=ORANGE)
    text(s, 0.6, 0.6, 12.1, 0.7, titulo_, size=28, bold=True)
    footer(s, n)
    return s


s = anexo("A", "Robustez del plan elegido: P_f = 0 en todo", 10)
rows = [["Comprobación", "P_f", "MΔ máx [°C]"],
        ["Malla 0,5 → 0,25 → 0,125 m (peor escenario)", "—", "15,96 → 16,99 → 17,60"],
        ["Paso temporal 3600 / 1800 / 900 s", "—", "15,964 / 15,982 / 15,986"],
        ["Balance de energía, caso real aislado", "—", "error 2,8·10⁻⁴ (baja con Δt)"],
        ["S25 a 25 / 50 / 275 mm", "0 / 0 / 0", "15,96 / 15,90 / 15,39"],
        ["Pesos del clima: declarados, iguales, todo frío, medio o cálido", "0 en todos", "—"],
        ["Solo la campaña SS (mayor confianza)", "0", "—"],
        ["31 miembros del ensemble × 8 curvas (248 corridas)", "0", "8,58 a 16,04"],
        ["β de la inversión 2,1 / 3,0", "0 / 0", "12,98 / 19,70"]]
t = table(s, 0.6, 1.55, 12.15, rows, [6.95, 2.0, 3.2], size=15, row_h=0.52,
          fills=lambda i, j: RED_BG if i == 8 else None)
notes(s, "Usar si preguntan por malla, S25, pesos del clima, campaña SS, 31 miembros, beta, paso temporal o energía. "
         "Fuente: entregas/defensa/COMPLEMENTOS.md y results/defensa/complementos/complementos.json.")

s = anexo("B", "Después del día 14: con la aislación puesta, MΔ sigue subiendo", 11)
image(s, FIG / "complementos/posterior_30d.png", 0.6, 1.55, w=8.4)
rows = [["Hasta", "MΔ máx [°C]"], ["14 días", "15,96"], ["20 días", "18,10"], ["25 días", "19,41"], ["30 días", "19,77"]]
table(s, 9.35, 1.6, 3.4, rows, [1.6, 1.8], size=16, row_h=0.5)
box(s, 9.35, 4.4, 3.4, 1.9, RED_BG)
text(s, 9.55, 4.45, 3.0, 1.8, ["Con +1,6 °C de malla pasaría 20 °C hacia el día 20–25.",
                               [("Retiro gradual guiado por sensores. No simulado.", {"bold": True})]], size=14,
     anchor=MSO_ANCHOR.MIDDLE)
notes(s, "Peor escenario (M4_SS, clima medio), malla 0,5 m, aislación puesta 30 días. Después del día 14 el núcleo se "
         "enfría lento porque está aislado, pero la superficie se enfría más rápido: el diferencial sigue creciendo. "
         "El cumplimiento vale para los 14 días del criterio; el retiro gradual es el siguiente cálculo.")

s = anexo("C", "Dónde está el gradiente: corte en y = 0, en el instante de MΔ", 12)
image(s, FIG / "complementos/mecanismo_cortes.png", 1.4, 1.45, h=5.45)
notes(s, "Color = temperatura (negro 0 °C, amarillo 60 °C). Sin protección, el borde es mucho más frío que el centro. "
         "En la propuesta, el campo es casi uniforme. Con espera de 6 h, la vertida superior recién colocada (oscura, "
         "~10 °C) queda como techo frío sobre capas más calientes. MT del plan: núcleo cerca del eje, a ~2,5 m de altura, "
         "a las 222 h.")

s = anexo("D", "Del IFC a la malla: voxeles por vertida", 13)
image(s, ROOT / "results/e07/voxeles_cortes.png", 0.6, 1.5, w=12.15)
text(s, 0.6, 5.15, 12.15, 0.35, "Imagen con Δx = 0,25 m (E07). La defensa usa la malla de 0,5 m:", size=13, color=MUTED)
for i, (v, e) in enumerate([("4 656", "celdas de hormigón"), ("0,5 × 0,5 × 0,55 m", "tamaño de celda"),
                            ("0,52 %", "error de volumen")]):
    x = 0.6 + i * 4.1
    box(s, x, 5.55, 3.95, 1.2, LIGHT)
    text(s, x + 0.2, 5.6, 3.55, 0.6, v, size=24, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    text(s, x + 0.2, 6.2, 3.55, 0.45, e, size=14, color=MUTED, align=PP_ALIGN.CENTER)
notes(s, "Una celda pertenece a un sólido si su centro está dentro (se cuenta cuántas veces un rayo cruza la "
         "superficie). Los escalones son el efecto de la malla sobre las caras inclinadas. Núcleo = celdas interiores; "
         "S25 = puntos a 25 mm bajo las caras exteriores existentes en cada instante, calculados con el flujo de borde.")

prs.save(OUT)
print("Presentación:", OUT)
