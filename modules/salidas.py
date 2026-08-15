# modules/salidas.py
"""
Compatibilidad / módulo 'salidas' que expone SalidasWindow.
Internamente contiene el VentasIntegradoWidget (POS) — se mantiene la funcionalidad
de ventas integradas pero exponemos SalidasWindow para mantener compatibilidad
con el Dashboard antiguo.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QMessageBox, QFrame, QHeaderView, QListWidget, QListWidgetItem, QInputDialog,
    QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from decimal import Decimal, ROUND_HALF_UP
import datetime
import uuid

from db_manager import DBManager
from modules.pricing import calcular_precio_venta_actual

# Payment method constants
_PAYMENT_METHODS = [
    ("Efectivo", "efectivo"),
    ("Transferencia", "transferencia"),
    ("Biopago", "biopago"),
    ("Pago Móvil", "pago_movil"),
    ("Punto (POS)", "punto")
]

DEC_2 = Decimal("0.01")


def D(v):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


class VentasIntegradoWidget(QWidget):
    """
    Widget POS (integrado). Mantengo la implementación original prácticamente
    igual a la que enviaste; este widget emite venta_completada cuando finaliza
    la salida.
    """
    venta_completada = pyqtSignal(object)   # dict with sale info
    volver_solicitado = pyqtSignal()        # request to return to dashboard view

    def __init__(self, db: DBManager = None, parent=None):
        super().__init__(parent)
        self.db = db if db is not None else DBManager()
        self.cart = []  # list of dicts: {producto_id, codigo, nombre, qty, precio_usd, precio_bs_unit}
        self.payments = []  # list of dicts: {method_key, method_label, amount}
        self._build_ui()
        QTimer.singleShot(0, self._load_products_into_search)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setObjectName("ventas_widget")
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Sistema de Salidas (Punto de Venta)")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        btn_back = QPushButton("← Volver")
        btn_back.clicked.connect(self._on_volver)
        header.addWidget(btn_back)
        main.addLayout(header)

        # Top area: product search / add to cart
        top = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(6)

        # Search input (free text) + product combo (filled with "Nombre (codigo)")
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto por nombre o código...")
        self.search_input.returnPressed.connect(self._on_search_enter)
        self.search_btn = QPushButton("Buscar")
        self.search_btn.clicked.connect(self._on_search_enter)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)
        left.addLayout(search_row)

        self.product_combo = QComboBox()
        self.product_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        left.addWidget(self.product_combo)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Cantidad:"))
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setRange(0.001, 1_000_000)
        self.qty_spin.setDecimals(3)
        self.qty_spin.setValue(1.0)
        qty_row.addWidget(self.qty_spin)
        self.add_btn = QPushButton("Agregar al carrito")
        self.add_btn.clicked.connect(self._on_add_to_cart)
        qty_row.addWidget(self.add_btn)
        left.addLayout(qty_row)

        top.addLayout(left, 1)

        # Cart table on the right
        right = QVBoxLayout()
        right.addWidget(QLabel("Carrito:"))
        self.cart_table = QTableWidget(0, 6)
        self.cart_table.setHorizontalHeaderLabels(["ID", "Código", "Nombre", "Cantidad", "Precio Bs (u)", "Subtotal Bs"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        right.addWidget(self.cart_table)

        # cart actions
        cart_actions = QHBoxLayout()
        self.remove_item_btn = QPushButton("Eliminar seleccionado")
        self.remove_item_btn.clicked.connect(self._remove_selected_cart_item)
        cart_actions.addWidget(self.remove_item_btn)
        self.clear_cart_btn = QPushButton("Limpiar carrito")
        self.clear_cart_btn.clicked.connect(self._clear_cart)
        cart_actions.addWidget(self.clear_cart_btn)
        cart_actions.addStretch()
        right.addLayout(cart_actions)

        top.addLayout(right, 2)

        main.addLayout(top)

        # Totals & payments area
        mid = QHBoxLayout()

        # Totals frame
        totals_frame = QFrame()
        totals_layout = QVBoxLayout(totals_frame)
        totals_layout.setContentsMargins(8, 8, 8, 8)
        totals_layout.setSpacing(6)
        totals_layout.addWidget(QLabel("Totales"))

        self.lbl_subtotal = QLabel("Subtotal: -- Bs")
        self.lbl_total = QLabel("Total a pagar: -- Bs")
        self.lbl_total.setObjectName("lbl_total")
        self.lbl_balance = QLabel("Saldo pendiente: -- Bs")
        totals_layout.addWidget(self.lbl_subtotal)
        totals_layout.addWidget(self.lbl_total)
        totals_layout.addWidget(self.lbl_balance)

        mid.addWidget(totals_frame, 1)

        # Payments frame
        payments_frame = QFrame()
        payments_layout = QVBoxLayout(payments_frame)
        payments_layout.setContentsMargins(8, 8, 8, 8)
        payments_layout.setSpacing(6)
        payments_layout.addWidget(QLabel("Pagos"))

        pay_row = QHBoxLayout()
        self.pay_method_cb = QComboBox()
        for label, key in _PAYMENT_METHODS:
            self.pay_method_cb.addItem(label, key)
        pay_row.addWidget(self.pay_method_cb)
        self.pay_amount_input = QDoubleSpinBox()
        self.pay_amount_input.setPrefix("")
        self.pay_amount_input.setRange(0.0, 1_000_000_000.0)
        self.pay_amount_input.setDecimals(2)
        pay_row.addWidget(self.pay_amount_input)
        add_pay_btn = QPushButton("Agregar pago")
        add_pay_btn.clicked.connect(self._add_payment)
        pay_row.addWidget(add_pay_btn)
        payments_layout.addLayout(pay_row)

        self.payments_list = QListWidget()
        payments_layout.addWidget(self.payments_list)

        pay_actions = QHBoxLayout()
        self.remove_payment_btn = QPushButton("Eliminar pago")
        self.remove_payment_btn.clicked.connect(self._remove_selected_payment)
        pay_actions.addWidget(self.remove_payment_btn)
        self.clear_payments_btn = QPushButton("Limpiar pagos")
        self.clear_payments_btn.clicked.connect(self._clear_payments)
        pay_actions.addWidget(self.clear_payments_btn)
        payments_layout.addLayout(pay_actions)

        mid.addWidget(payments_frame, 1)

        # Finalize actions
        actions_frame = QFrame()
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(8, 8, 8, 8)
        actions_layout.addStretch()
        self.finalize_btn = QPushButton("Finalizar Salida")
        self.finalize_btn.setObjectName("finalize_btn")
        self.finalize_btn.clicked.connect(self._on_finalize_sale)
        actions_layout.addWidget(self.finalize_btn)

        self.charge_btn = QPushButton("Cargar pago exacto (Efectivo)")
        self.charge_btn.clicked.connect(self._quick_cash)
        actions_layout.addWidget(self.charge_btn)

        self.receipt_btn = QPushButton("Generar número de registro (ver)")
        self.receipt_btn.clicked.connect(self._show_invoice_preview)
        actions_layout.addWidget(self.receipt_btn)

        mid.addWidget(actions_frame, 0)

        main.addLayout(mid)

        # helper: live totals update timer
        self._totals_timer = QTimer(self)
        self._totals_timer.setInterval(300)
        self._totals_timer.timeout.connect(self._recalculate_totals)
        self._totals_timer.start()

    # ---------------- Product loading / search ----------------
    def _load_products_into_search(self):
        try:
            self.product_combo.clear()
            prods = self.db.listar_productos() or []
            # Display label "Nombre (codigo) - stock"
            for p in prods:
                lbl = f"{p.get('nombre') or 'Sin nombre'} ({p.get('codigo') or 'N/A'})"
                pid = p.get('id')
                self.product_combo.addItem(lbl, pid)
        except Exception:
            pass

    def _on_search_enter(self):
        query = (self.search_input.text() or "").strip().lower()
        if not query:
            self._load_products_into_search()
            return
        # Simple local filter
        try:
            self.product_combo.clear()
            prods = self.db.listar_productos() or []
            for p in prods:
                name = (p.get('nombre') or '').lower()
                code = (p.get('codigo') or '').lower()
                if query in name or query in code:
                    lbl = f"{p.get('nombre') or 'Sin nombre'} ({p.get('codigo') or 'N/A'})"
                    self.product_combo.addItem(lbl, p.get('id'))
            if self.product_combo.count() == 0:
                QMessageBox.information(self, "Buscar", "No se encontraron productos coincidentes.")
                self._load_products_into_search()
        except Exception as e:
            QMessageBox.warning(self, "Buscar", f"Error al buscar: {e}")
            self._load_products_into_search()

    # ---------------- Cart operations ----------------
    def _on_add_to_cart(self):
        pid = self.product_combo.currentData()
        if pid is None:
            QMessageBox.warning(self, "Carrito", "Seleccione un producto.")
            return
        try:
            prod = self.db.fetchone("SELECT * FROM productos WHERE id = ?", (pid,))
            if not prod:
                QMessageBox.warning(self, "Carrito", "Producto no encontrado.")
                return
            qty = float(self.qty_spin.value())
            if qty <= 0:
                QMessageBox.warning(self, "Carrito", "Ingrese una cantidad mayor a 0.")
                return

            # compute unit price in Bs using current BCV rate
            try:
                from main import get_current_bcv_rate
                rate, _ = get_current_bcv_rate()
            except Exception:
                rate = None
            precio_usd = prod.get('precio_final') or 0.0
            precio_bs_unit = None
            if precio_usd and rate:
                ref = calcular_precio_venta_actual(float(precio_usd), rate)
                precio_bs_unit = ref.get('precio_bs_actual') or 0.0
            else:
                precio_bs_unit = 0.0

            # if item already in cart, increment quantity
            found = None
            for it in self.cart:
                if int(it.get('producto_id')) == int(pid):
                    found = it
                    break
            if found:
                found['qty'] = float(found.get('qty', 0)) + qty
                found['precio_bs_unit'] = float(precio_bs_unit)
            else:
                self.cart.append({
                    'producto_id': int(pid),
                    'codigo': prod.get('codigo'),
                    'nombre': prod.get('nombre'),
                    'qty': float(qty),
                    'precio_usd': float(precio_usd) if precio_usd is not None else 0.0,
                    'precio_bs_unit': float(precio_bs_unit)
                })
            self._refresh_cart_table()
        except Exception as e:
            QMessageBox.critical(self, "Carrito", f"No se pudo agregar: {e}")

    def _refresh_cart_table(self):
        try:
            self.cart_table.setRowCount(0)
            for it in self.cart:
                row = self.cart_table.rowCount()
                self.cart_table.insertRow(row)
                self.cart_table.setItem(row, 0, QTableWidgetItem(str(it.get('producto_id'))))
                self.cart_table.setItem(row, 1, QTableWidgetItem(str(it.get('codigo') or '')))
                self.cart_table.setItem(row, 2, QTableWidgetItem(str(it.get('nombre') or '')))
                self.cart_table.setItem(row, 3, QTableWidgetItem(f"{float(it.get('qty')):,.3f}"))
                self.cart_table.setItem(row, 4, QTableWidgetItem(f"{float(it.get('precio_bs_unit')):,.2f}"))
                subtotal = float(it.get('qty')) * float(it.get('precio_bs_unit') or 0.0)
                self.cart_table.setItem(row, 5, QTableWidgetItem(f"{subtotal:,.2f}"))
            try:
                self.cart_table.resizeRowsToContents()
            except Exception:
                pass
        except Exception:
            pass
        self._recalculate_totals()

    def _remove_selected_cart_item(self):
        try:
            r = self.cart_table.currentRow()
            if r < 0:
                return
            pid_item = self.cart_table.item(r, 0)
            if not pid_item:
                return
            pid = int(pid_item.text())
            self.cart = [c for c in self.cart if int(c.get('producto_id')) != int(pid)]
            self._refresh_cart_table()
        except Exception as e:
            QMessageBox.warning(self, "Carrito", f"Error al eliminar: {e}")

    def _clear_cart(self):
        self.cart = []
        self._refresh_cart_table()

    # ---------------- Payments ----------------
    def _add_payment(self):
        try:
            method_label = self.pay_method_cb.currentText()
            method_key = self.pay_method_cb.currentData()
            amount = float(self.pay_amount_input.value())
            if amount <= 0:
                QMessageBox.warning(self, "Pago", "Ingrese un monto mayor a 0.")
                return
            self.payments.append({
                'method_key': method_key,
                'method_label': method_label,
                'amount': float(round(amount, 2))
            })
            self._refresh_payments_list()
            self.pay_amount_input.setValue(0.0)
        except Exception as e:
            QMessageBox.warning(self, "Pago", f"Error agregando pago: {e}")

    def _refresh_payments_list(self):
        self.payments_list.clear()
        for p in self.payments:
            it = QListWidgetItem(f"{p.get('method_label')}: {float(p.get('amount')):,.2f} Bs")
            it.setData(Qt.UserRole, p)
            self.payments_list.addItem(it)
        self._recalculate_totals()

    def _remove_selected_payment(self):
        try:
            it = self.payments_list.currentItem()
            if not it:
                return
            p = it.data(Qt.UserRole)
            if not p:
                return
            # remove first matching
            removed = False
            for i, pay in enumerate(self.payments):
                if pay.get('method_key') == p.get('method_key') and float(pay.get('amount')) == float(p.get('amount')):
                    del self.payments[i]
                    removed = True
                    break
            if removed:
                self._refresh_payments_list()
        except Exception as e:
            QMessageBox.warning(self, "Pago", f"Error eliminando pago: {e}")

    def _clear_payments(self):
        self.payments = []
        self._refresh_payments_list()

    def _quick_cash(self):
        """Agregar un pago en efectivo por el total restante (útil para caja)."""
        total = self._compute_total_bs()
        paid = self._compute_amount_paid()
        restante = float(round(total - paid, 2))
        if restante <= 0:
            QMessageBox.information(self, "Pago", "No hay saldo pendiente.")
            return
        # agregar pago en efectivo
        self.pay_method_cb.setCurrentIndex(0)
        self.pay_amount_input.setValue(restante)
        self._add_payment()

    # ---------------- Totals / helpers ----------------
    def _compute_subtotal_bs(self):
        s = Decimal("0")
        for it in self.cart:
            qty = D(it.get('qty') or 0)
            pu = D(it.get('precio_bs_unit') or 0)
            s += (qty * pu)
        return float(s.quantize(DEC_2, rounding=ROUND_HALF_UP))

    def _compute_total_bs(self):
        # In current model precio_bs_unit already contains IVA (calculated from precio_final which includes IVA).
        # So subtotal == total for our simplified POS. Keep hooks if you want to separate IVA later.
        return self._compute_subtotal_bs()

    def _compute_amount_paid(self):
        return float(sum(float(p.get('amount') or 0.0) for p in self.payments))

    def _recalculate_totals(self):
        subtotal = self._compute_subtotal_bs()
        total = subtotal
        paid = self._compute_amount_paid()
        balance = total - paid
        self.lbl_subtotal.setText(f"Subtotal: {subtotal:,.2f} Bs")
        self.lbl_total.setText(f"Total a pagar: {total:,.2f} Bs")
        if balance <= 0:
            self.lbl_balance.setText(f"Pagado. Cambio: {abs(balance):,.2f} Bs")
        else:
            self.lbl_balance.setText(f"Saldo pendiente: {balance:,.2f} Bs")

    # ---------------- Finalizar venta ----------------
    def _generate_invoice_number(self):
        # Simple invoice generator: YYYYMMDD-HHMMSS-UUID4(short)
        now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        uid = uuid.uuid4().hex[:6].upper()
        return f"R-{now}-{uid}"

    def _on_finalize_sale(self):
        if not self.cart:
            QMessageBox.warning(self, "Salida", "Carrito vacío.")
            return
        total = self._compute_total_bs()
        paid = self._compute_amount_paid()
        if paid < total:
            QMessageBox.warning(self, "Pago", f"El total pagado ({paid:,.2f} Bs) es menor al total ({total:,.2f} Bs).")
            return

        factura = self._generate_invoice_number()
        motivo = factura
        # Try to insert movimientos: for each cart item, call db.insert_movimiento("Salida", producto_id, cantidad, costo=precio_unit_bs, imagen=None, motivo=factura)
        successful_movs = []
        failed = False
        failed_msgs = []
        try:
            for it in self.cart:
                pid = int(it.get('producto_id'))
                qty = float(it.get('qty') or 0.0)
                precio_unit_bs = float(it.get('precio_bs_unit') or 0.0)
                # insert movimiento; DBManager will validate stock for 'Salida'
                try:
                    mov_id = self.db.insert_movimiento("Salida", pid, qty, costo=precio_unit_bs, imagen=None, motivo=motivo)
                    successful_movs.append({
                        'mov_id': mov_id,
                        'producto_id': pid,
                        'codigo': it.get('codigo'),
                        'nombre': it.get('nombre'),
                        'qty': qty,
                        'precio_unit_bs': precio_unit_bs,
                        'subtotal_bs': round(qty * precio_unit_bs, 2)
                    })
                except Exception as e:
                    failed = True
                    failed_msgs.append(str(e))
                    # stop further processing to avoid partial sales
                    break
            if failed:
                # rollback already attempted by DBManager.insert_movimiento on exception, but we must inform user
                QMessageBox.critical(self, "Salida", f"Error al registrar la salida: {failed_msgs[0]}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Salida", f"Error al procesar salida: {e}")
            return

        # Build sale summary
        sale_data = {
            'numero_factura': factura,
            'fecha': datetime.datetime.now().isoformat(timespec='seconds'),
            'productos': successful_movs,
            'totales': {
                'total_bs': round(total, 2),
                'pagado_bs': round(paid, 2),
                'cambio_bs': round(paid - total, 2)
            },
            'pagos': list(self.payments)
        }

        # Emit signal so dashboard can show notification / update totals
        try:
            self.venta_completada.emit(sale_data)
        except Exception:
            pass

        # Reset UI: clear cart and payments
        QMessageBox.information(self, "Salida", f"Salida registrada. Registro de salida: {factura}\nTotal: {total:,.2f} Bs")
        self.cart = []
        self.payments = []
        self._refresh_cart_table()
        self._refresh_payments_list()

    # ---------------- Utilities ----------------
    def _show_invoice_preview(self):
        # Show a simple dialog with invoice number preview and totals
        fact = self._generate_invoice_number()
        total = self._compute_total_bs()
        QMessageBox.information(self, "Registro de salida (previsualización)", f"Número de registro: {fact}\nTotal aproximado: {total:,.2f} Bs")

    def _on_cierre_diario(self):
        """Genera el cierre diario y guarda PDF en factura/cierres/."""
        try:
            from modules.cierre_diario import DialogoCierreDiario
            dlg = DialogoCierreDiario(self.db, parent=self, tipo='Salida', title='Salidas del día')
            # _guardar_pdf muestra el diálogo de guardado / notifica al usuario
            dlg._guardar_pdf()
        except Exception as e:
            QMessageBox.critical(self, "Cierre Diario", f"No se pudo generar cierre diario: {e}")

    def _on_volver(self):
        # ask user if there is unsaved cart
        if self.cart:
            msg = QMessageBox(self)
            msg.setWindowTitle("Volver")
            msg.setText("Hay un carrito con productos. ¿Desea cancelar la salida y volver?")
            btn_si = msg.addButton("Sí", QMessageBox.YesRole)
            btn_no = msg.addButton("No", QMessageBox.NoRole)
            msg.setDefaultButton(btn_no)
            msg.exec_()
            if msg.clickedButton() != btn_si:
                return
        # emit to dashboard to restore view
        try:
            self.volver_solicitado.emit()
        except Exception:
            pass


# ---------------- Compatibility wrapper ----------------
class SalidasWindow(QDialog):
    """
    Wrapper QDialog para compatibilidad con llamadas antiguas:
      from modules.salidas import SalidasWindow
    El wrapper contiene un VentasIntegradoWidget y reexpone la señal
    'venta_finalizada' (nombre esperado por Dashboard antiguo).
    """
    venta_finalizada = pyqtSignal(object)  # mantiene la API antigua

    def __init__(self, parent=None, db: DBManager = None):
        super().__init__(parent)
        self.setWindowTitle("Registro de Salidas - Punto de Venta")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(1000), scale_px(700))
        except Exception:
            self.resize(1000, 700)
        self._db = db if db is not None else DBManager()
        layout = QVBoxLayout(self)
        self.pos_widget = VentasIntegradoWidget(db=self._db, parent=self)
        layout.addWidget(self.pos_widget)
        try:
            self.pos_widget.set_mode('Salida')
        except Exception:
            pass

        # reemit sale signal under the old name
        self.pos_widget.venta_completada.connect(self._on_venta_completada)
        # optionally connect volver_solicitado to close dialog if desired
        self.pos_widget.volver_solicitado.connect(self._on_volver_requested)

    def _on_venta_completada(self, data):
        try:
            self.venta_finalizada.emit(data)
        except Exception:
            pass

    def _on_volver_requested(self):
        try:
            self.close()
        except Exception:
            pass


# For convenience, keep module exports explicit
__all__ = ["VentasIntegradoWidget", "SalidasWindow"]

