# modules/registro_general.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QLineEdit, QHBoxLayout, QWidget, QHeaderView, QMessageBox, QPushButton, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer
from db_manager import DBManager
import csv
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from modules.product_detail import ProductDetailDialog
from modules.pricing import calcular_precio_venta_actual, format_usd_minimal, format_bs_minimal

def _get_bcv_rate():
    try:
        from main import get_current_bcv_rate
        r, _ = get_current_bcv_rate()
        return r
    except Exception:
        return None

def _normalize_text(s: str) -> str:
    """Normalize string: lower-case and remove diacritics for tolerant comparisons."""
    if not s:
        return ""
    if not isinstance(s, str):
        s = str(s)
    s = s.strip().lower()
    # remove accents
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s

class RegistroGeneralWindow(QDialog):
    """
    Registro General (productos) con búsqueda en tiempo real.
    Todos los precios se muestran con USD como base permanente y Bs calculado dinámicamente.
    """
    def __init__(self, parent=None, departamento: str = None):
        super().__init__(parent)
        self.db = DBManager()
        self.setWindowTitle("Registro General - Productos")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(1000), scale_px(600))
        except Exception:
            self.resize(1000, 600)
        self.initial_department = departamento
        self._all_rows = []
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(180)
        main = QVBoxLayout(self)
        
        title = QLabel("Registro General de Productos")
        title.setObjectName("title")
        main.addWidget(title)
        
        # Info sobre moneda base
        info_lbl = QLabel("💡 Todos los precios se muestran en USD (base permanente) y Bs (calculado con tasa actual)")
        info_lbl.setObjectName("info_lbl")
        main.addWidget(info_lbl)
        
        search_bar_w = QWidget()
        search_bar_l = QHBoxLayout(search_bar_w)
        search_bar_l.setContentsMargins(0, 0, 0, 0)
        search_bar_l.addWidget(QLabel("Buscar producto:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Escriba el nombre del producto (filtro en tiempo real)...")
        search_bar_l.addWidget(self.search_input)
        self.export_pdf_btn = QPushButton("Exportar PDF")
        self.export_pdf_btn.clicked.connect(self._on_export_pdf)
        search_bar_l.addWidget(self.export_pdf_btn)
        main.addWidget(search_bar_w)
        
        # Columnas actualizadas para reflejar la nueva lógica
        headers = [
            "ID", 
            "Código", 
            "Nombre", 
            "Stock", 
            "Departamento", 
            "Precio Base ($)",      # ← USD permanente
            "Precio Hoy (Bs)",      # ← Calculado dinámicamente
            "Fecha de registro", 
            "Fecha de caducidad"
        ]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnHidden(0, True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        main.addWidget(self.table)
        
        self.info_lbl = QLabel("")
        self.info_lbl.setObjectName("info_lbl_status")
        main.addWidget(self.info_lbl)
        
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self._debounce_timer.timeout.connect(self._apply_filter)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.load_all_products()

    def load_all_products(self):
        try:
            rows = self.db.listar_productos() or []
            rows = sorted(rows, key=lambda r: (r.get('nombre') or '').lower())
            self._all_rows = rows
            if self.initial_department:
                target_norm = _normalize_text(self.initial_department)
                filtered = [r for r in rows if _normalize_text(r.get('departamento', '')) == target_norm]
            else:
                filtered = rows
            self._populate_table(filtered)
            self._update_info_label()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar productos: {e}")

    def _on_search_text_changed(self, text: str):
        self._debounce_timer.start()

    def _apply_filter(self):
        q = (self.search_input.text() or "").strip().lower()
        if not q:
            rows = self._all_rows
        else:
            rows = [r for r in self._all_rows if q in (r.get('nombre') or '').lower()]
        self._populate_table(rows)
        self._update_info_label()

    def _populate_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        rate = _get_bcv_rate()
        
        for r in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            pid = r.get('id', '')
            codigo = r.get('codigo', '') or ''
            nombre = r.get('nombre', '') or ''
            stock = r.get('stock', 0)
            try:
                sval = float(stock)
                stock_disp = int(sval) if sval.is_integer() else f"{sval:.3f}"
            except Exception:
                stock_disp = stock or 0
            departamento = r.get('departamento', '') or ''

            # === NUEVA LÓGICA: USD es base permanente, Bs se calcula dinámicamente ===
            precio_usd_base = r.get('precio_final')  # Precio PERMANENTE en USD
            
            # Calcular Bs actual usando la tasa del momento
            precio_bs_actual = None
            if precio_usd_base and rate:
                ref = calcular_precio_venta_actual(float(precio_usd_base), rate)
                precio_bs_actual = ref.get('precio_bs_actual')
            
            # Formatear USD (siempre mostrar, es la base permanente)
            try:
                usd_val = float(precio_usd_base) if precio_usd_base else 0.0
                usd_text = f"{usd_val:,.4f} $"
            except:
                usd_text = "-- $"
            
            # Formatear Bs (calculado dinámicamente)
            if precio_bs_actual:
                bs_text = f"{float(precio_bs_actual):,.2f} Bs"
            else:
                bs_text = "-- Bs"
            
            # Mostrar: USD (base) / Bs (calculado actual)
            precio_base_col = usd_text
            precio_bs_col = bs_text
            # === FIN NUEVA LÓGICA ===

            fecha_reg = r.get('fecha_registro', '') or ''
            fecha_cad = r.get('fecha_caducidad', '') or ''

            values = [pid, codigo, nombre, stock_disp, departamento, precio_base_col, precio_bs_col, fecha_reg, fecha_cad]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col in (2, 3, 5, 6):
                    item.setTextAlignment(Qt.AlignCenter)
                # Para sorting por precio en Bs
                if col == 6 and precio_bs_actual:
                    try:
                        item.setData(Qt.UserRole, float(precio_bs_actual))
                    except:
                        pass
                self.table.setItem(row_idx, col, item)
                
        self.table.setSortingEnabled(True)

    def _update_info_label(self):
        total = self.table.rowCount()
        tasa_info = ""
        rate = _get_bcv_rate()
        if rate:
            tasa_info = f" | Tasa BCV: {rate:,.2f} Bs/$"
        else:
            tasa_info = " | Tasa BCV: No disponible"
            
        if self.initial_department:
            self.info_lbl.setText(f"Productos mostrados: {total} (Departamento: {self.initial_department}){tasa_info}")
        else:
            self.info_lbl.setText(f"Productos mostrados: {total}{tasa_info}")

    def _on_row_double_clicked(self, row, column):
        try:
            id_item = self.table.item(row, 0)
            if not id_item:
                QMessageBox.warning(self, "Seleccionar", "No se pudo obtener el ID del producto.")
                return
            pid = id_item.text()
            try:
                prod_rows = self.db.fetchall("SELECT * FROM productos WHERE id = ?", (pid,)) or []
                prod = prod_rows[0] if prod_rows else None
            except Exception:
                prod = None
            dlg = ProductDetailDialog(self, db=self.db, product_id=pid, product_dict=prod)
            dlg.exec_()
            self.load_all_products()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir detalle del producto: {e}")

    def _on_export_pdf(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "registro_productos.pdf", "PDF Files (*.pdf);;All Files (*)")
            if not path:
                return
            # import lazy to avoid import-time errors
            try:
                from modules.pdf_exporter import export_qtablewidget_to_pdf
                company_info = {
                    "name": "Minimarket ChiChi N-K, C.A",
                    "tax_id": "J-5099900-7"
                }
                res = export_qtablewidget_to_pdf(self.table, path, title="Registro General de Productos", company_info=company_info, orientation="landscape")
                if res.get("type") == "pdf":
                    QMessageBox.information(self, "Exportar", f"PDF guardado en: {res.get('path')}")
                else:
                    QMessageBox.information(self, "Exportar", f"Reportlab no está disponible. Se generó CSV como fallback en: {res.get('path')}")
            except Exception:
                # fallback: export CSV
                csv_path = path.rsplit(".", 1)[0] + ".csv"
                try:
                    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                        writer = csv.writer(fh)
                        headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
                        writer.writerow(headers)
                        for r in range(self.table.rowCount()):
                            row_vals = []
                            for c in range(self.table.columnCount()):
                                it = self.table.item(r, c)
                                row_vals.append(it.text() if it else "")
                            writer.writerow(row_vals)
                    QMessageBox.information(self, "Exportar", f"CSV guardado en: {csv_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Exportar", f"Error al exportar CSV: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Exportar", f"Error al exportar PDF: {e}")

