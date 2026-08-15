# modules/caducidad.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from db_manager import DBManager
import datetime
import os

# Theme colors (fallback)
_PRIMARY = "#6B4ED6"
_SECONDARY = "#8E6BE6"

class CaducidadWindow(QDialog):
    """
    Control de caducidad:
      - Lista productos con fecha de caducidad, ordenados por días restantes (ascendente).
      - Colorea filas según proximidad.
      - Exporta a PDF (fallback CSV si reportlab no está instalado).
      - Método soon_to_expire_count(days=3).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setObjectName("caducidad")
        except Exception:
            pass
        self.db = DBManager()
        self.setWindowTitle("Productos con stock bajo")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(820), scale_px(550))
        except Exception:
            self.resize(820, 550)

        # Load styles.qss if present (scaled)
        try:
            base_dir = os.path.dirname(__file__)
            candidates = [
                os.path.join(base_dir, "styles.qss"),
                os.path.join(base_dir, "..", "styles.qss"),
                os.path.join(os.getcwd(), "styles.qss"),
            ]
            css = None
            for c in candidates:
                cpath = os.path.abspath(c)
                if os.path.exists(cpath):
                    with open(cpath, "r", encoding="utf-8", errors="ignore") as fh:
                        css = fh.read()
                    break
            if css:
                try:
                    from modules.ui_scaling import scale_qss
                    css = scale_qss(css)
                except Exception:
                    pass
                self.setStyleSheet(css)
        except Exception:
            pass

        layout = QVBoxLayout(self)

        title = QLabel("Control de Caducidad y Stock")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("title")
        layout.addWidget(title)

        btns = QHBoxLayout()
        self.btn_export = QPushButton("Exportar PDF")
        self.btn_export.clicked.connect(self.export_pdf)
        btns.addStretch()
        btns.addWidget(self.btn_export)
        layout.addLayout(btns)

        # Columns: ID, Código, Nombre, Stock, Fecha Caducidad, Días Restantes/Estado
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Stock", "Fecha Caducidad", "Días Restantes"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.load_data()

    def _parse_date(self, iso_str):
        try:
            return datetime.datetime.strptime(iso_str[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    def load_data(self):
        self.table.setRowCount(0)
        try:
            rows = self.db.fetchall("""SELECT id, codigo, nombre, COALESCE(stock,0) as stock, fecha_caducidad FROM productos
                                        WHERE (fecha_caducidad IS NOT NULL AND fecha_caducidad != '') OR COALESCE(stock,0) <= ?
                                        ORDER BY fecha_caducidad ASC, stock ASC""", (10,)) or []
        except Exception:
            rows = []
        hoy = datetime.date.today()
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get('id') or '')))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get('codigo') or '')))
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get('nombre') or '')))
            stock_val = r.get('stock')
            try:
                stock_text = str(int(float(stock_val))) if float(stock_val).is_integer() else f"{float(stock_val):,.3f}"
            except Exception:
                stock_text = str(stock_val or '0')
            stock_item = QTableWidgetItem(stock_text)
            stock_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, stock_item)

            fecha_raw = r.get('fecha_caducidad')
            fd = self._parse_date(fecha_raw) if fecha_raw else None
            fecha_text = fd.isoformat() if fd else ''
            self.table.setItem(row, 4, QTableWidgetItem(fecha_text))

            dias_item = QTableWidgetItem('')
            if fd:
                try:
                    delta = (fd - hoy).days
                    dias_item = QTableWidgetItem(str(delta))
                    dias_item.setTextAlignment(Qt.AlignCenter)
                    # color by proximity
                    if delta < 0:
                        # expired
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it:
                                it.setBackground(QColor(255,200,200))
                    elif delta <= 30:
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it:
                                it.setBackground(QColor(255,240,200))
                    else:
                        for c in range(self.table.columnCount()):
                            it = self.table.item(row, c)
                            if it:
                                it.setBackground(QColor(220,255,220))
                except Exception:
                    pass
            self.table.setItem(row, 5, dias_item)
    def export_pdf(self):
        """
        Export table to PDF using modules.pdf_exporter.export_qtablewidget_to_pdf.
        If reportlab isn't installed the exporter returns a CSV fallback and we report that to the user.
        """
        try:
            path, _ = QFileDialog.getSaveFileName(self, 'Guardar PDF', 'caducidad.pdf', 'PDF files (*.pdf);;All Files (*)')
            if not path:
                return
            # lazy import of exporter to avoid import-time failures
            from modules.pdf_exporter import export_qtablewidget_to_pdf
            company_info = {
                "name": "Minimarket ChiChi N-K, C.A",
                "tax_id": "J-5099900-7"
            }
            res = export_qtablewidget_to_pdf(self.table, path, title="Productos con stock bajo", company_info=company_info, orientation="landscape")
            if res.get("type") == "pdf":
                QMessageBox.information(self, "Exportar", f"PDF guardado en: {res.get('path')}")
            else:
                QMessageBox.information(self, "Exportar", f"Reportlab no está disponible. Se generó CSV como fallback en: {res.get('path')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar: {e}")

    def soon_to_expire_count(self, days=3):
        # Repurposed: return count of products with low stock (<= 10). 'days' parameter is ignored.
        rows = self.db.fetchall("SELECT id FROM productos WHERE COALESCE(stock,0) <= ?", (10,)) or []
        return len(rows)
        rows = self.db.fetchall("SELECT id, fecha_caducidad FROM productos WHERE fecha_caducidad IS NOT NULL AND fecha_caducidad != ''") or []
        hoy = datetime.date.today()
        cnt = 0
        for r in rows:
            fd = r.get('fecha_caducidad')
            try:
                d = datetime.datetime.strptime(fd[:10], "%Y-%m-%d").date()
                delta = (d - hoy).days
                if delta >= 0 and delta <= days:
                    cnt += 1
            except Exception:
                continue
        return cnt

