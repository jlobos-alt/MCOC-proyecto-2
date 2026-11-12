"""Genera E12_informe.md y E12_informe.docx desde results/e12/resumen_e12.json.

El contenido se escribe una sola vez y se emite en los dos formatos, de modo que
las cifras del Markdown y del Word salen del mismo JSON y no pueden divergir.

Uso (desde entregas/entrega12):
    python scripts/generar_informe_e12.py --commit 5aa4bfa
    python scripts/generar_informe_e12.py --commit <sha> --solo-md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "e12"
REPO = "https://github.com/jlobos-alt/MCOC-proyecto-2"
FECHA = "viernes 13 de noviembre de 2026"

AZUL = (0x1F, 0x3B, 0x57)
GRIS = (0x59, 0x59, 0x59)
NARANJA = (0xC0, 0x50, 0x2A)


def fmt(valor: float, dec: int = 2) -> str:
    """Numero con coma decimal, como el resto de los informes."""
    return f"{valor:.{dec}f}".replace(".", ",")


def contenido(d: dict, commit: str):
    """Bloques del informe: (tipo, ...). Misma fuente para MD y DOCX."""
    r = d["resultado"]
    loc = d["localizacion"]
    x = loc["T_max"]
    dm = loc["delta_T_max"]
    cl = d["clima"]
    borde = d["condiciones_borde"]
    ex = d["excedencia_delta_T"]
    malla = d["malla"]
    pv = d["por_vertida"]
    hid = d["hidratacion"]

    b = []
    b.append(("h1", "E12 — Simulación determinista de 14 días"))
    b.append(("meta", "**Grupo 5:** José Lobos, Clemente Sánchez y Matías Campos"))
    b.append(("meta", f"**Repositorio:** {REPO}"))
    b.append(("meta", f"**Commit evaluado:** {commit}"))
    b.append(("meta", f"**Fecha:** {FECHA}"))
    b.append(("meta", "**Caso:** fundación del IFC, 5 vertidas, 336 h desde el 27-nov-2026 04:00"))

    b.append(("h2", "1. Introducción"))
    b.append(("p",
        "Este informe documenta la simulación determinista de 14 días (336 h) del caso de fundación del "
        "IFC. Su propósito es evaluar, con un único conjunto de supuestos y sin variabilidad aleatoria, si "
        "el plan de vertidas satisface los criterios de 70 °C de temperatura máxima y 20 °C de diferencial "
        "núcleo-superficie. El modelo integra la geometría y la secuencia del IFC, una única curva de "
        "hidratación (C1), el suelo semi-infinito, el moldaje por vertida, el clima de snapshots "
        "verificados y la visualización tridimensional, sobre una malla de 0,5 m. Los resultados indican "
        f"que el criterio de 70 °C se satisface con {fmt(r['T_max_C'])} °C, mientras que el diferencial "
        f"alcanza {fmt(r['delta_T_max_C'])} °C y excede los 20 °C."))

    b.append(("h2", "2. Curva de hidratación"))
    b.append(("p",
        f"Se emplea la curva C1, única declarada en el modelo desde E09: θ_ad(a) = "
        f"{fmt(hid['theta_inf_C'], 0)}·(1 − e^(−a/{fmt(hid['tau_h'], 0)})) °C, con madurez de Arrhenius "
        f"Ea/R = {fmt(hid['Ea_R_K'], 0)} K y T_ref = {fmt(hid['T_ref_C'], 0)} °C, sin segunda rama "
        f"exponencial (θ∞₂ = {fmt(hid['segunda_rama_C'], 0)}). La curva se evalúa con la edad equivalente: "
        "el hormigón caliente libera la misma energía en menos tiempo. La curva proporciona "
        "θ_ad(24 h) = 24,78 °C, θ_ad(168 h) = 44,83 °C y q̇(0) = 0,97 kW/m³."))
    b.append(("formula", "θ_ad(a) = θ∞ (1 − e^(−a/τ)),    q̇_h = ρ c_p (dθ_ad/da) · m(T)"))
    b.append(("p",
        "La curva se modifica editando θ∞, τ y Ea/R en `datos/fundacion_e12.yaml`; no se mezclan curvas "
        "entre vertidas."))

    b.append(("h2", "3. Clima: datasets, timestamps y horizonte"))
    b.append(("p",
        "Dos snapshots inmutables de Open-Meteo, verificados mediante SHA-256 antes de simular:"))
    b.append(("tabla", ["Snapshot", "Contenido", "Horizonte", "SHA-256 (csv)"], [
        ["20261111T193622Z_open-meteo-forecast",
         "forecast best_match, Pahuil/Chanco; emitido 2026-11-11 19:36:22 UTC",
         "2026-11-11 00:00 → 2026-11-24 23:00 (336 h)", "`ba1d71b5…`"],
        ["20261111T193623Z_open-meteo-archive",
         "reanalysis ERA5 del mismo calendario",
         "2025-11-27 00:00 → 2025-12-11 23:00 (360 h)", "`f4377629…`"],
    ], None, 8.5))
    b.append(("p",
        "**Horizonte no cubierto.** La primera vertida ocurre el 27 de noviembre de 2026 a las 04:00, "
        "mientras que el pronóstico disponible finaliza el 24 de noviembre y no aporta horas. Las 336 h se "
        "completan con la climatología del archivo, desplazada al año del caso, hora a hora y sin "
        "interpolación entre años. Cada fila de `series_e12.csv` declara su fuente: 0 h de pronóstico y "
        "337 puntos de climatología, sin horas faltantes. El archivo presenta aire entre "
        f"{fmt(cl['T_aire_min_C'], 1)} y {fmt(cl['T_aire_max_C'], 1)} °C, viento medio de "
        f"{fmt(cl['viento_medio_ms'])} m/s (máximo {fmt(cl['viento_max_ms'])}), radiación máxima de "
        f"{cl['G_max_W_m2']:.0f} W/m², h entre {fmt(cl['h_total_min_W_m2K'])} y "
        f"{fmt(cl['h_total_max_W_m2K'])} W/(m²·K) y sol-aire máxima de "
        f"{fmt(cl['T_sol_aire_max_C'])} °C."))

    b.append(("h2", "4. Condiciones de borde"))
    b.append(("p",
        "Las caras laterales y la superficie usan una condición de Robin; la base es un medio conductivo "
        "semi-infinito:"))
    b.append(("tabla", ["Frontera", "Tipo", "Parámetros"], [
        ["Lateral y superior", "Robin",
         "−k∂T/∂n = h(t)·(T − T∞); h = 5,7 + 3,8v + 4εσT³; T∞ = T sol-aire; α = 0,6; ε = 0,9"],
        ["Moldaje", "Capa en serie",
         "madera 19 mm, k = 0,12 → R = 0,158 m²K/W; se retira 72 h después de cada vertida"],
        ["Base", "Robin conductivo",
         "R = e/k = 1,0/1,389 = 0,72 m²K/W; T∞ = suelo a 1 m (onda anual, amortiguación 0,69, atraso 517 h)"],
        ["Inicial", "Dirichlet", "T = 18 °C al colocar cada vertida"],
        ["Fuente", "Volumétrica", "q̇ de la curva C1 con madurez de Arrhenius"],
    ], [3.0, 3.0, 10.0], 8.5))
    b.append(("p", "Muestras de la serie que recibe la condición de Robin:"))
    filas = borde["muestras"]
    elegidos = [f for f in filas if f["t_h"] in (0.0, 12.0, 24.0, 72.0, 168.0, 336.0)]
    b.append(("tabla",
              ["t [h]", "Hora local", "T aire [°C]", "v [m/s]", "G [W/m²]", "h [W/m²K]", "T∞ [°C]", "T suelo [°C]"],
              [[f"{f['t_h']:g}", f["time_local"][11:16], fmt(f["T_aire_C"], 1), fmt(f["viento_ms"]),
                f"{f['solar_W_m2']:.0f}", fmt(f["h_total_W_m2K"], 1), fmt(f["T_sol_aire_C"], 1),
                fmt(f["T_suelo_C"], 1)] for f in elegidos],
              [1.6, 2.0, 2.2, 1.9, 2.1, 2.2, 1.9, 2.2], 8.5))

    b.append(("h2", "5. Plan de vertidas"))
    b.append(("p",
        "El plan se obtiene del IFC (horas, temperatura de colocación, moldaje y retiro), sin datos de "
        "obra en el script:"))
    zs = {"1": "0,00–0,55", "2": "0,55–1,10", "3": "1,10–2,20", "4": "2,20–3,30", "5": "3,30–4,30"}
    b.append(("tabla", ["V", "Inicio [h]", "Hora local", "T col. [°C]", "z [m]", "Moldaje", "Retiro [h]"],
              [[p["id"], f"{p['inicio_h']:g}", p["inicio_local"][11:16], fmt(p["T_colocacion_C"], 1),
                zs[str(p["id"])], p["moldaje"], f"{p['retiro_moldaje_h']:g}"] for p in d["plan_vertidas"]],
              [1.0, 2.0, 2.4, 2.2, 2.6, 2.6, 2.2], 9))
    b.append(("p", "Las cinco vertidas suman 636,89 m³ y usan madera sin aislación."))

    b.append(("h2", "6. Resultados de los criterios de 70 °C y 20 °C"))
    b.append(("tabla", ["Criterio", "Límite [°C]", "Valor [°C]", "Instante", "Veredicto"], [
        ["T_max", "70", fmt(r["T_max_C"]), f"{r['T_max_h']:g} h · {r['T_max_local'].replace('T', ' ')}", "**cumple**"],
        ["ΔT_max", "20", fmt(r["delta_T_max_C"]), f"{r['delta_T_h']:g} h · {r['delta_T_local'].replace('T', ' ')}", "**no cumple**"],
    ], [2.4, 2.4, 2.4, 5.4, 2.8], 9))
    b.append(("p",
        f"La temperatura máxima asciende a {fmt(x['T_C'])} °C a las {x['t_h']:g} h en la celda "
        f"({fmt(x['x_m'])}; {fmt(x['y_m'])}; {fmt(x['z_m'])}) m, sobre el eje del pedestal (V{x['vertida']}). "
        f"Queda {fmt(70.0 - x['T_C'])} °C bajo el límite, aunque el hormigón permanece 208 h sobre 60 °C."))
    b.append(("p",
        f"El diferencial máximo alcanza {fmt(dm['delta_T_C'])} °C a las {dm['t_h']:g} h. El núcleo más "
        f"caliente está en ({fmt(dm['nucleo']['x_m'])}; {fmt(dm['nucleo']['y_m'])}; "
        f"{fmt(dm['nucleo']['z_m'])}) m con {fmt(dm['nucleo']['T_C'])} °C (V{dm['nucleo']['vertida']}), y la "
        f"superficie más fría en ({fmt(dm['superficie']['x_m'])}; {fmt(dm['superficie']['y_m'])}; "
        f"{fmt(dm['superficie']['z_m'])}) m con {fmt(dm['superficie']['T_C'])} °C "
        f"(V{dm['superficie']['vertida']}), sobre la cara lateral. El ΔT supera los 20 °C en "
        f"{ex['horas_sobre_20']} de las 337 horas: comienza a las {ex['primera_h']:g} h y permanece sobre el "
        f"límite al finalizar la ventana ({fmt(r['delta_T_final_C'])} °C a las 336 h)."))
    b.append(("p",
        f"La temperatura máxima por vertida es V1 {fmt(pv['1']['T_max_C'])} °C, V2 {fmt(pv['2']['T_max_C'])} °C, "
        f"V3 {fmt(pv['3']['T_max_C'])} °C, V4 {fmt(pv['4']['T_max_C'])} °C y V5 {fmt(pv['5']['T_max_C'])} °C, "
        "con instantes entre 43 y 64 h. El máximo global se explica por la acumulación de V1–V3 en el centro "
        "del bloque."))

    b.append(("h2", "7. Curvas núcleo-superficie y visualización tridimensional"))
    b.append(("fig", "results/e12/e12_clima.png",
              "Figura 1. Clima del caso: aire, sol-aire, suelo y h(t) en las 336 h (todo climatología)."))
    b.append(("fig", "results/e12/e12_curva_c1.png",
              "Figura 2. Curva C1: elevación adiabática y calor volumétrico con madurez."))
    b.append(("fig", "results/e12/e12_criterios.png",
              "Figura 3. T_max(t) contra 70 °C y ΔT(t) contra 20 °C."))
    b.append(("p",
        "El núcleo asciende con rapidez y desciende lentamente: 63,98 °C a las 54 h y 56,58 °C al final. "
        "La superficie sigue el ciclo diario y el retiro del moldaje: 35,53 °C a las 54 h y 20,38 °C a las "
        "148 h. El ΔT crece de 28,45 a 42,06 °C al retirarse el moldaje (72–96 h), cuando la cara lateral "
        "pasa de R ≈ 0,37 a ≈ 0,21 m²K/W."))
    b.append(("fig", "results/e12/e12_nucleo_superficie.png",
              "Figura 4. Curvas núcleo (máximo) y superficie (mínimo) con el ΔT y el límite de 20 °C."))
    b.append(("fig", "results/e12/e12_3d_tmax.png",
              "Figura 5. Cortes ortogonales x = 0, y = 0 y z = 1,6 m en el instante de T_max."))
    b.append(("fig", "results/e12/e12_3d_dtmax.png",
              "Figura 6. Los mismos cortes en el instante de ΔT_max: núcleo caliente y perímetro frío."))
    b.append(("fig", "results/e12/e12_3d_zonas.png",
              "Figura 7. Zonas de control del criterio (núcleo y superficie) a t = 148 h."))
    b.append(("p",
        "La serie `.vti` (17 archivos, cada 24 h y los dos máximos) se abre en ParaView con temperatura, "
        "vertida y las zonas de control."))

    b.append(("h2", "8. Conclusiones"))
    b.append(("p",
        "En las condiciones declaradas, el plan no satisface el criterio de 20 °C: la temperatura máxima "
        f"se mantiene bajo 70 °C, con {fmt(r['T_max_C'])} °C a las {r['T_max_h']:g} h y "
        f"{fmt(70.0 - r['T_max_C'])} °C de margen, pero el diferencial alcanza "
        f"{fmt(r['delta_T_max_C'])} °C a las {r['delta_T_h']:g} h. El veredicto es determinista, pues la "
        "corrida reproduce exactamente la misma serie y la no conformidad proviene de los supuestos del "
        "caso, no de una fluctuación aleatoria."))
    b.append(("p",
        "El resultado está controlado por dos mecanismos. La temperatura máxima depende del calor de "
        "hidratación acumulado por las cinco vertidas y de las pérdidas de borde, y se aproxima a la suma "
        "adiabática de 63 °C porque la pérdida temprana es pequeña. El diferencial depende del desacople "
        "núcleo-superficie: con k = 2,22 W/(m·K) y V3 de 1,10 m, la conducción del núcleo tarda semanas, "
        "mientras que la superficie sigue el aire y la radiación en horas. El mínimo de superficie "
        "(20,38 °C), y no el máximo del núcleo, fija el ΔT, que crece al retirarse el moldaje."))
    b.append(("p",
        "Para cumplir los 20 °C sería necesario desacoplar la superficie, por ejemplo con aislación lateral "
        "de EPS o un retiro más tardío del moldaje; esa comparación se abordará en E15."))

    b.append(("h2", "9. Reproducibilidad"))
    b.append(("code", "cd entregas/entrega12\n"
                      "pip install -r requirements.txt\n"
                      "python scripts/e12_determinista.py\n"
                      "python -m pytest tests -q"))
    b.append(("p",
        "El script imprime los siete pasos, verifica los snapshots y genera las figuras, `series_e12.csv` "
        "(337 filas con su fuente), las tablas de borde y plan, `resumen_e12.json` y la serie `.vti`. La "
        "corrida usa dt = "
        f"{d['dt_s']:.0f} s y {d['pasos']} pasos. Los nueve tests comprueban la curva, el clima, el plan, "
        "ambos criterios, la ubicación de los máximos y la repetibilidad."))

    return b


def a_markdown(bloques) -> str:
    lineas = []
    for bloque in bloques:
        tipo = bloque[0]
        if tipo == "h1":
            lineas += [f"# {bloque[1]}", ""]
        elif tipo == "h2":
            lineas += [f"## {bloque[1]}", ""]
        elif tipo == "meta":
            lineas += [bloque[1], ""]
        elif tipo == "p":
            lineas += [bloque[1], ""]
        elif tipo == "formula":
            lineas += ["$$" + bloque[1] + "$$", ""]
        elif tipo == "tabla":
            _, encabezado, filas = bloque[0], bloque[1], bloque[2]
            lineas.append("| " + " | ".join(str(c) for c in encabezado) + " |")
            lineas.append("|" + "|".join("---:" if i else "---" for i in range(len(encabezado))) + "|")
            for fila in filas:
                lineas.append("| " + " | ".join(str(c) for c in fila) + " |")
            lineas.append("")
        elif tipo == "fig":
            lineas += [f"![]({bloque[1]})", "", f"*{bloque[2]}*", ""]
        elif tipo == "code":
            lineas += ["```powershell", bloque[1], "```", ""]
    return "\n".join(lineas).rstrip() + "\n"


def contar_palabras(texto: str) -> int:
    cuerpo = re.sub(r"```.*?```", "", texto, flags=re.S)
    return len(re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9.,%°+\-–/]*", cuerpo))


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------


def generar_docx(bloques, salida: Path) -> None:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    azul, gris, naranja = RGBColor(*AZUL), RGBColor(*GRIS), RGBColor(*NARANJA)

    def shade(cell, color: str) -> None:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), color)
        tcPr.append(shd)

    def campo(par, instr: str) -> None:
        run = par.add_run()
        ini = OxmlElement("w:fldChar"); ini.set(qn("w:fldCharType"), "begin")
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr
        sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate")
        t = OxmlElement("w:t"); t.text = "1"
        fin = OxmlElement("w:fldChar"); fin.set(qn("w:fldCharType"), "end")
        run._r.extend([ini, it, sep, t, fin])

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12
    for nombre, tam in (("Title", 24), ("Heading 1", 15), ("Heading 2", 12)):
        st = doc.styles[nombre]
        st.font.name = "Calibri"
        st.font.size = Pt(tam)
        st.font.color.rgb = azul
        st.font.bold = True
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(4)

    sec = doc.sections[0]
    sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.2); sec.right_margin = Cm(2.2)
    head = sec.header.paragraphs[0]
    head.text = "E12 — Simulación determinista de 14 días  ·  Grupo 5"
    head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in head.runs:
        run.font.size = Pt(8); run.font.color.rgb = gris
    pie = sec.footer.paragraphs[0]
    pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = pie.add_run("MCOC Proyecto 2 — Hormigón masivo  ·  página ")
    r.font.size = Pt(8); r.font.color.rgb = gris
    campo(pie, "PAGE")

    def parrafo(texto: str, tam: float = 10.5, negrita: bool = False, cursiva: bool = False,
                color=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, espacio: float = 5):
        par = doc.add_paragraph()
        par.alignment = align
        par.paragraph_format.space_after = Pt(espacio)
        # Respeta **negritas** dentro del texto.
        for i, trozo in enumerate(re.split(r"\*\*(.+?)\*\*", texto)):
            if not trozo:
                continue
            run = par.add_run(trozo)
            run.bold = negrita or (i % 2 == 1)
            run.italic = cursiva
            run.font.size = Pt(tam)
            if color is not None:
                run.font.color.rgb = color
        return par

    def tabla(encabezado, filas, anchos=None, fuente: float = 9):
        t = doc.add_table(rows=1, cols=len(encabezado))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, texto in enumerate(encabezado):
            celda = t.rows[0].cells[i]
            celda.text = ""
            par = celda.paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = par.add_run(str(texto))
            run.bold = True
            run.font.size = Pt(fuente)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            shade(celda, "1F3B57")
        for fila in filas:
            celdas = t.add_row().cells
            for i, texto in enumerate(fila):
                celdas[i].text = ""
                par = celdas[i].paragraphs[0]
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
                limpio = str(texto).replace("**", "").replace("`", "")
                run = par.add_run(limpio)
                run.font.size = Pt(fuente)
                if str(texto).startswith("**"):
                    run.bold = True
        if anchos:
            for row in t.rows:
                for i, ancho in enumerate(anchos):
                    row.cells[i].width = Cm(ancho)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)

    for bloque in bloques:
        tipo = bloque[0]
        if tipo == "h1":
            par = doc.add_paragraph(bloque[1], style="Title")
            par.alignment = WD_ALIGN_PARAGRAPH.LEFT
            par.paragraph_format.space_after = Pt(8)
        elif tipo == "h2":
            doc.add_heading(bloque[1], level=1)
        elif tipo == "meta":
            parrafo(bloque[1], tam=10, espacio=2, align=WD_ALIGN_PARAGRAPH.LEFT)
        elif tipo == "p":
            parrafo(bloque[1])
        elif tipo == "formula":
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.space_before = Pt(4)
            par.paragraph_format.space_after = Pt(6)
            run = par.add_run(bloque[1])
            run.italic = True
            run.font.name = "Cambria"
            run.font.size = Pt(11)
            run.font.color.rgb = azul
        elif tipo == "tabla":
            tabla(bloque[1], bloque[2], bloque[3] if len(bloque) > 3 else None,
                  bloque[4] if len(bloque) > 4 else 9)
        elif tipo == "fig":
            ruta = ROOT / bloque[1]
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.space_before = Pt(6)
            par.paragraph_format.space_after = Pt(2)
            par.add_run().add_picture(str(ruta), width=Cm(15.5))
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_after = Pt(10)
            run = cap.add_run(bloque[2])
            run.italic = True
            run.font.size = Pt(8.5)
            run.font.color.rgb = gris
        elif tipo == "code":
            par = doc.add_paragraph()
            par.paragraph_format.space_after = Pt(8)
            run = par.add_run(bloque[1])
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)

    doc.core_properties.title = "E12 — Simulación determinista de 14 días"
    doc.core_properties.author = "Grupo 5 — José Lobos, Clemente Sánchez, Matías Campos"
    doc.core_properties.subject = "MCOC Proyecto 2 — Hormigón masivo"
    doc.save(salida)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", default="f53f3d9", help="SHA que se declara en el informe")
    ap.add_argument("--solo-md", action="store_true")
    args = ap.parse_args()

    d = json.loads((RES / "resumen_e12.json").read_text(encoding="utf-8"))
    bloques = contenido(d, args.commit)

    md = a_markdown(bloques)
    destino_md = ROOT / "E12_informe.md"
    destino_md.write_text(md, encoding="utf-8")
    palabras = contar_palabras(md)
    print(f"Markdown: {destino_md} ({palabras} palabras)")
    if palabras > 1400:
        raise SystemExit(f"El Markdown excede 1400 palabras: {palabras}")

    if not args.solo_md:
        destino_docx = ROOT / "E12_informe.docx"
        generar_docx(bloques, destino_docx)
        print(f"Word: {destino_docx}")


if __name__ == "__main__":
    main()
