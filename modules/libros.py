# modules/libros.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QDate, QTimer
from db_manager import DBManager
from modules.pdf_exporter import export_table_to_pdf
import datetime
import calendar

_COMPANY_INFO = {
    "name": "Minimarket ChiChi N-K, C.A",
    "tax_id": "J-5099900-7"
}

class LibrosWidget(QWidget):
    """
    Widget que muestra el Libro de Compras o Libro de Ventas en pantalla:
    - lee movimientos desde la tabla 'movimientos'
    - filtra por tipo ('Entrada' => Compras, 'Salida' => Ventas)
    - presenta columnas típicas requeridas en libros contables
    - permite exportar a PDF (o CSV como fallback si reportlab no está ausente)
    - diseñado para reemplazar el contenido principal del Dashboard (no ventana modal)
    """

    def __init__(self, parent=None, default_book="compras"):
        super().__init__(parent)
        self.db = DBManager()
        self.current_book = default_book  # 'compras' or 'ventas'
        self._build_ui()
        # load initial
        QTimer.singleShot(0, lambda: self.refresh())

    def _build_ui(self):
        self.setLayout(QVBoxLayout())
        header = QHBoxLayout()
        title = QLabel("Libros Contables")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#5E3DB3;")
        header.addWidget(title)
        header.addStretch()

        # Book selector (compras/ventas) - but we'll also expose via Dashboard buttons
        self.book_cb = QComboBox()
        self.book_cb.addItem("Libro de Entradas", "compras")
        self.book_cb.addItem("Libro de Salidas", "ventas")
        self.book_cb.setCurrentIndex(0 if self.current_book == "compras" else 1)
        self.book_cb.currentIndexChanged.connect(self._on_book_changed)
        header.addWidget(QLabel("Libro:"))
        header.addWidget(self.book_cb)

        # Date range filters
        self.fecha_desde = QDateEdit()
        self.fecha_desde.setCalendarPopup(True)
        self.fecha_desde.setDisplayFormat("yyyy-MM-dd")
        self.fecha_desde.setDate(QDate.currentDate().addMonths(-1))
        self.fecha_hasta = QDateEdit()
        self.fecha_hasta.setCalendarPopup(True)
        self.fecha_hasta.setDisplayFormat("yyyy-MM-dd")
        self.fecha_hasta.setDate(QDate.currentDate())

        header.addWidget(QLabel("Desde:"))
        header.addWidget(self.fecha_desde)
        header.addWidget(QLabel("Hasta:"))
        header.addWidget(self.fecha_hasta)

        # Generate & Export
        self.btn_generar = QPushButton("Generar")
        self.btn_generar.clicked.connect(self.refresh)
        header.addWidget(self.btn_generar)

        self.btn_export = QPushButton("Exportar PDF")
        self.btn_export.clicked.connect(self._on_export)
        header.addWidget(self.btn_export)

        # Back to dashboard placeholder (parent must implement restore_main_view)
        self.btn_volver = QPushButton("Volver al panel")
        self.btn_volver.clicked.connect(self._on_back)
        header.addWidget(self.btn_volver)

        self.layout().addLayout(header)

        # Table area
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout().addWidget(self.table)

        # Totals row
        totals_row = QHBoxLayout()
        totals_row.addItem(QSpacerItem(12, 12, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.totales_lbl = QLabel("")
        totals_row.addWidget(self.totales_lbl)
        self.layout().addLayout(totals_row)

    def _on_book_changed(self, idx):
        self.current_book = self.book_cb.currentData()
        self.refresh()

    def _on_back(self):
        # parent (Dashboard) must implement restore_dashboard_view(widget)
        parent = self.parent()
        try:
            if parent and hasattr(parent, "restore_dashboard_view"):
                parent.restore_dashboard_view()
            else:
                # try to call generic method to restore
                if parent and hasattr(parent, "show_dashboard_main"):
                    parent.show_dashboard_main()
        except Exception:
            pass

    def _get_date_range(self):
        d1 = self.fecha_desde.date().toString("yyyy-MM-dd")
        d2 = self.fecha_hasta.date().toString("yyyy-MM-dd")
        # ensure order
        try:
            sd = datetime.datetime.strptime(d1, "%Y-%m-%d").date()
            ed = datetime.datetime.strptime(d2, "%Y-%m-%d").date()
            if sd > ed:
                sd, ed = ed, sd
            return sd.isoformat(), ed.isoformat()
        except Exception:
            today = datetime.date.today()
            return today.replace(day=1).isoformat(), today.isoformat()

    def _build_rows_for_book(self, rows_raw):
        """
        Given raw movimientos rows (dicts), build the table rows and headers for the selected book.
        We try to include as many accounting fields as available in the DB:
         - Fecha, N° Documento (mov id or motivo if present), Tipo Documento, RIF, Nombre Tercero,
           Código Producto, Producto, Cantidad, Unidad, Precio Unitario, Base, IVA, Total
        """
        headers = [
            "Fecha", "Nº Doc", "Tipo Doc", "RIF", "Nombre / Tercero",
            "Código", "Producto", "Cantidad", "Unidad", "Precio Unit.",
            "Base (Bs)", "IVA (Bs)", "Total (Bs)"
        ]
        rows = []
        sum_base = 0.0
        sum_iva = 0.0
        sum_total = 0.0

        for r in rows_raw:
            fecha = r.get('fecha') or r.get('fecha_registro') or ""
            doc = r.get('motivo') or f"MV-{r.get('id')}"
            tipo_doc = r.get('tipo_documento') or r.get('documento_tipo') or ""
            rif = r.get('rif') or r.get('tercero_rif') or r.get('ruc') or ""
            tercero = r.get('tercero') or r.get('nombre_tercero') or r.get('producto_nombre') or ""
            codigo = r.get('codigo_producto') or r.get('codigo') or ""
            producto = r.get('producto_nombre') or ""
            cantidad = float(r.get('cantidad') or 0.0)
            unidad = r.get('unidad') or ""
            precio_unit = None
            # compute price unit from costo if present and cantidad>0
            if cantidad and float(cantidad) != 0:
                try:
                    precio_unit = float(r.get('costo') or 0.0)  # movements store cost
                except Exception:
                    precio_unit = 0.0
            else:
                precio_unit = float(r.get('costo') or 0.0)

            # Base (net) and IVA: if movimientos store 'iva' or we must infer
            iva_val = float(r.get('iva') or 0.0)
            base = precio_unit * cantidad
            iva_bs = (base * iva_val / 100.0) if iva_val else 0.0
            total = base + iva_bs

            sum_base += base
            sum_iva += iva_bs
            sum_total += total

            row = [
                fecha,
                doc,
                tipo_doc,
                rif,
                tercero,
                codigo,
                producto,
                f"{cantidad:.3f}",
                unidad,
                f"{precio_unit:,.4f}",
                f"{base:,.2f}",
                f"{iva_bs:,.2f}",
                f"{total:,.2f}"
            ]
            rows.append(row)

        totals = {
            "base": sum_base,
            "iva": sum_iva,
            "total": sum_total
        }
        return headers, rows, totals

    def refresh(self):
        """
        Query movimientos depending on book and date range, fill the table.
        """
        start, end = self._get_date_range()
        # map book type -> movement tipo
        tipo = "Entrada" if self.current_book == "compras" else "Salida"
        # Query: select movements in range and of given tipo.
        # We select many fields in case DB has them; if not present, fetch available ones.
        q = """
            SELECT id, codigo_producto, producto_id, producto_nombre, departamento,
                   tipo, cantidad, costo, fecha, motivo,
                   unidad, iva, -- attempt to read iva column if exists
                   tercero, rif, tipo_documento
            FROM movimientos
            WHERE tipo = ? AND date(fecha) BETWEEN date(?) AND date(?)
            ORDER BY date(fecha), id
        """
        try:
            rows = self.db.fetchall(q, (tipo, start, end)) or []
        except Exception:
            # fallback if DB schema differs: select generic columns
            q2 = "SELECT id, codigo_producto, producto_id, producto_nombre, tipo, cantidad, costo, fecha, motivo FROM movimientos WHERE tipo = ? AND date(fecha) BETWEEN date(?) AND date(?) ORDER BY date(fecha), id"
            rows = self.db.fetchall(q2, (tipo, start, end)) or []

        headers, rows_table, totals = self._build_rows_for_book(rows)

        # fill QTableWidget
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels(headers)
        for r in rows_table:
            idx = self.table.rowCount()
            self.table.insertRow(idx)
            for c, v in enumerate(r):
                item = QTableWidgetItem(str(v))
                if c in (7, 10, 11, 12):  # numeric columns center
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(idx, c, item)

        self.totales_lbl.setText(
            f"Totales → Base: {totals['base']:,.2f} Bs    IVA: {totals['iva']:,.2f} Bs    Total: {totals['total']:,.2f} Bs"
        )

    def _on_export(self):
        # prepare headers and rows from current table
        try:
            if self.table.rowCount() == 0:
                QMessageBox.information(self, "Exportar", "No hay registros para exportar en el rango seleccionado.")
                return
            headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
            rows = []
            for r in range(self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    row.append(it.text() if it else "")
                rows.append(row)
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", f"libro_{self.current_book}.pdf", "PDF Files (*.pdf);;All Files (*)")
            if not path:
                return
            title = "Libro de Entradas" if self.current_book == "compras" else "Libro de Salidas"
            res = export_table_to_pdf(path, title, headers, rows, company_info=_COMPANY_INFO, orientation="landscape",
                                      footer_note=f"Generado desde Sistema — Libro: {title}")
            if res.get("type") == "pdf":
                QMessageBox.information(self, "Exportar", f"PDF guardado en: {res.get('path')}")
            else:
                QMessageBox.information(self, "Exportar", f"Reportlab no está disponible. Se generó CSV como fallback en: {res.get('path')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar: {e}")

