from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextDocument, QFont
from PyQt5.QtPrintSupport import QPrinter
import os
import re
import datetime

class DialogoRegistroCompras(QDialog):
    """Diálogo que muestra el registro completo de entradas (movimientos tipo 'Entrada').
    Separado del cierre de ventas para no mezclar lógicas.
    """
    def __init__(self, db, parent=None, title='Registro de Entradas'):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(title)
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
        # Cargar todos los movimientos de tipo 'Entrada' (compras)
        try:
            rows = self.db.fetchall("SELECT * FROM movimientos WHERE tipo = ? ORDER BY fecha DESC", ("Entrada",)) or []
        except Exception:
            rows = []
        html = f"<h1>Registro de Entradas</h1>\n"
        if not rows:
            html += "<p>No hay registros de entradas.</p>"
        else:
            html += "<table style='width:100%;border-collapse:collapse'><tr><th style='border:1px solid #ddd;padding:6px'>Fecha</th><th style='border:1px solid #ddd;padding:6px'>Motivo</th><th style='border:1px solid #ddd;padding:6px'>Producto</th><th style='border:1px solid #ddd;padding:6px'>Cant.</th><th style='border:1px solid #ddd;padding:6px'>Costo (Bs)</th></tr>"
            total_general = 0.0
            for r in rows:
                fecha = r.get('fecha','')
                motivo = r.get('motivo') or ''
                # Remover prefijo 'Compra' (insensible a mayúsculas) para mostrar solo 'REG-...' u otro identificador
                try:
                    motivo = re.sub(r'(?i)^compra[:\s\-–—]*', '', motivo).strip()
                except Exception:
                    pass
                nombre = r.get('producto_nombre') or r.get('producto', '') or ''
                cantidad = r.get('cantidad') or 0
                try:
                    costo = float(r.get('costo') or 0.0)
                except Exception:
                    costo = 0.0
                total_general += costo
                html += f"<tr><td style='border:1px solid #ddd;padding:6px'>{fecha}</td><td style='border:1px solid #ddd;padding:6px'>{motivo}</td><td style='border:1px solid #ddd;padding:6px'>{nombre}</td><td style='border:1px solid #ddd;padding:6px'>{cantidad}</td><td style='border:1px solid #ddd;padding:6px'>{costo:,.2f} Bs</td></tr>"
            html += f"</table><h3>Total general: {total_general:,.2f} Bs</h3>"
        self.html_content = f"<html><body>{html}</body></html>"
        self.browser.setHtml(self.html_content)

    def _guardar_pdf(self):
        try:
            try:
                from modules import config as app_config
                pdf_base = app_config.get_pdf_dir()
            except Exception:
                pdf_base = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'registros')
            entradas_dir = os.path.join(pdf_base, 'entradas')
            os.makedirs(entradas_dir, exist_ok=True)
            filename = f"registro_entradas_{datetime.date.today().isoformat()}.pdf"
            out_path = os.path.join(entradas_dir, filename)
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Arial", 10))
            doc.setHtml(self.html_content)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(out_path)
            doc.print_(printer)
            QMessageBox.information(self, "Guardado", f"Registro guardado en: {out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar registro: {e}")
