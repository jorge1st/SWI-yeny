from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QDateEdit, QWidget,
    QCheckBox
)
from PyQt5.QtCore import Qt, QDate
import datetime
from decimal import Decimal
from db_manager import DBManager
from modules.pricing import calcular_desde_usd, calcular_desde_bs, format_usd_minimal

class ProductDetailDialog(QDialog):
    def __init__(self, parent=None, db=None, product_id=None, product_dict=None):
        super().__init__(parent)
        self.db = db if db is not None else DBManager()
        self.product_id = int(product_id) if product_id is not None and str(product_id).isdigit() else product_id
        self.product = product_dict or {}
        self.setWindowTitle("Detalle de Producto")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(560), scale_px(480))
        except Exception:
            self.resize(560, 480)
        self._build_ui()
        if self.product_id and not self.product:
            self._load_from_db()
        elif self.product:
            self._fill_fields(self.product)

    def _build_ui(self):
        main = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(6,6,6,6)

        grid.addWidget(QLabel("ID:"),0,0)
        self.id_lbl = QLabel(str(self.product.get('id') if self.product else (self.product_id or '')))
        grid.addWidget(self.id_lbl,0,1)

        grid.addWidget(QLabel("Código:"),0,2)
        self.codigo_edit = QLineEdit(self.product.get('codigo','') if self.product else "")
        self.codigo_edit.setReadOnly(True)
        grid.addWidget(self.codigo_edit,0,3)

        grid.addWidget(QLabel("Nombre:"),1,0)
        self.nombre_edit = QLineEdit(self.product.get('nombre','') if self.product else "")
        grid.addWidget(self.nombre_edit,1,1,1,3)

        grid.addWidget(QLabel("Departamento:"),2,0)
        self.depto_cb = QComboBox()
        for d in ["Productos de Limpieza", "Confiteria", "Lacteos", "Aseo Personal", "Vivieres", "Bebidas", "Farmacia", "Bisuteria", "Ferreteria"]:
            self.depto_cb.addItem(d)
        grid.addWidget(self.depto_cb,2,1)

        grid.addWidget(QLabel("Stock:"),2,2)
        self.stock_edit = QLineEdit(str(self.product.get('stock',0)) if self.product else "0")
        self.unidad_cb = QComboBox(); self.unidad_cb.addItems(["und","kg","Metro"])
        s_w = QWidget(); s_l = QHBoxLayout(s_w); s_l.setContentsMargins(0,0,0,0); s_l.addWidget(self.stock_edit); s_l.addWidget(self.unidad_cb)
        grid.addWidget(s_w,2,3)

        grid.addWidget(QLabel("Costo de compra:"),3,0)
        self.costo_edit = QLineEdit(str(self.product.get('costo_compra', self.product.get('costo',0.0))) if self.product else "0.00")
        grid.addWidget(self.costo_edit,3,1)

        grid.addWidget(QLabel("IVA (%):"),3,2)
        self.iva_edit = QLineEdit(str(self.product.get('iva',0)) if self.product else "0")
        grid.addWidget(self.iva_edit,3,3)
        grid.addWidget(QLabel("Ganancia (%):"),4,0)
        self.ganancia_edit = QLineEdit(str(self.product.get('ganancia',0)) if self.product else "0")
        grid.addWidget(self.ganancia_edit,4,1)

        grid.addWidget(QLabel("Moneda:"),4,2)
        self.moneda_cb = QComboBox(); self.moneda_cb.addItems(["$","Bs"]); grid.addWidget(self.moneda_cb,4,3)

        grid.addWidget(QLabel("Fecha de caducidad:"),5,0)
        self.has_cad_cb = QCheckBox("Tiene fecha de caducidad")
        self.has_cad_cb.setChecked(True)
        self.fecha_cad_edit = QDateEdit()
        self.fecha_cad_edit.setCalendarPopup(True)
        self.fecha_cad_edit.setDisplayFormat("yyyy-MM-dd")
        self.fecha_cad_edit.setDate(QDate.currentDate())
        self.fecha_cad_edit.setEnabled(True)
        self.has_cad_cb.toggled.connect(self.fecha_cad_edit.setEnabled)
        cad_w = QWidget(); cad_l = QHBoxLayout(cad_w); cad_l.setContentsMargins(0,0,0,0); cad_l.addWidget(self.has_cad_cb); cad_l.addWidget(self.fecha_cad_edit)
        grid.addWidget(cad_w,5,1)

        grid.addWidget(QLabel("Imagen:"),5,2)
        self.imagen_edit = QLineEdit(self.product.get('imagen','') if self.product else "")
        self.img_btn = QPushButton("Seleccionar imagen"); self.img_btn.clicked.connect(self._choose_image)
        img_w = QWidget(); img_l = QHBoxLayout(img_w); img_l.setContentsMargins(0,0,0,0); img_l.addWidget(self.imagen_edit); img_l.addWidget(self.img_btn)
        grid.addWidget(img_w,5,3)

        main.addLayout(grid)

        # "Registrar Entrada" feature removed per user request
        # Entries should now be handled from the Entradas module only


        row = QHBoxLayout(); row.addStretch()
        self.delete_btn = QPushButton("Eliminar"); self.delete_btn.setStyleSheet("background:#E25555; color:white;"); self.delete_btn.clicked.connect(self._on_delete)
        self.save_btn = QPushButton("Guardar"); self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("Cerrar"); self.cancel_btn.clicked.connect(self.reject)
        row.addWidget(self.delete_btn); row.addWidget(self.save_btn); row.addWidget(self.cancel_btn)
        main.addLayout(row)

    def _load_from_db(self):
        try:
            rows = self.db.fetchall("SELECT * FROM productos WHERE id = ?", (self.product_id,)) or []
            if rows:
                self.product = rows[0]; self._fill_fields(self.product); self.id_lbl.setText(str(self.product.get('id','')))
            else:
                QMessageBox.warning(self, "No encontrado", "Producto no encontrado."); self.reject()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar producto: {e}"); self.reject()

    def _fill_fields(self, p: dict):
        self.product_id = p.get('id') or self.product_id
        self.id_lbl.setText(str(self.product_id or ""))
        self.codigo_edit.setText(str(p.get('codigo','') or ''))
        self.nombre_edit.setText(str(p.get('nombre','') or ''))
        idx = self.depto_cb.findText(p.get('departamento','') or ''); 
        if idx >= 0: self.depto_cb.setCurrentIndex(idx)
        stock_val = p.get('stock',0) or 0
        try:
            stock_display = str(int(stock_val)) if float(stock_val).is_integer() else f"{float(stock_val):,.3f}"
        except Exception:
            stock_display = str(stock_val)
        self.stock_edit.setText(stock_display)
        unidad = p.get('unidad','und') or 'und'; uidx = self.unidad_cb.findText(unidad)
        if uidx >= 0: self.unidad_cb.setCurrentIndex(uidx)
        self.costo_edit.setText(str(p.get('costo_compra', p.get('costo',0.0)) or 0.0))
        self.iva_edit.setText(str(p.get('iva',0) or 0)); self.ganancia_edit.setText(str(p.get('ganancia',0) or 0))
        midx = self.moneda_cb.findText(p.get('moneda','$') or '$'); 
        if midx >= 0: self.moneda_cb.setCurrentIndex(midx)
        fecha = p.get('fecha_caducidad') or ''
        try:
            if fecha:
                qd = QDate.fromString(str(fecha)[:10], 'yyyy-MM-dd')
                if qd.isValid():
                    self.fecha_cad_edit.setDate(qd)
                    self.has_cad_cb.setChecked(True)
                    self.fecha_cad_edit.setEnabled(True)
                else:
                    self.fecha_cad_edit.setDate(QDate.currentDate())
                    self.has_cad_cb.setChecked(False)
                    self.fecha_cad_edit.setEnabled(False)
            else:
                self.fecha_cad_edit.setDate(QDate.currentDate())
                self.has_cad_cb.setChecked(False)
                self.fecha_cad_edit.setEnabled(False)
        except Exception:
            try:
                self.fecha_cad_edit.setDate(QDate.currentDate())
                self.has_cad_cb.setChecked(False)
                self.fecha_cad_edit.setEnabled(False)
            except Exception:
                pass
        self.imagen_edit.setText(str(p.get('imagen','') or ''))

    def _choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.imagen_edit.setText(path)

    def _validate(self):
        if not self.nombre_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre es obligatorio."); return False
        try:
            Decimal(str(self.costo_edit.text() or "0"))
        except Exception:
            QMessageBox.warning(self, "Validación", "Costo inválido."); return False
        return True

    def _on_save(self):
        if not self._validate(): return
        data = {
            'id': self.product_id,
            'codigo': self.codigo_edit.text().strip(),
            'nombre': self.nombre_edit.text().strip(),
            'departamento': self.depto_cb.currentText(),
            'stock': float(str(self.stock_edit.text() or "0").replace(",", ".")),
            'unidad': self.unidad_cb.currentText(),
            'costo_compra': float(str(self.costo_edit.text() or "0").replace(",", ".")),
            'iva': float(str(self.iva_edit.text() or "0").replace(",", ".")),
            'ganancia': float(str(self.ganancia_edit.text() or "0").replace(",", ".")),
            'moneda': self.moneda_cb.currentText(),
            'fecha_caducidad': (self.fecha_cad_edit.date().toString("yyyy-MM-dd") if getattr(self, "has_cad_cb", None) and self.has_cad_cb.isChecked() else None),
            'imagen': self.imagen_edit.text().strip() or None
        }

        try:
            from main import get_current_bcv_rate
            rate, _ = get_current_bcv_rate()
        except Exception:
            rate = None

        moneda = data['moneda']
        if moneda in ('$', 'usd', 'USD'):
            # calcular_desde_usd now returns precio_with_iva_usd and precio_with_iva_bs
            res = calcular_desde_usd(data['costo_compra'], data['iva'], data['ganancia'], rate)
            precio_with_iva_usd = res.get('precio_with_iva_usd'); precio_with_iva_bs = res.get('precio_with_iva_bs'); bcv_tasa = res.get('bcv_tasa')
        else:
            res = calcular_desde_bs(data['costo_compra'], data['iva'], data['ganancia'], rate)
            precio_with_iva_bs = res.get('precio_with_iva_bs'); precio_with_iva_usd = res.get('precio_with_iva_usd'); bcv_tasa = res.get('bcv_tasa')
            if precio_with_iva_usd is None:
                QMessageBox.warning(self, "Tasa necesaria", "No hay tasa BCV disponible. Para ingresar precios en Bs el sistema necesita la tasa para calcular la referencia en $."); return

        try:
            if hasattr(self.db, "update_producto"):
                data_with_price = dict(data)
                data_with_price['precio_final'] = float(precio_with_iva_usd) if precio_with_iva_usd is not None else 0.0
                data_with_price['precio_final_bs'] = float(precio_with_iva_bs) if precio_with_iva_bs is not None else None
                data_with_price['bcv_tasa'] = float(bcv_tasa) if bcv_tasa is not None else None
                self.db.update_producto(data['id'], data_with_price)
            else:
                cur = self.db.conn.cursor()
                cur.execute("""
                    UPDATE productos SET
                        codigo=?, nombre=?, departamento=?, stock=?, costo_compra=?,
                        iva=?, ganancia=?, unidad=?, moneda=?, fecha_caducidad=?, imagen=?,
                        precio_final=?, precio_final_bs=?, bcv_tasa=?
                    WHERE id = ?
                """, (
                    data['codigo'], data['nombre'], data['departamento'], data['stock'],
                    data['costo_compra'], data['iva'], data['ganancia'], data['unidad'], data['moneda'],
                    data['fecha_caducidad'], data['imagen'],
                    float(precio_with_iva_usd) if precio_with_iva_usd is not None else 0.0,
                    float(precio_with_iva_bs) if precio_with_iva_bs is not None else None,
                    float(bcv_tasa) if bcv_tasa is not None else None,
                    data['id']
                ))
                self.db.conn.commit()
            QMessageBox.information(self, "Guardado", "Producto actualizado correctamente.")
            self._after_change()
            self.accept()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {ex}")

    def _on_delete(self):
        if not self.product_id:
            QMessageBox.warning(self, "Eliminar", "Producto sin id no puede ser eliminado."); return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar este producto? Esta acción no se puede deshacer.", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            try:
                record = self.db.fetchall("SELECT * FROM productos WHERE id = ?", (self.product_id,)) or []
                record = record[0] if record else None
            except Exception:
                record = None

            if hasattr(self.db, "delete_producto"):
                try:
                    self.db.delete_producto(self.product_id)
                except TypeError:
                    self.db.delete_producto(id=self.product_id)
            else:
                cur = self.db.conn.cursor()
                cur.execute("DELETE FROM productos WHERE id = ?", (self.product_id,))
                self.db.conn.commit()

            QMessageBox.information(self, "Eliminado", "Producto eliminado correctamente.")
            self._after_change(deleted=True, deleted_row=record)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo eliminar: {e}")

    # _on_register_entrada removed per user request; entradas are handled via the Entradas module

    def _after_change(self, deleted=False, deleted_row=None):
        parent = self.parent()
        try:
            for name in ("cargar_tabla", "load_all_products", "refresh_totals", "cargar_tabla_productos"):
                fn = getattr(parent, name, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
            if deleted and deleted_row and hasattr(parent, "_on_child_deleted") and callable(parent._on_child_deleted):
                try:
                    parent._on_child_deleted(deleted_row)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            w = parent
            while w is not None:
                if hasattr(w, "_update_expiry_badge") and callable(getattr(w, "_update_expiry_badge")):
                    try:
                        w._update_expiry_badge()
                    except Exception:
                        pass
                    break
                try:
                    w = w.parent()
                except Exception:
                    break
        except Exception:
            pass

