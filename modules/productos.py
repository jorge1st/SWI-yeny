# modules/productos.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QDoubleSpinBox,
    QFileDialog, QMessageBox, QWidget, QDateEdit, QFrame, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, QDate, QSize, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from decimal import Decimal
from db_manager import DBManager
from modules.product_detail import ProductDetailDialog
from modules.pricing import calcular_desde_usd, calcular_desde_bs, format_usd_minimal, format_bs_minimal, calcular_precio_venta_actual
import os
import csv
from shutil import copyfile

# For autosave / archiving
import hashlib
import json
import tempfile
import shutil
import datetime
from modules.pdf_exporter import export_qtablewidget_to_pdf

DEBUG = False

# Autosave configuration (adjustable)
_AUTOSAVE_INTERVAL_MS = 2 * 60 * 1000    # 2 minutes
_DATE_CHECK_INTERVAL_MS = 60 * 1000      # 1 minute
_ARCHIVE_BASE = os.path.join(os.getcwd(), "archives", "productos")


def _get_bcv_rate():
    try:
        from main import get_current_bcv_rate
        r, _ = get_current_bcv_rate()
        return r
    except Exception:
        return None


def _ensure_dir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


def _date_str(dt: datetime.date = None) -> str:
    if dt is None:
        dt = datetime.date.today()
    return dt.strftime("%Y-%m-%d")


def _snapshot_hash(snapshot: dict) -> str:
    try:
        payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
    except Exception:
        return ""


def _atomic_write(src_path: str, final_path: str):
    _ensure_dir(os.path.dirname(final_path))
    try:
        os.replace(src_path, final_path)
    except Exception:
        try:
            shutil.copyfile(src_path, final_path)
        except Exception:
            pass
        try:
            os.remove(src_path)
        except Exception:
            pass


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview_widget")
        # preview widget styling moved to styles/modules/productos.qss
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(0)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        try:
            from modules.ui_scaling import scale_px

            self.img_label.setFixedSize(scale_px(160), scale_px(110))
        except Exception:
            self.img_label.setFixedSize(160, 110)
        self.layout.addStretch()
        self.layout.addWidget(self.img_label, alignment=Qt.AlignCenter)
        self.layout.addStretch()

        self.overlay_btn = QPushButton("", self)
        self.overlay_btn.setToolTip("Cargar imagen")
        self.overlay_btn.setCursor(Qt.PointingHandCursor)
        try:
            from modules.ui_scaling import scale_px

            self.overlay_btn.setFixedSize(scale_px(44), scale_px(44))
        except Exception:
            self.overlay_btn.setFixedSize(44, 44)
        icon = QIcon.fromTheme("camera-photo")
        if not icon.isNull():
            self.overlay_btn.setIcon(icon)
            try:
                from modules.ui_scaling import scale_px

                self.overlay_btn.setIconSize(QSize(scale_px(20), scale_px(20)))
            except Exception:
                self.overlay_btn.setIconSize(QSize(20, 20))
        else:
            self.overlay_btn.setText("📷")
        # overlay button visuals moved to QSS
        self.overlay_btn.setObjectName("overlay_btn")
        self.overlay_btn.raise_()

    def resizeEvent(self, ev):
        lbl = self.img_label
        if lbl:
            lbl_pos = lbl.pos()
            lw = lbl.width()
            lh = lbl.height()
            bx = lbl_pos.x() + (lw - self.overlay_btn.width()) // 2
            by = lbl_pos.y() + (lh - self.overlay_btn.height()) // 2
            self.overlay_btn.move(bx, by)
        super().resizeEvent(ev)

    def set_pixmap(self, path):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(self.img_label.width(), self.img_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.img_label.setPixmap(scaled)
                return
        self.img_label.setPixmap(QPixmap())


class ProductosWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DBManager()
        self.setWindowTitle("Registro de Productos")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(1100), scale_px(740))
        except Exception:
            self.resize(1100, 740)
        self.img_path = None
        self.last_deleted = None

        # Archiver state
        _ensure_dir(_ARCHIVE_BASE)
        self._last_snapshot = {"headers": [], "rows": []}
        self._last_saved_hash = None
        self._last_saved_date = _date_str()
        # timers
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(_AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)

        self._date_check_timer = QTimer(self)
        self._date_check_timer.setInterval(_DATE_CHECK_INTERVAL_MS)
        self._date_check_timer.timeout.connect(self._on_date_check_tick)

        self._build_ui()
        QTimer.singleShot(0, self._post_init)
        QTimer.singleShot(0, self._refresh_bcv_display)

    def _post_init(self):
        # initial load
        try:
            self.cargar_tabla()
        except Exception:
            pass
        try:
            # Focus the code field so barcode scanners will type into it when opening the product form
            self.codigo_edit.setFocus()
        except Exception:
            pass
        # capture snapshot
        try:
            self._capture_snapshot()
            # initial save to ensure at least one file exists for today (only if content non-empty)
            if self._snapshot_has_data():
                self._save_snapshot_now()
        except Exception:
            pass
        # start timers
        try:
            self._autosave_timer.start()
            self._date_check_timer.start()
        except Exception:
            pass

    def _build_ui(self):
        self.field_style = """
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                border: 2px solid #C5B4E3;
                border-radius: 8px;
                padding: 6px;
                background: white;
                font-size: 13px;
            }
            QPushButton#undo_btn {
                background: #FFD966;
                color: #333;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight:700;
            }
        """
        # Styling moved to styles/modules/productos.qss
        self.setObjectName("productos")
        self.main_layout = QVBoxLayout(self)

        title = QLabel("Registro de Productos")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#5E3DB3;")
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)

        form_w = QWidget()
        grid = QGridLayout(form_w)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.codigo_edit = QLineEdit(self._generar_codigo())
        # Allow manual input so barcode scanners can fill the code when registering a product
        self.codigo_edit.setReadOnly(False)
        self.codigo_edit.setObjectName("codigo_edit")
        grid.addWidget(QLabel("Código:"), 0, 0)
        grid.addWidget(self.codigo_edit, 0, 1, 1, 3)

        self.nombre_edit = QLineEdit()
        grid.addWidget(QLabel("Nombre:"), 1, 0)
        grid.addWidget(self.nombre_edit, 1, 1, 1, 3)

        self.depto_cb = QComboBox()
        for d in ["Productos de Limpieza", "Confiteria", "Lacteos", "Aseo Personal", "Vivieres", "Bebidas", "Farmacia", "Bisuteria", "Ferreteria"]:
            self.depto_cb.addItem(d)
        grid.addWidget(QLabel("Departamento:"), 2, 0)
        grid.addWidget(self.depto_cb, 2, 1)

        stock_widget = QWidget()
        stock_layout = QHBoxLayout(stock_widget)
        stock_layout.setContentsMargins(0, 0, 0, 0)
        stock_layout.setSpacing(8)
        self.unidad_cb = QComboBox()
        self.unidad_cb.addItems(["und", "kg", "Litros", "Metro"])
        try:
            from modules.ui_scaling import scale_px

            self.unidad_cb.setFixedWidth(scale_px(100))
        except Exception:
            self.unidad_cb.setFixedWidth(100)
        self.stock_spin = QDoubleSpinBox()
        self.stock_spin.setDecimals(3)
        self.stock_spin.setRange(0, 1000000)
        self.stock_spin.setSingleStep(0.1)
        try:
            from modules.ui_scaling import scale_px

            self.stock_spin.setFixedWidth(scale_px(160))
        except Exception:
            self.stock_spin.setFixedWidth(160)
        stock_layout.addWidget(self.unidad_cb)
        stock_layout.addWidget(self.stock_spin)
        stock_layout.addStretch()
        grid.addWidget(QLabel("Stock inicial / Unidad:"), 2, 2)
        grid.addWidget(stock_widget, 2, 3)

        self.costo_compra_edit = QLineEdit("0.00")
        grid.addWidget(QLabel("Costo de compra:"), 3, 0)
        grid.addWidget(self.costo_compra_edit, 3, 1)

        self.iva_edit = QLineEdit("16")
        self.ganancia_edit = QLineEdit("30")
        grid.addWidget(QLabel("IVA (%):"), 3, 2)
        grid.addWidget(self.iva_edit, 3, 3)
        grid.addWidget(QLabel("Ganancia (%):"), 4, 0)
        grid.addWidget(self.ganancia_edit, 4, 1)

        # Fecha de caducidad (opcional) - colocado debajo de Ganancia
        grid.addWidget(QLabel("Fecha de caducidad:"), 5, 0)
        self.has_cad_cb = QCheckBox("Tiene fecha de caducidad")
        self.has_cad_cb.setChecked(True)
        self.fecha_cad_edit = QDateEdit()
        self.fecha_cad_edit.setCalendarPopup(True)
        self.fecha_cad_edit.setDisplayFormat("yyyy-MM-dd")
        self.fecha_cad_edit.setDate(QDate.currentDate())
        self.fecha_cad_edit.setEnabled(True)
        self.has_cad_cb.toggled.connect(self.fecha_cad_edit.setEnabled)
        try:
            from modules.ui_scaling import scale_px
            self.fecha_cad_edit.setFixedWidth(scale_px(120))
        except Exception:
            self.fecha_cad_edit.setFixedWidth(120)
        cad_w = QWidget(); cad_l = QHBoxLayout(cad_w); cad_l.setContentsMargins(0,0,0,0); cad_l.addWidget(self.has_cad_cb); cad_l.addWidget(self.fecha_cad_edit)
        grid.addWidget(cad_w, 5, 1)

        self.moneda_cb = QComboBox()
        self.moneda_cb.addItems(["$", "Bs"])
        grid.addWidget(QLabel("Moneda:"), 4, 2)
        grid.addWidget(self.moneda_cb, 4, 3)

        # === NUEVA ETIQUETA: Mostrar que USD es la moneda base ===
        self.bcv_lbl = QLabel("Tasa BCV: No disponible")
        self.bcv_lbl.setObjectName("bcv_lbl")
        grid.addWidget(self.bcv_lbl, 6, 0, 1, 2)
        
        info_base = QLabel("💡 Todos los productos se guardan en $ como base")
        info_base.setObjectName("info_base")
        grid.addWidget(info_base, 6, 2, 1, 2)

        # Fecha de caducidad eliminado (campo deshabilitado según requerimiento)

        # === ETIQUETAS DE PRECIO ACTUALIZADAS ===
        grid.addWidget(QLabel("Precio de venta:"), 7, 2)
        precios_row = QWidget()
        precios_layout = QHBoxLayout(precios_row)
        precios_layout.setContentsMargins(0, 0, 0, 0)
        precios_layout.setSpacing(10)
        
        self.precio_usd_lbl = QLabel("-- $")
        self.precio_bs_lbl = QLabel("-- Bs")
        self.precio_usd_lbl.setObjectName("precio_usd")  # Verde para destacar
        self.precio_bs_lbl.setObjectName("precio_bs")      # Gris para secundario
        
        precios_layout.addWidget(QLabel("Base ($):"))
        precios_layout.addWidget(self.precio_usd_lbl)
        precios_layout.addStretch()
        precios_layout.addWidget(QLabel("Ref. hoy (Bs):"))
        precios_layout.addWidget(self.precio_bs_lbl)
        
        grid.addWidget(precios_row, 7, 3)

        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Box)
        preview_frame.setObjectName("preview_frame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(8)
        self.preview = PreviewWidget()
        self.preview.overlay_btn.clicked.connect(self._cargar_imagen)
        preview_layout.addWidget(self.preview, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("Imagen:"), 8, 0)
        grid.addWidget(preview_frame, 8, 1, 1, 3)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        self.nuevo_btn = QPushButton("Nuevo")
        self.guardar_btn = QPushButton("Guardar")
        try:
            from modules.ui_scaling import scale_px

            self.nuevo_btn.setFixedWidth(scale_px(100))
        except Exception:
            self.nuevo_btn.setFixedWidth(100)
        try:
            from modules.ui_scaling import scale_px

            self.guardar_btn.setFixedWidth(scale_px(100))
        except Exception:
            self.guardar_btn.setFixedWidth(100)
        self.guardar_btn.setDefault(True)
        self.guardar_btn.setAutoDefault(True)
        btn_layout.addWidget(self.nuevo_btn)
        btn_layout.addWidget(self.guardar_btn)
        grid.addWidget(btn_row, 9, 0, 1, 4)

        try:
            self.nombre_edit.returnPressed.connect(self.guardar_producto)
            # If barcode scanner sends Enter while focused on code, move focus to name (so user can press Enter to save)
            self.codigo_edit.returnPressed.connect(lambda: self.nombre_edit.setFocus())
        except Exception:
            pass

        self.costo_compra_edit.textChanged.connect(self._update_prices)
        self.iva_edit.textChanged.connect(self._update_prices)
        self.ganancia_edit.textChanged.connect(self._update_prices)
        self.moneda_cb.currentIndexChanged.connect(self._update_prices)
        self.guardar_btn.clicked.connect(self.guardar_producto)
        self.nuevo_btn.clicked.connect(self.limpiar_form)

        self.main_layout.addWidget(form_w)

        # === TABLA CON COLUMNAS ACTUALIZADAS ===
        headers = [
            "ID", "Código", "Nombre", "Departamento", "Stock", "Unidad",
            "Costo Compra", "IVA (%)", "Ganancia (%)", 
            "Precio Base ($)",      # ← Antes "Ref (USD)"
            "Precio Hoy (Bs)",      # ← Antes "Precio (Bs)" - calculado dinámico
            "Acciones"
        ]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.main_layout.addWidget(self.table)

    def _refresh_bcv_display(self):
        rate = _get_bcv_rate()
        if rate:
            self.bcv_lbl.setText(f"Tasa BCV: {rate:,.6f} Bs/$")
        else:
            self.bcv_lbl.setText("Tasa BCV: No disponible - Se necesita para registrar en Bs")
        self._update_prices()

    def _update_prices(self):
        """Actualiza la visualización de precios mostrando USD como base permanente y Bs como referencia actual."""
        rate = _get_bcv_rate()
        moneda = (self.moneda_cb.currentText() or '$').strip()
        costo_text = self.costo_compra_edit.text() or "0"
        iva_text = self.iva_edit.text() or "0"
        gan_text = self.ganancia_edit.text() or "0"

        try:
            if moneda in ('$', 'usd', 'USD'):
                # Registro en USD: calculo directo
                res = calcular_desde_usd(costo_text, iva_text, gan_text, rate)
                pf_with_iva_usd = res.get("precio_with_iva_usd")
                
                # Calcular referencia Bs actual si hay tasa
                if pf_with_iva_usd and rate:
                    ref_bs = calcular_precio_venta_actual(float(pf_with_iva_usd), rate)
                    precio_bs = ref_bs.get("precio_bs_actual")
                else:
                    precio_bs = None
                
                self.precio_usd_lbl.setText(format_usd_minimal(pf_with_iva_usd))
                self.precio_bs_lbl.setText(format_bs_minimal(precio_bs))
            else:
                # Registro en Bs: calculo en Bs pero CONVIERTO a USD para guardar
                if not rate:
                    self.precio_usd_lbl.setText("Necesita tasa BCV")
                    self.precio_bs_lbl.setText("-- Bs")
                    return
                    
                res = calcular_desde_bs(costo_text, iva_text, gan_text, rate)
                pf_with_iva_usd = res.get("precio_with_iva_usd")  # ← ESTO se guarda como base
                pf_with_iva_bs = res.get("precio_with_iva_bs")   # ← Referencia al momento
                
                # USD es el precio base permanente (destacado)
                self.precio_usd_lbl.setText(format_usd_minimal(pf_with_iva_usd))
                # Bs es lo que el usuario ingresó (referencia)
                self.precio_bs_lbl.setText(format_bs_minimal(pf_with_iva_bs))
        except Exception as e:
            self.precio_usd_lbl.setText("-- $")
            self.precio_bs_lbl.setText("-- Bs")

    def _cargar_imagen(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", "Images (*.png *.jpg *.jpeg *.bmp)")
            if path:
                os.makedirs('img', exist_ok=True)
                dest = os.path.join('img', os.path.basename(path))
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest)
                    i = 1
                    while os.path.exists(f"{base}_{i}{ext}"):
                        i += 1
                    dest = f"{base}_{i}{ext}"
                try:
                    copyfile(path, dest)
                    self.img_path = dest
                    self.preview.set_pixmap(dest)
                except Exception as ex:
                    QMessageBox.warning(self, "Imagen", f"No se pudo copiar la imagen: {ex}")
        except Exception as e:
            QMessageBox.warning(self, "Imagen", f"No se pudo cargar: {e}")

    def _generar_codigo(self):
        try:
            cur = self.db.conn.cursor()
            cur.execute("SELECT codigo FROM productos ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row and row[0]:
                import re
                m = re.search(r"(\d+)$", row[0])
                if m:
                    n = int(m.group(1)) + 1
                    return f"PRD-{n:04d}"
            return "PRD-0001"
        except Exception:
            return "PRD-0001"

    def validar(self):
        if not self.nombre_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre es obligatorio.")
            return False
        try:
            Decimal(str(self.costo_compra_edit.text() or "0"))
        except Exception:
            QMessageBox.warning(self, "Validación", "Costo inválido.")
            return False
        
        # Validar que si es Bs, haya tasa BCV
        moneda = (self.moneda_cb.currentText() or '$').strip()
        if moneda == "Bs":
            rate = _get_bcv_rate()
            if not rate:
                QMessageBox.warning(self, "Validación", 
                    "Se requiere la tasa BCV para registrar en Bs.\\n"
                    "El sistema convertirá a USD para proteger el valor del producto.")
                return False
        return True

    def guardar_producto(self):
        if not self.validar():
            return
        self.guardar_btn.setEnabled(False)
        try:
            codigo = self.codigo_edit.text().strip()
            nombre = self.nombre_edit.text().strip()
            depto = self.depto_cb.currentText()
            stock = float(self.stock_spin.value())
            unidad = self.unidad_cb.currentText()
            costo_text = self.costo_compra_edit.text() or "0"
            iva_text = self.iva_edit.text() or "0"
            gan_text = self.ganancia_edit.text() or "0"
            moneda = self.moneda_cb.currentText()
            fecha_cad = None
            try:
                if getattr(self, 'has_cad_cb', None) and self.has_cad_cb.isChecked():
                    fecha_cad = self.fecha_cad_edit.date().toString("yyyy-MM-dd")
                else:
                    fecha_cad = None
            except Exception:
                fecha_cad = None
            imagen = self.img_path

            rate = _get_bcv_rate()

            if moneda in ('$', 'usd', 'USD'):
                # Registro en USD: calculo directo, USD es la base
                r = calcular_desde_usd(costo_text, iva_text, gan_text, rate)
                precio_with_iva_usd = r.get('precio_with_iva_usd')
                
                # Referencia Bs al momento (opcional, para historial)
                if precio_with_iva_usd and rate:
                    ref_bs = calcular_precio_venta_actual(float(precio_with_iva_usd), rate)
                    precio_final_bs_store = float(ref_bs.get('precio_bs_actual')) if ref_bs.get('precio_bs_actual') else None
                else:
                    precio_final_bs_store = None
            else:
                # Registro en Bs: calculamos y convertimos a USD para guardar como BASE PERMANENTE
                try:
                    r = calcular_desde_bs(costo_text, iva_text, gan_text, rate)
                except ValueError as ve:
                    QMessageBox.warning(self, "Tasa requerida", str(ve))
                    self.guardar_btn.setEnabled(True)
                    return
                
                precio_with_iva_usd = r.get('precio_with_iva_usd')  # ← BASE PERMANENTE EN USD
                # Guardamos también referencia Bs del momento (para historial)
                precio_final_bs_store = float(r.get('precio_with_iva_bs')) if r.get('precio_with_iva_bs') else None

            precio_store_usd = float(precio_with_iva_usd) if precio_with_iva_usd is not None else 0.0
            bcv_tasa_store = float(rate) if rate is not None else None

            newid = self.db.insert_producto(
                codigo=codigo,
                nombre=nombre,
                descripcion="",
                departamento=depto,
                stock=float(stock),
                costo_compra=float(Decimal(str(costo_text))),
                imagen=imagen,
                fecha_caducidad=fecha_cad,
                iva=float(Decimal(str(iva_text))),
                ganancia=float(Decimal(str(gan_text))),
                unidad=unidad,
                moneda=moneda,  # Guardamos moneda original para referencia
                precio_final=float(precio_store_usd),        # ← USD BASE PERMANENTE
                precio_final_bs=precio_final_bs_store,       # ← Referencia histórica (opcional)
                bcv_tasa=bcv_tasa_store
            )

            if DEBUG:
                try:
                    inserted = self.db.fetchone("SELECT * FROM productos WHERE id = ?", (newid,))
                    print("DEBUG: inserted product row:", inserted)
                except Exception:
                    pass

            QTimer.singleShot(0, self.cargar_tabla)
            QMessageBox.information(self, "Guardado", 
                f"Producto guardado correctamente.\\n"
                f"Precio base: {format_usd_minimal(Decimal(str(precio_store_usd)))}\\n"
                f"Este precio en $ no cambiará con la tasa BCV.")
            self.limpiar_form()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {ex}")
        finally:
            self.guardar_btn.setEnabled(True)
            try:
                from modules.notification import NotificationManager
                QTimer.singleShot(0, lambda: NotificationManager.instance(parent=self.parent() if hasattr(self, "parent") else None).evaluate_and_show(self.db))
            except Exception:
                pass

    def limpiar_form(self):
        self.codigo_edit.setText(self._generar_codigo())
        self.nombre_edit.clear()
        self.depto_cb.setCurrentIndex(0)
        self.stock_spin.setValue(0.0)
        self.costo_compra_edit.setText("0.00")
        self.iva_edit.setText("16")
        self.ganancia_edit.setText("30")
        self.moneda_cb.setCurrentIndex(0)
        self.unidad_cb.setCurrentIndex(0)
        try:
            self.fecha_cad_edit.setDate(QDate.currentDate())
            if getattr(self, 'has_cad_cb', None):
                self.has_cad_cb.setChecked(True)
                self.fecha_cad_edit.setEnabled(True)
        except Exception:
            pass
        self.img_path = None
        self.preview.set_pixmap(None)
        self._refresh_bcv_display()

    def cargar_tabla(self):
        try:
            rows = self.db.listar_productos() or []
            rate = _get_bcv_rate()

            self.table.setSortingEnabled(False)
            self.table.clearContents()
            self.table.setRowCount(0)

            for r in rows:
                nombre_raw = r.get('nombre')
                if not nombre_raw or not str(nombre_raw).strip():
                    continue

                row = self.table.rowCount()
                self.table.insertRow(row)

                pid = r.get('id', '') or ''
                codigo = r.get('codigo', '') or ''
                nombre = r.get('nombre', '') or ''
                departamento = r.get('departamento', '') or ''

                stock_raw = r.get('stock', 0.0) or 0.0
                try:
                    stock = float(stock_raw)
                except Exception:
                    stock = 0.0
                unidad = (r.get('unidad') or 'und').strip().lower()
                unidad_label = 'Unid' if unidad == 'und' else unidad
                try:
                    if unidad_label.lower() == 'unid' and float(stock).is_integer():
                        stock_str = f"{int(round(float(stock)))} {unidad_label}"
                    else:
                        stock_str = f"{float(stock):,.3f} {unidad_label}"
                except Exception:
                    stock_str = f"{stock} {unidad_label}"

                costo = r.get('costo_compra') or r.get('costo') or 0.0
                fecha_cad = r.get('fecha_caducidad') or ''

                # === NUEVA LÓGICA: USD es la moneda base, Bs se calcula dinámicamente ===
                precio_usd_base = r.get('precio_final')  # Este es el precio PERMANENTE en USD
                
                # Calcular precio en Bs usando la tasa ACTUAL (siempre actualizado)
                precio_bs_actual = None
                if precio_usd_base and rate:
                    ref = calcular_precio_venta_actual(float(precio_usd_base), rate)
                    precio_bs_actual = ref.get('precio_bs_actual')
                
                # Formatear USD (moneda base - siempre mostrar con 4 decimales para precisión)
                try:
                    usd_val = Decimal(str(precio_usd_base)) if precio_usd_base else Decimal('0')
                    usd_display = f"{float(usd_val):,.4f} $"
                except:
                    usd_display = "-- $"
                
                # Formatear Bs (calculado dinámicamente con tasa actual)
                if precio_bs_actual:
                    bs_display = f"{float(precio_bs_actual):,.2f} Bs"
                else:
                    bs_display = "-- Bs"
                # === FIN NUEVA LÓGICA ===

                values = [
                    pid, codigo, nombre, departamento, stock_str, unidad_label,
                    f"{float(costo):.2f}", 
                    f"{float(r.get('iva') or 0.0):.2f}", 
                    f"{float(r.get('ganancia') or 0.0):.2f}",
                    usd_display,      # ← Precio Base ($) - permanente
                    bs_display       # ← Precio Hoy (Bs) - calculado con tasa actual
                ]

                for col in range(self.table.columnCount()):
                    val = values[col] if col < len(values) else ""
                    item = QTableWidgetItem(str(val))
                    if col == 0:
                        try:
                            item.setData(Qt.UserRole, int(pid))
                        except Exception:
                            item.setData(Qt.UserRole, pid)
                        item.setTextAlignment(Qt.AlignCenter)
                    elif col in (9, 10):  # Columnas de precios
                        item.setTextAlignment(Qt.AlignRight)
                    else:
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)

                actions_col = self.table.columnCount() - 1
                edit_btn = QPushButton("Editar")
                edit_btn.clicked.connect(self._make_edit_handler(pid))
                edit_btn.setCursor(Qt.PointingHandCursor)
                self.table.setCellWidget(row, actions_col, edit_btn)

            try:
                self.table.resizeRowsToContents()
            except Exception:
                pass
            try:
                self.table.setSortingEnabled(True)
                self.table.sortItems(0, Qt.DescendingOrder)
            except Exception:
                pass

            # capture snapshot after loading table
            try:
                self._capture_snapshot()
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar tabla: {e}")

    def _make_edit_handler(self, pid):
        def handler():
            self._open_detail_for_id(pid)
        return handler

    def _on_table_double_clicked(self, row, col):
        try:
            id_item = self.table.item(row, 0)
            if not id_item:
                QMessageBox.warning(self, "Seleccionar", "No se pudo obtener el ID del producto.")
                return
            pid = id_item.text() if id_item else None
            self._open_detail_for_id(pid)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir detalle del producto: {e}")

    def _open_detail_for_id(self, pid):
        dlg = ProductDetailDialog(self, db=self.db, product_id=pid)
        dlg.exec_()
        QTimer.singleShot(50, self.cargar_tabla)

    # ---------------- Snapshot / Archiving helpers ----------------
    def _capture_snapshot(self):
        try:
            headers = []
            for c in range(self.table.columnCount()):
                hi = self.table.horizontalHeaderItem(c)
                headers.append(hi.text() if hi else f"Col{c}")
            rows = []
            for r in range(self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it:
                        row.append(it.text())
                    else:
                        w = self.table.cellWidget(r, c)
                        if w is not None:
                            try:
                                val = getattr(w, "text", lambda: "")()
                                row.append(str(val))
                            except Exception:
                                try:
                                    row.append(str(w.text()))
                                except Exception:
                                    row.append("")
                        else:
                            row.append("")
                rows.append(row)
            self._last_snapshot = {"headers": headers, "rows": rows}
        except Exception:
            self._last_snapshot = {"headers": [], "rows": []}

    def _snapshot_has_data(self):
        try:
            return bool(self._last_snapshot.get("rows"))
        except Exception:
            return False

    def _get_archive_path_for_date(self, date_str: str) -> str:
        _ensure_dir(_ARCHIVE_BASE)
        return os.path.join(_ARCHIVE_BASE, f"{date_str}.pdf")

    def _save_snapshot_now(self, date: str = None) -> dict:
        """
        Export the current snapshot to PDF for given date (YYYY-MM-DD) or today if None.
        Uses atomic move to avoid partial files. Returns exporter result dict or {} on failure.
        Implements change detection: if snapshot hash equals last saved, skip write.
        """
        try:
            target_date = date or _date_str()
            target_path = self._get_archive_path_for_date(target_date)

            # compute hash and skip if same for today's file
            curr_hash = _snapshot_hash(self._last_snapshot)
            if target_date == _date_str() and self._last_saved_hash and curr_hash == self._last_saved_hash:
                return {"type": "skipped", "path": target_path}

            # build temporary QTableWidget to pass to exporter
            from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
            tmp_table = QTableWidget()
            headers = self._last_snapshot.get("headers", [])
            rows = self._last_snapshot.get("rows", [])
            tmp_table.setColumnCount(len(headers))
            tmp_table.setHorizontalHeaderLabels(headers)
            tmp_table.setRowCount(0)
            for r in rows:
                rowidx = tmp_table.rowCount()
                tmp_table.insertRow(rowidx)
                for c, val in enumerate(r):
                    item = QTableWidgetItem(str(val))
                    tmp_table.setItem(rowidx, c, item)

            # export to temporary file path
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                res = export_qtablewidget_to_pdf(tmp_table, tmp_path, title=f"Registro de Productos ({target_date})", company_info={"name": "Minimarket ChiChi N-K, C.A", "tax_id": "J-5099900-7"}, orientation="landscape")
                # atomic move
                _atomic_write(tmp_path, target_path)
                # update last saved hash & date
                if target_date == _date_str():
                    self._last_saved_hash = curr_hash
                    self._last_saved_date = target_date
                return {"type": res.get("type", "pdf"), "path": target_path}
            except Exception:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                return {}
        except Exception:
            return {}

    def _on_autosave_tick(self):
        """
        Periodic autosave: capture snapshot, and save if changed.
        """
        try:
            self._capture_snapshot()
            # if no data at all, skip saving
            if not self._snapshot_has_data():
                return
            self._save_snapshot_now()
        except Exception:
            pass

    def _on_date_check_tick(self):
        """
        Detect day rollover. When day changes:
         - attempt to save previous day's snapshot if not already saved,
         - clear view so UI starts visually blank for new day,
         - reset last_saved_hash so first save of new day will persist.
        """
        try:
            today = _date_str()
            if today != self._last_saved_date:
                # attempt to save snapshot for yesterday using last_snapshot (if any)
                yesterday = self._last_saved_date
                if yesterday:
                    # if file doesn't exist for yesterday, write it using the snapshot we have (which might be from yesterday)
                    y_path = self._get_archive_path_for_date(yesterday)
                    if not os.path.exists(y_path) and self._last_snapshot:
                        # perform save for yesterday date
                        try:
                            # temporarily save using current snapshot but label as yesterday
                            self._save_snapshot_now(date=yesterday)
                        except Exception:
                            pass
                # clear table view so UI appears blank for new day (doesn't delete DB)
                try:
                    self.table.setRowCount(0)
                except Exception:
                    pass
                # reset tracking
                self._last_saved_hash = None
                self._last_saved_date = today
                # capture empty snapshot
                self._capture_snapshot()
        except Exception:
            pass

    def closeEvent(self, ev):
        # final save before closing
        try:
            self._capture_snapshot()
            if self._snapshot_has_data():
                self._save_snapshot_now()
        except Exception:
            pass
        # stop timers
        try:
            if self._autosave_timer.isActive():
                self._autosave_timer.stop()
            if self._date_check_timer.isActive():
                self._date_check_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)

