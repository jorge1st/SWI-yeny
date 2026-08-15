# modules/pdf_exporter.py
"""
Exportador a PDF con fallback a CSV si 'reportlab' no está disponible.
Funciones principales:
- export_table_to_pdf(path, title, headers, rows, company_info, orientation)
- export_qtablewidget_to_pdf(qtable, path, title, company_info, orientation)

Mejoras añadidas:
- Ahora calcula anchos de columna proporcionales a la longitud de contenido para evitar
  que textos largos se solapen.
- Usa Paragraph para el contenido de las celdas (permitiendo wrapping).
- Ajustes de estilos y alineación (vertical centrado, filas con padding) para evitar
  que el texto se monte encima de líneas.
- Mantiene el fallback a CSV cuando reportlab no está disponible.
"""
import os
import csv
import datetime
from typing import List, Dict, Any

# No importamos reportlab al nivel de módulo para evitar errores en el import inicial
# Intentamos importar dentro de las funciones cuando sea necesario.

DEFAULT_FONT = "Helvetica"

def _ensure_dir_for_file(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _fallback_export_csv(path: str, headers: List[str], rows: List[List[Any]]):
    # Asegurar extensión .csv
    if not path.lower().endswith(".csv"):
        base = os.path.splitext(path)[0]
        path = base + ".csv"
    _ensure_dir_for_file(path)
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for r in rows:
                writer.writerow([str(c) if c is not None else "" for c in r])
        return {"type": "csv", "path": path}
    except Exception as e:
        raise

def _approx_column_weights(headers: List[str], rows: List[List[Any]]) -> List[float]:
    """
    Calculate approximate weights for columns based on max text length in each column.
    This helps assign wider columns to long content (eg. Nombre, Ref, Precio).
    """
    n = max(1, len(headers))
    max_lens = [len(str(headers[i] if i < len(headers) else "")) for i in range(n)]
    for r in rows:
        for i in range(n):
            try:
                v = str(r[i]) if i < len(r) else ""
                l = len(v)
                if l > max_lens[i]:
                    max_lens[i] = l
            except Exception:
                pass
    # convert lengths to weights with a small floor to avoid zero-width columns
    weights = [max(1.0, float(l)) for l in max_lens]
    # give a slight extra boost to the first columns commonly id/names so they don't become too narrow
    if n >= 3:
        weights[0] = max(weights[0], weights[0] * 1.0)  # ID
        weights[2] = max(weights[2], weights[2] * 1.2)  # Nombre
    return weights

def export_table_to_pdf(path: str, title: str, headers: List[str], rows: List[List[Any]],
                        company_info: Dict[str, str] = None, orientation: str = "landscape",
                        footer_note: str = None) -> Dict[str, str]:
    """
    Intenta exportar a PDF usando reportlab. Si no está disponible, exporta CSV.
    Devuelve diccionario con keys: type ('pdf' | 'csv') y path (ruta generada).

    Mejoras:
    - cálculo dinámico de anchos de columnas según contenido
    - uso de Paragraph para permitir word-wrapping en celdas
    - estilos ajustados para evitar superposición de texto
    """
    if company_info is None:
        company_info = {}

    # Lazy import reportlab
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape, portrait
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Try to register a local TTF if available for nicer look (not required)
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
            default_font = "DejaVu"
        except Exception:
            default_font = DEFAULT_FONT

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="TitleCenter", alignment=1, fontName=default_font, fontSize=14, leading=16))
        styles.add(ParagraphStyle(name="Small", fontSize=8, fontName=default_font))
        styles.add(ParagraphStyle(name="NormalSmall", fontSize=10, fontName=default_font))
        # style for table cells that allows wrapping
        cell_style = ParagraphStyle(
            name="Cell",
            fontName=default_font,
            fontSize=9,
            leading=11,  # leading slightly larger than font to avoid overlap
            spaceBefore=0,
            spaceAfter=0,
        )
        header_style = ParagraphStyle(
            name="Header",
            fontName=default_font,
            fontSize=10,
            leading=12,
            alignment=1,  # center
            spaceBefore=0,
            spaceAfter=0,
        )

        # Build doc
        if orientation == "landscape":
            page_size = landscape(A4)
        else:
            page_size = portrait(A4)

        _ensure_dir_for_file(path)
        doc = SimpleDocTemplate(path, pagesize=page_size, leftMargin=18*mm, rightMargin=18*mm, topMargin=24*mm, bottomMargin=18*mm)
        elements = []

        # header company info
        name = company_info.get("name")
        tax = company_info.get("tax_id")
        if name:
            elements.append(Paragraph(f"<b>{name}</b>", styles["NormalSmall"]))
        if tax:
            elements.append(Paragraph(f"RIF: {tax}", styles["NormalSmall"]))
        elements.append(Spacer(1, 4))

        if title:
            elements.append(Paragraph(title, styles["TitleCenter"]))
            elements.append(Spacer(1, 6))

        # prepare table data but using Paragraphs for wrapping
        data = []
        # header row as Paragraphs
        header_row = [Paragraph(str(h), header_style) for h in headers]
        data.append(header_row)

        # convert each cell to Paragraph to allow wrapping
        for r in rows:
            row_cells = []
            for c, h in enumerate(headers):
                try:
                    val = "" if c >= len(r) or r[c] is None else str(r[c])
                except Exception:
                    val = ""
                # replace multiple consecutive spaces which might collapse; keep as-is
                row_cells.append(Paragraph(val, cell_style))
            data.append(row_cells)

        # Calculate column widths based on content length (approx)
        page_w, _ = page_size
        usable = page_w - (doc.leftMargin + doc.rightMargin)
        # create weights from content lengths
        weights = _approx_column_weights(headers, rows)
        total_weight = float(sum(weights)) if sum(weights) > 0 else len(weights)
        # ensure a minimum width for each column to avoid extremely narrow columns
        min_col_mm = 18 * mm  # minimum 18 mm
        min_col_pt = min_col_mm
        # compute widths
        col_widths = []
        for w in weights:
            cw = usable * (w / total_weight)
            if cw < min_col_pt:
                cw = min_col_pt
            col_widths.append(cw)
        # If sum exceeds usable (when min enforced), scale down proportionally
        sum_cw = sum(col_widths)
        if sum_cw > usable:
            factor = usable / sum_cw
            col_widths = [cw * factor for cw in col_widths]

        # Create table
        t = Table(data, colWidths=col_widths, repeatRows=1)
        ts = TableStyle([
            ("FONTNAME", (0,0), (-1,-1), default_font),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EDE7F6")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#3F2D75")),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("ALIGN", (0,1), (-1,-1), "LEFT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CCCCCC")),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
        ])
        # Align numeric-looking columns to right (simple heuristic)
        numeric_headers = ["Cantidad", "Stock", "Costo", "Costo Compra", "IVA (%)", "Ganancia (%)", "Precio (Bs)", "Ref (USD)"]
        for col_idx, h in enumerate(headers):
            if any(k.lower() in str(h).lower() for k in numeric_headers):
                ts.add('ALIGN', (col_idx,1), (col_idx,-1), 'RIGHT')

        t.setStyle(ts)
        elements.append(t)

        if footer_note:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(footer_note, styles["Small"]))

        def _on_page(canvas, doc):
            canvas.saveState()
            w, h = doc.pagesize
            # header right: datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            canvas.setFont(default_font, 8)
            canvas.drawRightString(w - 18*mm, h - 12*mm, now)
            # footer page number
            canvas.drawRightString(w - 18*mm, 10*mm, f"Página {canvas.getPageNumber()}")
            canvas.restoreState()

        doc.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)
        return {"type": "pdf", "path": path}
    except Exception as e:
        # If reportlab not available or failed, fallback to CSV
        try:
            return _fallback_export_csv(path, headers, rows)
        except Exception as e2:
            raise e2

def export_qtablewidget_to_pdf(qtable, path: str, title: str = None, company_info: Dict[str, str] = None, orientation: str = "landscape") -> Dict[str, str]:
    """
    Extrae datos de un QTableWidget y llama a export_table_to_pdf.
    Si reportlab no está presente generará un CSV como fallback.
    """
    if company_info is None:
        company_info = {}

    headers = []
    for c in range(qtable.columnCount()):
        h = qtable.horizontalHeaderItem(c)
        headers.append(h.text() if h else f"Col {c}")

    rows = []
    for r in range(qtable.rowCount()):
        row = []
        for c in range(qtable.columnCount()):
            it = qtable.item(r, c)
            if it:
                row.append(it.text())
            else:
                w = qtable.cellWidget(r, c)
                if w is not None:
                    try:
                        txt = getattr(w, "text", lambda: "")()
                        row.append(str(txt()))
                    except Exception:
                        try:
                            row.append(str(w.text()))
                        except Exception:
                            row.append("")
                else:
                    row.append("")
        rows.append(row)

    return export_table_to_pdf(path, title or "Exportación", headers, rows, company_info=company_info, orientation=orientation)

