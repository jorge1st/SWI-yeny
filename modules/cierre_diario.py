from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextDocument, QFont
from PyQt5.QtPrintSupport import QPrinter
import os
import datetime

class DialogoCierreDiario(QDialog):
    def __init__(self, db, parent=None, tipo='Entrada', title=None):
        super().__init__(parent)
        self.db = db
        self.tipo = tipo
        self.title = title or ("Entradas Del dia" if tipo == 'Entrada' else "Salidas Del dia")
        self.setWindowTitle(self.title)
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(900), scale_px(700))
        except Exception:
            self.resize(900, 700)
        self.html_content = ""
        self._build_ui()
        self._cargar_datos()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        layout.addWidget(self.browser)
        buttons = QHBoxLayout()
        self.btn_guardar = QPushButton("💾 Guardar PDF")
        self.btn_guardar.clicked.connect(self._guardar_pdf)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(self.btn_guardar)
        buttons.addStretch()
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

    def _cargar_datos(self):
        today_str = datetime.date.today().isoformat()
        # Mostrar transacciones del día según tipo ('Entrada' para compras, 'Salida' para ventas)
        rows = self.db.fetchall("SELECT * FROM movimientos WHERE tipo = ? AND fecha LIKE ? ORDER BY fecha ASC", (self.tipo, today_str + "%"))
        grouped = {}
        for r in rows:
            motivo = r.get('motivo') or self.tipo
            fecha = r.get('fecha') or ''
            if motivo not in grouped:
                grouped[motivo] = {'rows': [], 'total': 0.0, 'fecha': fecha}
            grouped[motivo]['rows'].append(r)
            try:
                grouped[motivo]['total'] += float(r.get('costo') or 0.0)
            except Exception:
                pass
        label = 'Entradas' if self.tipo == 'Entrada' else 'Salidas'
        html = f"<h1>{label} del día - {today_str}</h1>"
        total_general = 0.0
        if not grouped:
            html += f"<p>No hay {label.lower()} hoy.</p>"
        else:
            for motivo, data in grouped.items():
                html += f"<h3>{motivo} - {data.get('fecha','')}</h3>"
                html += "<table style='width:100%;border-collapse:collapse'><tr><th style='border:1px solid #ddd;padding:6px'>Producto</th><th style='border:1px solid #ddd;padding:6px'>Cantidad</th><th style='border:1px solid #ddd;padding:6px'>Precio</th><th style='border:1px solid #ddd;padding:6px'>Subtotal</th></tr>"
                for item in data['rows']:
                    nombre = item.get('producto_nombre','')
                    cantidad = item.get('cantidad') or 0
                    subtotal = float(item.get('costo') or 0.0)
                    precio_unit = subtotal / float(cantidad) if cantidad else subtotal
                    html += f"<tr><td style='border:1px solid #ddd;padding:6px'>{nombre}</td><td style='border:1px solid #ddd;padding:6px'>{cantidad}</td><td style='border:1px solid #ddd;padding:6px'>{precio_unit:,.2f} Bs</td><td style='border:1px solid #ddd;padding:6px'>{subtotal:,.2f} Bs</td></tr>"
                html += "</table>"
                html += f"<p><b>Total: {data['total']:,.2f} Bs</b></p><hr>"
                total_general += data['total']
            html += f"<h2>Total General: {total_general:,.2f} Bs</h2>"
        self.html_content = f"<html><body>{html}</body></html>"
        self.browser.setHtml(self.html_content)

    def _guardar_pdf(self):
        try:
            # Use configured PDF base directory (set by installer); fallback to Documents\Facturas
            try:
                from modules import config as app_config
                pdf_base = app_config.get_pdf_dir()
            except Exception:
                pdf_base = os.path.join(os.path.expanduser('~'), 'Documents', 'Registros')
            out_dir = os.path.join(pdf_base, 'cierres')
            os.makedirs(out_dir, exist_ok=True)
            filename = f"cierre_{datetime.date.today().isoformat()}.pdf"
            out_path = os.path.join(out_dir, filename)
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Arial", 10))
            doc.setHtml(self.html_content)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(out_path)
            doc.print_(printer)
            QMessageBox.information(self, "Guardado", f"Cierre guardado en: {out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar cierre: {e}")


