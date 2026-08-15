# modules/entradas.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QCompleter, QHBoxLayout,
    QDoubleSpinBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QWidget, QHeaderView, QSizePolicy, QFileDialog
)
from PyQt5.QtCore import Qt, QDate, QTimer
from db_manager import DBManager
import datetime

from modules.pdf_exporter import export_qtablewidget_to_pdf
from modules.daily_archiver import DailyArchiver

class EntradasWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setObjectName("entradas")
        except Exception:
            pass
        self.parent_widget = parent
        self.db = DBManager()
        self.setWindowTitle("Registro de Entradas")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(900), scale_px(560))
        except Exception:
            self.resize(900, 560)
        self._build_ui()

        # create archiver for entradas table
        self.archiver = DailyArchiver("entradas", self.table, title="Registro de Entradas")
        self.archiver.update_snapshot()
        self.archiver.start()

        QTimer.singleShot(0, self._populate_products)
        QTimer.singleShot(0, self.cargar_tabla)

    def _build_ui(self):
        main = QVBoxLayout(self)

        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Producto
        grid.addWidget(QLabel("Producto:"), 0, 0)
        self.product_cb = QComboBox()
        self.product_cb.setEditable(True)
        self.product_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # enable typing filter with completer
        self._product_completer = QCompleter(self.product_cb)
        self._product_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_cb.setCompleter(self._product_completer)
        grid.addWidget(self.product_cb, 0, 1, 1, 3)

        # Cantidad
        grid.addWidget(QLabel("Cantidad:"), 1, 0)
        self.cantidad_spin = QDoubleSpinBox()
        self.cantidad_spin.setDecimals(3)
        self.cantidad_spin.setRange(0.001, 1_000_000)
        self.cantidad_spin.setSingleStep(1)
        self.cantidad_spin.setValue(1)
        grid.addWidget(self.cantidad_spin, 1, 1)

        # Motivo
        grid.addWidget(QLabel("Motivo:"), 2, 0)
        self.motivo_edit = QLineEdit()
        self.motivo_edit.setPlaceholderText("Opcional: referencia, compra, ajuste...")
        grid.addWidget(self.motivo_edit, 2, 1, 1, 3)

        # Botón registrar
        btn_row = QWidget()
        btn_row_l = QHBoxLayout(btn_row)
        btn_row_l.setContentsMargins(0, 0, 0, 0)
        btn_row_l.addStretch()
        self.abrir_carrito_btn = QPushButton("Abrir Carrito de Entradas")
        self.abrir_carrito_btn.setObjectName("abrir_carrito_btn")
        self.abrir_carrito_btn.clicked.connect(self._abrir_carrito_compras)
        btn_row_l.addWidget(self.abrir_carrito_btn)
        self.registrar_btn = QPushButton("Registrar Entrada")
        self.registrar_btn.setObjectName("registrar_btn")
        self.registrar_btn.clicked.connect(self._on_registrar)
        btn_row_l.addWidget(self.registrar_btn)
        # Export PDF button
        self.export_pdf_btn = QPushButton("Exportar PDF")
        self.export_pdf_btn.setObjectName("export_pdf_btn")
        self.export_pdf_btn.clicked.connect(self._on_export_pdf)
        btn_row_l.addWidget(self.export_pdf_btn)
        grid.addWidget(btn_row, 3, 0, 1, 4)

        main.addLayout(grid)

        # Tabla de entradas recientes
        headers = ["ID", "Código", "Producto", "Cantidad", "Tipo", "Fecha", "Motivo", "Acciones"]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        main.addWidget(self.table, 1)

        # Close
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        main.addLayout(footer)

    def _populate_products(self):
        """
        Carga productos en el combo: etiqueta 'nombre (codigo)' con userdata=id
        También actualiza el modelo del completer para permitir filtrar escribiendo.
        """
        self.product_cb.clear()
        try:
            prods = self.db.listar_productos() or []
            prods = sorted(prods, key=lambda p: (p.get('nombre') or '').lower())
            labels = []
            for p in prods:
                name = p.get('nombre') or ''
                code = p.get('codigo') or ''
                label = f"{name} ({code})" if name else code
                pid = p.get('id')
                self.product_cb.addItem(label, pid)
                labels.append(label)
            # update completer model
            from PyQt5.QtCore import QStringListModel
            try:
                model = QStringListModel(labels, self._product_completer)
                self._product_completer.setModel(model)
            except Exception:
                # fallback: some PyQt versions accept list directly
                try:
                    self._product_completer.setModel(labels)
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.warning(self, "Productos", f"No se pudieron cargar productos: {e}")

    # _validate_entry, _on_registrar unchanged, but after registro we call archiver.update_snapshot()
    def _validate_entry(self):
        # when editable, user might have typed a name; try to resolve to a product id
        if self.product_cb.currentIndex() < 0:
            text = self.product_cb.currentText().strip()
            if text:
                # try to find matching item by label
                for i in range(self.product_cb.count()):
                    if self.product_cb.itemText(i).lower().startswith(text.lower()):
                        self.product_cb.setCurrentIndex(i)
                        break
        if self.product_cb.currentIndex() < 0:
            QMessageBox.warning(self, "Validación", "Seleccione un producto.")
            return False
        try:
            cantidad = float(self.cantidad_spin.value())
        except Exception:
            QMessageBox.warning(self, "Validación", "Cantidad inválida.")
            return False
        if cantidad <= 0:
            QMessageBox.warning(self, "Validación", "Ingrese una cantidad mayor a 0.")
            return False
        return True

    def _on_registrar(self):
        if not self._validate_entry():
            return
        # disable button
        self.registrar_btn.setEnabled(False)
        try:
            pid = self.product_cb.currentData()
            cantidad = float(self.cantidad_spin.value())
            # costo fijo en 0.0 ya que se quitó el campo
            costo = 0.0
            motivo = self.motivo_edit.text().strip() or None

            # insert movimiento (DBManager.insert_movimiento expected signature)
            if hasattr(self.db, "insert_movimiento"):
                mov_id = self.db.insert_movimiento("Entrada", int(pid), float(cantidad), float(costo), None, motivo)
            else:
                # fallback manual insertion
                cur = self.db.conn.cursor()
                fecha = datetime.datetime.now().isoformat(timespec='seconds')
                prod = self.db.fetchone("SELECT id,codigo,nombre,departamento FROM productos WHERE id = ?", (pid,))
                codigo = prod.get('codigo') if prod else None
                nombre = prod.get('nombre') if prod else None
                departamento = prod.get('departamento') if prod else None
                cur.execute("""
                    INSERT INTO movimientos (codigo_producto, producto_id, producto_nombre, departamento, tipo, cantidad, costo, fecha, imagen, motivo)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (codigo, int(pid), nombre, departamento, "Entrada", float(cantidad), float(costo), fecha, None, motivo))
                cur.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (float(cantidad), int(pid)))
                self.db.conn.commit()
                mov_id = cur.lastrowid

            QMessageBox.information(self, "Entrada", f"Entrada registrada (id: {mov_id}).")
            # limpiar inputs
            self.cantidad_spin.setValue(1.0)
            self.motivo_edit.clear()

            # refresh table and parent widgets
            QTimer.singleShot(0, self.cargar_tabla)
            try:
                if self.parent_widget and hasattr(self.parent_widget, "refresh_totals"):
                    QTimer.singleShot(0, lambda: self.parent_widget.refresh_totals())
                from modules.notification import NotificationManager
                if hasattr(NotificationManager, "instance"):
                    QTimer.singleShot(0, lambda: NotificationManager.instance(parent=self.parent_widget if self.parent_widget else None).evaluate_and_show(self.db))
            except Exception:
                pass
            # update archiver snapshot as table will be reloaded
            try:
                self.archiver.update_snapshot()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo registrar la entrada: {e}")
        finally:
            self.registrar_btn.setEnabled(True)

    def cargar_tabla(self, limit=300):
        """
        Carga últimas entradas (tipo = 'Entrada') desde movimientos y las muestra.
        """
        try:
            q = "SELECT id, codigo_producto, producto_id, producto_nombre, departamento, tipo, cantidad, fecha, motivo FROM movimientos WHERE lower(tipo) = 'entrada' ORDER BY fecha DESC LIMIT ?"
            rows = self.db.fetchall(q, (limit,)) or []
            if not rows:
                q2 = "SELECT id, codigo_producto, producto_id, producto_nombre, departamento, tipo, cantidad, fecha, motivo FROM movimientos WHERE tipo LIKE '%Entrada%' ORDER BY fecha DESC LIMIT ?"
                rows = self.db.fetchall(q2, (limit,)) or []

            self.table.setRowCount(0)
            for r in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                vals = [
                    r.get('id') or '',
                    r.get('codigo_producto') or '',
                    r.get('producto_nombre') or '',
                    f"{float(r.get('cantidad') or 0.0):,.3f}",
                    r.get('tipo') or '',
                    r.get('fecha') or '',
                    r.get('motivo') or ''
                ]
                for col, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    if col in (0, 3, 4, 5):
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col, item)

                # actions: eliminar entrada (si quieres)
                actions_col = self.table.columnCount() - 1
                del_btn = QPushButton("Eliminar")
                del_btn.setObjectName("del_btn")
                del_btn.setProperty("mov_id", r.get('id'))
                del_btn.clicked.connect(self._make_delete_handler(r.get('id'), r.get('producto_id'), r.get('cantidad')))
                self.table.setCellWidget(row, actions_col, del_btn)

            # after filling table update the archiver snapshot
            try:
                self.archiver.update_snapshot()
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar tabla de entradas: {e}")

    def _make_delete_handler(self, mov_id, producto_id, cantidad):
        def handler():
            if not mov_id:
                QMessageBox.warning(self, "Eliminar", "Movimiento inválido.")
                return
            msg = QMessageBox(self)
            msg.setWindowTitle("Eliminar")
            msg.setText("¿Eliminar esta entrada? Esto intentará revertir el stock.")
            btn_si = msg.addButton("Sí", QMessageBox.YesRole)
            btn_no = msg.addButton("No", QMessageBox.NoRole)
            msg.setDefaultButton(btn_no)
            msg.exec_()
            if msg.clickedButton() != btn_si:
                return
            try:
                # try db method first
                if hasattr(self.db, "eliminar_movimiento"):
                    self.db.eliminar_movimiento(mov_id)
                    try:
                        cur = self.db.conn.cursor()
                        cur.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (float(cantidad or 0.0), int(producto_id)))
                        self.db.conn.commit()
                    except Exception:
                        pass
                else:
                    cur = self.db.conn.cursor()
                    cur.execute("DELETE FROM movimientos WHERE id = ?", (mov_id,))
                    try:
                        cur.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (float(cantidad or 0.0), int(producto_id)))
                    except Exception:
                        pass
                    self.db.conn.commit()
                QMessageBox.information(self, "Eliminar", "Entrada eliminada. Stock ajustado.")
                QTimer.singleShot(0, self.cargar_tabla)
                try:
                    if self.parent_widget and hasattr(self.parent_widget, "refresh_totals"):
                        QTimer.singleShot(0, lambda: self.parent_widget.refresh_totals())
                except Exception:
                    pass
                # update archiver
                try:
                    self.archiver.update_snapshot()
                except Exception:
                    pass
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar la entrada: {e}")
        return handler

    def _on_export_pdf(self):
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "entradas.pdf", "PDF Files (*.pdf);;All Files (*)")
            if not path:
                return
            company_info = {
                "name": "Minimarket ChiChi N-K, C.A",
                "tax_id": "J-5099900-7"
            }
            export_qtablewidget_to_pdf(self.table, path, title="Registro de Entradas", company_info=company_info, orientation="landscape")
            QMessageBox.information(self, "Exportar", f"PDF guardado en: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Exportar", f"Error al exportar PDF: {e}")

    def _abrir_carrito_compras(self):
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout
            dlg = QDialog(self)
            dlg.setWindowTitle("Carrito de Entradas")
            try:
                from modules.ui_scaling import scale_px
                dlg.resize(scale_px(960), scale_px(640))
            except Exception:
                dlg.resize(960, 640)
            layout = QVBoxLayout(dlg)
            from modules.compras_carrito import ComprasCarritoWidget
            widget = ComprasCarritoWidget(db=self.db, parent=self)
            try:
                widget.venta_completada.connect(lambda data: (dlg.accept(), QTimer.singleShot(0, self.cargar_tabla)))
            except Exception:
                pass
            layout.addWidget(widget)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir carrito de entradas: {e}")

    def closeEvent(self, ev):
        try:
            if hasattr(self, 'archiver') and self.archiver:
                self.archiver.shutdown()
        except Exception:
            pass
        super().closeEvent(ev)

