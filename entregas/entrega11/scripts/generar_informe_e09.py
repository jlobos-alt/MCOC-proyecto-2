"""Genera E09_informe.docx a partir de las figuras y resultados de results/e09."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "e09"
AZUL = RGBColor(0x1F, 0x3B, 0x57)
GRIS = RGBColor(0x59, 0x59, 0x59)
NARANJA = RGBColor(0xC0, 0x50, 0x2A)


def shade(cell, color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def add_field(paragraph, instr: str):
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar"); fld1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr
    fld2 = OxmlElement("w:fldChar"); fld2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = "1"
    fld3 = OxmlElement("w:fldChar"); fld3.set(qn("w:fldCharType"), "end")
    run._r.extend([fld1, it, fld2, t, fld3])


def estilo(doc):
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12
    for name, size, color in (("Title", 26, AZUL), ("Heading 1", 15, AZUL), ("Heading 2", 12, AZUL)):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.color.rgb = color
        st.font.bold = True
        st.paragraph_format.space_before = Pt(12 if name != "Title" else 0)
        st.paragraph_format.space_after = Pt(4)


def p(doc, texto: str = "", negrita=False, cursiva=False, tam=10.5, color=None,
      align=WD_ALIGN_PARAGRAPH.JUSTIFY, espacio=5):
    par = doc.add_paragraph()
    par.alignment = align
    par.paragraph_format.space_after = Pt(espacio)
    run = par.add_run(texto)
    run.bold = negrita
    run.italic = cursiva
    run.font.size = Pt(tam)
    if color is not None:
        run.font.color.rgb = color
    return par


def formula(doc, texto: str):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(6)
    run = par.add_run(texto)
    run.italic = True
    run.font.name = "Cambria"
    run.font.size = Pt(11.5)
    run.font.color.rgb = AZUL
    return par


def figura(doc, nombre: str, caption: str, ancho_cm=16.0):
    ruta = RES / nombre
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(6)
    par.paragraph_format.space_after = Pt(2)
    par.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    run = cap.add_run(caption)
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = GRIS


def tabla(doc, encabezado, filas, anchos=None, fuente=9):
    t = doc.add_table(rows=1, cols=len(encabezado))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, texto in enumerate(encabezado):
        hdr[i].text = ""
        par = hdr[i].paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run(texto)
        run.bold = True
        run.font.size = Pt(fuente)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(hdr[i], "1F3B57")
    for fila in filas:
        celdas = t.add_row().cells
        for i, texto in enumerate(fila):
            celdas[i].text = ""
            par = celdas[i].paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
            run = par.add_run(str(texto))
            run.font.size = Pt(fuente)
            if str(texto).startswith("**"):
                run.text = str(texto).replace("**", "")
                run.bold = True
    if anchos:
        for row in t.rows:
            for i, ancho in enumerate(anchos):
                row.cells[i].width = Cm(ancho)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def build():
    doc = Document()
    estilo(doc)
    sec = doc.sections[0]
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)

    # Encabezado y pie
    head = sec.header.paragraphs[0]
    head.text = "E09 — Baseline 3D con hidratación  ·  Grupo 5"
    head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in head.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = GRIS
    pie = sec.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pie.add_run("MCOC Proyecto 2 — Hormigón masivo  ·  página ")
    r.font.size = Pt(8); r.font.color.rgb = GRIS
    add_field(pie, "PAGE")

    # ---------------- Portada ----------------
    p(doc, "", espacio=40)
    p(doc, "E09", negrita=True, tam=40, color=NARANJA, align=WD_ALIGN_PARAGRAPH.CENTER, espacio=0)
    p(doc, "Baseline 3D con hidratación", negrita=True, tam=24, color=AZUL,
      align=WD_ALIGN_PARAGRAPH.CENTER, espacio=6)
    p(doc, "Primera simulación 3D físicamente interpretable del caso de referencia",
      cursiva=True, tam=12, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, espacio=30)

    tabla(doc, ["Dato", "Detalle"], [
        ["Grupo", "Grupo 5"],
        ["Integrantes", "José Lobos · Clemente Sánchez · Matías Campos"],
        ["Repositorio", "https://github.com/jlobos-alt/MCOC-proyecto-2"],
        ["Commit evaluado", "7773d10"],
        ["Fecha", "Viernes 6 de noviembre de 2026"],
        ["Caso", "Fundación para aerogenerador, geometría del curso (IFC)"],
    ], anchos=[4.5, 11.5], fuente=9.5)

    p(doc, "Resumen ejecutivo", negrita=True, tam=11.5, color=AZUL, espacio=3)
    p(doc, "Se ejecutó la primera simulación 3D del caso de referencia con geometría del IFC, cinco vertidas e "
           "hidratación con madurez de Arrhenius. La temperatura máxima llega a 63,06 °C a las 52 h y el "
           "diferencial núcleo–superficie alcanza 47,18 °C en centros de celda (49,17 °C estimado a 25 mm). "
           "El modelo reproduce la forma y el orden de magnitud del paper de Ju & Lei (2019), pero todavía no su "
           "peak de 73 °C a los 4 días ni su ΔT cercano a 35 °C. Es un baseline interpretable, no una validación.")
    doc.add_page_break()

    # ---------------- 1 ----------------
    doc.add_heading("1. Geometría y BIM", level=1)
    p(doc, "La geometría sale de foundation.ifc (IFC4, cinco IfcFooting). Es un octágono regular de 18 m entre "
           "caras opuestas en la base, que se reduce en altura hasta un pedestal cilíndrico de 7 m de diámetro. "
           "La cota superior es 4,30 m: 3,30 m de fundación y 1,00 m de pedestal. El volumen geométrico es "
           "636,88 m³, coherente con los Pset de cada vertida.")
    figura(doc, "bim_base.png", "Figura 1. Modelo BIM del caso base: planta, elevación y vista 3D de las cinco vertidas.", 16.5)

    doc.add_heading("2. Voxelización y error de volumen", level=1)
    p(doc, "Se usó una grilla cartesiana de Δx = Δy = 0,25 m y Δz = 0,275 m, elegida para que las interfaces "
           "entre vertidas caigan en caras de celda. La grilla es de 72 × 72 × 16 y tiene 37 164 celdas activas. "
           "El error de volumen se calcula como e_V = |V_voxel − V_IFC| / V_IFC.")
    formula(doc, "e_V = |V_voxel − V_IFC| / V_IFC        V_voxel = N · Δx · Δy · Δz")
    tabla(doc, ["Vertida", "Inicio [h]", "T col. [°C]", "V IFC [m³]", "V voxel [m³]", "e_V"], [
        ["1", "0", "18", "147,63", "146,44", "0,81 %"],
        ["2", "6", "18", "147,63", "146,44", "0,81 %"],
        ["3", "12", "18", "214,22", "214,71", "0,23 %"],
        ["4", "18", "18", "88,93", "88,83", "0,11 %"],
        ["5", "24", "18", "38,48", "42,35", "10,07 %"],
        ["**Total**", "", "", "**636,88**", "**638,76**", "**0,29 %**"],
    ], anchos=[2.2, 2.6, 2.8, 3.0, 3.2, 2.2], fuente=9)
    p(doc, "El total es bajo, pero la vertida 5 concentra 10,07 % de error porque su cara superior cilíndrica "
           "no calza con Δz. Las cuatro primeras quedan bajo 0,81 %.")
    figura(doc, "voxeles_cortes.png", "Figura 2. Cortes de la voxelización: cada color es una vertida y cada celda tiene un único vertida_id.", 16.5)

    doc.add_heading("3. Vertidas y condiciones ambientales", level=1)
    p(doc, "Las cinco vertidas se colocan cada 6 h (0, 6, 12, 18 y 24 h), con temperatura de colocación de 18 °C. "
           "La secuencia y las temperaturas se leen del IFC (InicioPlanificado y TemperaturaColocacion_C); el "
           "solver no contiene nombres ni horas de obra.")
    p(doc, "Las condiciones ambientales son deliberadamente simples y quedan declaradas: aire 15 ± 5 °C con "
           "período de 24 h, suelo a 12 °C, convección de h = 12 W/(m²·K) en el perímetro y la superficie, y un "
           "encofrado de madera de 20 mm y k = 0,5 W/(m·K) en el perímetro durante las primeras 72 h. La base "
           "tiene una capa de suelo de 1 m y k = 1,389 W/(m·K). No se modelan radiación, viento ni curado "
           "superficial, y el encofrado es común a todas las vertidas.")

    doc.add_heading("4. Modelo de hidratación", level=1)
    p(doc, "El calor se obtiene de una elevación adiabática de un término, con madurez de Arrhenius:")
    formula(doc, "θ_ad(a) = θ∞ [1 − exp(−a/τ)]")
    formula(doc, "q̇_h = ρ c_p (dθ_ad/da) · m(T)")
    formula(doc, "m(T) = exp[−(Ea/R)(1/T − 1/T_ref)]        a_eq(t) = ∫₀ᵗ m(T) dτ")
    p(doc, "con θ∞ = 45 °C, τ = 30 h, Ea/R = 4000 K, T_ref = 20 °C, ρ = 2400 kg/m³, c_p = 970 J/(kg·K) y "
           "k = 2,22 W/(m·K). La ecuación que resuelve el solver es el balance de celdas:")
    formula(doc, "ρ c_p ∂T/∂t = ∇·(k ∇T) + q̇_h")
    p(doc, "y en las caras expuestas se aplica −k ∂T/∂n = h (T − T_aire). Con θ∞ = 45 K y T col. = 18 °C, la cota "
           "adiabática es 63 °C; el máximo calculado (63,06 °C) coincide con ella, lo que confirma la coherencia "
           "del calor total.")

    doc.add_heading("5. Resultados térmicos", level=1)
    figura(doc, "e09_tmax.png", "Figura 3. T_max(t), temperaturas de control y ΔT en centros de celda y a 25 mm. Líneas punteadas: límites de 70 °C y 20/30 °C.", 16.5)
    p(doc, "La temperatura máxima es 63,06 °C a las 52 h y luego decae lentamente. El ΔT en centros de celda llega "
           "a 47,18 °C a las 166 h; estimado a 25 mm de la superficie sube a 49,17 °C a las 138 h. Ambos superan "
           "el límite de 20 °C del curso y también el de 30 °C de la ICH para hormigones de más de 25 MPa.")
    p(doc, "Para estimar la temperatura a 25 mm se usa conducción 1D entre el centro de la primera celda y el aire:")
    formula(doc, "q = (T_c − T_aire) / (Δz/(2k) + 1/h);   T_s = T_c − q Δz/(2k);   T_25 = T_s − q (0,025)/k")
    tabla(doc, ["Punto de control", "T máx [°C]", "Instante [h]", "T final [°C]"], [
        ["Núcleo (0,0; 0,0; 2,06 m)", "62,63", "84", "55,93"],
        ["Superficie superior, 1.ª celda (0,0; 0,0; 4,26 m)", "43,44", "57", "22,45"],
        ["Base (0,0; 0,0; 0,14 m)", "55,28", "42", "43,95"],
        ["Borde lateral (−6,1; 0,0; 2,06 m)", "42,27", "42", "20,81"],
        ["Superficie a 25 mm (0,0; 0,0)", "31,40", "54", "18,70"],
    ], anchos=[8.2, 2.6, 2.6, 2.6], fuente=9)
    p(doc, "El núcleo se mantiene sobre 60 °C entre 48 y 234 h, mientras la superficie superior baja de 43 °C a "
           "22 °C en el mismo período. Esa separación sostenida es la que produce el ΔT alto.")
    figura(doc, "e09_puntos.png", "Figura 4. Evolución en los puntos de control.", 15.0)
    figura(doc, "e09_cortes.png", "Figura 5. Cortes en el plano y = 0 a 24, 48, 72, 120, 168 y 336 h.", 16.5)
    figura(doc, "e09_vista3d.png", "Figura 6. Voxeles activos a 72 h, cortados en y = 0 y coloreados por temperatura.", 13.5)
    p(doc, "Los cortes muestran el frente térmico: a 24 h aún hay vertidas frías arriba; entre 48 y 72 h el núcleo "
           "alcanza su máximo; desde 120 h el enfriamiento entra por la superficie y el perímetro. La zona más "
           "caliente es el centro del bloque, no la cara superior.")

    doc.add_heading("6. Comparación cualitativa con Ju & Lei (2019)", level=1)
    tabla(doc, ["Característica del paper", "¿Se reproduce?", "Comentario"], [
        ["Fundación de 18 × 18 m y ~3,3 m de espesor", "Sí, parcial", "Base de 18 m; espesor total 4,3 m (3,3 + 1,0 m de pedestal)."],
        ["Pedestal cilíndrico de 7 m de diámetro", "Sí", "Radio 3,5 m sobre la fundación."],
        ["Peak de núcleo cercano a 73 °C", "No", "El modelo da 63,06 °C; faltan ~10 °C."],
        ["Peak cercano a 4 días", "No", "El modelo adelanta el peak a 52 h (~2,2 días)."],
        ["ΔT núcleo–superficie cercano a 35 °C", "No", "El modelo da 47–49 °C, más severo."],
        ["Núcleo más caliente que la superficie", "Sí", "El núcleo es sistemáticamente más caliente."],
        ["Construcción por vertidas", "Sí", "Cinco vertidas cada 6 h, leídas del IFC."],
        ["Efecto de la hidratación y la madurez", "Sí, cualitativo", "El calor total no depende de T; el peak se adelanta al calentar."],
        ["Aislación y curado superficial", "No", "Contorno superior convectivo h = 12 W/(m²·K), sin manta."],
        ["Clima real del sitio", "No", "Aire sinusoidal genérico 15 ± 5 °C, no el de Chanco."],
    ], anchos=[7.2, 3.4, 6.4], fuente=8.5)
    p(doc, "¿Qué reproduce y qué no? El modelo reproduce la geometría de escala, la secuencia de vertidas, la forma "
           "de la curva (subida rápida, peak y enfriamiento lento), la existencia de un núcleo más caliente que la "
           "superficie y el orden de magnitud del calor de hidratación (θ∞ = 45 K). No reproduce el peak absoluto "
           "ni su instante, ni el ΔT del paper. Las causas son: (i) θ∞, τ y Ea/R son provisorios y no se "
           "calibraron contra las mediciones; (ii) el contorno superior no incluye aislación ni curado, por lo que "
           "la superficie se enfría de más y el ΔT crece; (iii) el ΔT del paper se mide con sensores internos, no "
           "a 25 mm; (iv) la geometría del curso es un tronco de octágono escalonado, más esbelto y de menor "
           "volumen que el raft prismático del paper.")

    doc.add_heading("7. Reproducibilidad", level=1)
    codigo = doc.add_paragraph()
    codigo.paragraph_format.space_after = Pt(8)
    run = codigo.add_run("cd entregas/entrega9\n"
                         "pip install -r requirements.txt\n"
                         "python scripts/baseline_e09.py\n"
                         "python scripts/simular_fundacion_ifc.py --salida results/e09/base --t 72 --corte --vti-cada-h 0\n"
                         "python -m pytest tests -q")
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    p(doc, "baseline_e09.py guarda results/e09/series_e09.csv y resumen_e09.json con las series, la malla, los "
           "volúmenes y los parámetros. El entorno está en environment.yml y las versiones en requirements.txt.")

    doc.add_heading("8. Limitaciones y próximos pasos", level=1)
    for texto in [
        "Hidratación y clima provisorios: falta calibrar θ∞, τ, Ea/R y usar el clima real de Chanco (E10–E11).",
        "El ΔT se informa en centros de celda y, como estimación, a 25 mm; falta un sensor virtual consistente con la instrumentación del paper.",
        "El encofrado es una capa común de 0 a 72 h; no se retira vertida por vertida ni se modela la aislación (E10).",
        "El error de volumen de la vertida 5 (10,07 %) se corrige refinando Δz o ajustando la cara superior del cilindro.",
        "Verificado, no validado: la comparación con Ju & Lei es cualitativa; la validación cuantitativa queda para E10–E12.",
    ]:
        par = doc.add_paragraph(style="List Bullet")
        par.paragraph_format.space_after = Pt(3)
        par.add_run(texto).font.size = Pt(10)

    doc.add_heading("Referencias", level=1)
    p(doc, "Ju, Y. y Lei, H. (2019). Actual Temperature Evolution of Thick Raft Concrete Foundations and Cracking "
           "Risk Analysis. Advances in Materials Science and Engineering, Article ID 7029671. "
           "https://doi.org/10.1155/2019/7029671", tam=9)
    p(doc, "ICH (2019). Especificación para Hormigón Masivo Estructural. Instituto del Cemento y del Hormigón de Chile.", tam=9)

    # Bloque Canvas
    doc.add_paragraph()
    p(doc, "Entrega en Canvas", negrita=True, tam=10.5, color=AZUL, espacio=2)
    p(doc, "Repositorio: https://github.com/jlobos-alt/MCOC-proyecto-2", tam=10, align=WD_ALIGN_PARAGRAPH.LEFT, espacio=1)
    p(doc, "Commit evaluado: 7773d10", tam=10, align=WD_ALIGN_PARAGRAPH.LEFT, espacio=1)

    doc.core_properties.title = "E09 — Baseline 3D con hidratación"
    doc.core_properties.author = "Grupo 5 — José Lobos, Clemente Sánchez, Matías Campos"
    doc.core_properties.subject = "MCOC Proyecto 2 — Hormigón masivo"
    salida = ROOT / "E09_informe.docx"
    doc.save(salida)
    print(f"Guardado: {salida}")


if __name__ == "__main__":
    build()
