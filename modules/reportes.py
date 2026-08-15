# modules/reportes.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QComboBox, QDateEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from db_manager import DBManager

def _get_bcv_rate():
    try:
        from main import get_current_bcv_rate
        r, _ = get_current_bcv_rate()
        return r
    except Exception:
        return None

class ReportesWindow(QDialog):
    """
    Reportes: para la vista Productos el encabezado combinado se reemplaza por "Ref" y se incluye "Precio (Bs)".
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DBManager()
        self.setWindowTitle("Reportes del Sistema")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(900), scale_px(600))
        except Exception:
            self.resize(900, 600)
        self.setStyleSheet("""
            QDialog { background-color: #F5F3FB; }
            QLabel { color: #5E3DB3; font-weight:700; }
        """)
        main = QVBoxLayout(self)

        title = QLabel("Reportes del Sistema")
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)

        filtros = QHBoxLayout()
        self.tipo_reporte = QComboBox()
        self.tipo_reporte.addItems([
            "Entradas",
            "Salidas",
            "Productos",
            "Caducidad"
        ])

        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDate(QDate.currentDate().addMonths(-1))
        self.fecha_fin = QDateEdit()
        self.fecha_fin.setCalendarPopup(True)
        self.fecha_fin.setDate(QDate.currentDate())

        self.btn_generar = QPushButton("Generar Reporte")
        self.btn_generar.clicked.connect(self.generar_reporte)

        filtros.addWidget(QLabel("Tipo de reporte"))
        filtros.addWidget(self.tipo_reporte)
        filtros.addWidget(QLabel("Desde"))
        filtros.addWidget(self.fecha_inicio)
        filtros.addWidget(QLabel("Hasta"))
        filtros.addWidget(self.fecha_fin)
        filtros.addWidget(self.btn_generar)
        main.addLayout(filtros)

        self.table = QTableWidget()
        main.addWidget(self.table)

    def generar_reporte(self):
        tipo = self.tipo_reporte.currentText()
        inicio = self.fecha_inicio.date().toString("yyyy-MM-dd")
        fin = self.fecha_fin.date().toString("yyyy-MM-dd")

        data = []
        headers = []
        rate = _get_bcv_rate()

        if tipo == "Entradas":
            data = self.db.reporte_entradas(inicio, fin)
            headers = ["ID", "Producto", "Cantidad", "Costo", "Fecha"]
        elif tipo == "Salidas":
            data = self.db.reporte_salidas(inicio, fin)
            headers = ["ID", "Producto", "Cantidad", "Costo", "Motivo", "Fecha"]
        elif tipo == "PRODUCTOS" or tipo == "Productos" or tipo.lower() == "productos":
            data = self.db.listar_productos()
            headers = ["ID", "Nombre", "Descripción", "Departamento", "Stock", "Ref", "Precio (Bs)"]
        elif tipo == "Caducidad":
            data = self.db.reporte_caducidad(inicio, fin)
            headers = ["ID", "Producto", "Fecha de Caducidad"]

        self.table.setRowCount(0)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_data in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            if isinstance(row_data, dict) or hasattr(row_data, "keys"):
                if tipo.lower() == "productos":
                    pid = row_data.get('id')
                    nombre = row_data.get('nombre') or ''
                    descripcion = row_data.get('descripcion') or ''
                    departamento = row_data.get('departamento') or ''
                    stock = row_data.get('stock') or 0
                    precio_final = row_data.get('precio_final') or 0.0
                    moneda = (row_data.get('moneda') or '$')
                    try:
                        p = float(precio_final)
                    except Exception:
                        p = 0.0
                    if moneda == "$":
                        usd = f"{p:,.2f} $"
                        if rate:
                            try:
                                bs_val = p * float(rate)
                                bs_only = f"{bs_val:,.2f} Bs"
                                price_disp = f"{usd} / {bs_only}"
                            except Exception:
                                bs_only = "-- Bs"
                                price_disp = f"{usd} / -- Bs"
                        else:
                            bs_only = "-- Bs"
                            price_disp = f"{usd} / -- Bs"
                    else:
                        bs_only = f"{p:,.2f} Bs"
                        try:
                            usd_equiv = p / float(rate) if rate and float(rate) else None
                            usd = f"{usd_equiv:,.2f} $" if usd_equiv is not None else "-- $"
                        except Exception:
                            usd = "-- $"
                        price_disp = f"{bs_only} / {usd}"
                    vals = [str(pid), nombre, descripcion, departamento, str(stock), price_disp, bs_only]
                    for col, val in enumerate(vals):
                        self.table.setItem(row, col, QTableWidgetItem(str(val)))
                else:
                    if isinstance(row_data, dict) or hasattr(row_data, "keys"):
                        keys = list(row_data.keys())
                        for col, key in enumerate(keys):
                            try:
                                self.table.setItem(row, col, QTableWidgetItem(str(row_data[key])))
                            except Exception:
                                self.table.setItem(row, col, QTableWidgetItem(""))
                    else:
                        for col, val in enumerate(row_data):
                            self.table.setItem(row, col, QTableWidgetItem(str(val)))
            else:
                for col, val in enumerate(row_data):
                    self.table.setItem(row, col, QTableWidgetItem(str(val)))

