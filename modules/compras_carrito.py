"""
Módulo: Carrito de Entradas
Reutiliza el carrito de ventas (VentasCarritoWidget) y lo adapta para registrar Entradas/Compras.
- Permite editar Precio de compra, Moneda (Bs/$) y % IVA al seleccionar un producto
- Calcula subtotal, IVA y total correctamente en Bs y USD (usando tasa BCV)
- Al completar, inserta movimientos tipo 'Entrada' y actualiza stock
"""
from PyQt5.QtWidgets import QHBoxLayout, QDoubleSpinBox, QComboBox, QLabel, QDialog, QVBoxLayout, QMessageBox, QGridLayout
from PyQt5.QtCore import QTimer

try:
    from modules.ventas_carrito import VentasCarritoWidget
except Exception:
    # Fallback import if package layout differs
    from ventas_carrito import VentasCarritoWidget


class ComprasCarritoWidget(VentasCarritoWidget):
    """Widget adaptado para compras. Hereda la mayor parte de la lógica del carrito de ventas
    pero permite editar precio de compra, moneda y %IVA por producto.
    """

    def __init__(self, db=None, parent=None):
        # Construir UI base (carrito de ventas)
        super().__init__(db=db, parent=parent, include_out_of_stock=True)

        # Cambiar encabezado y etiquetas para indicar modo compra
        try:
            if hasattr(self, 'lbl_factura'):
                self.lbl_factura.setText(f"Registro de Entrada {self.numero_factura}")
        except Exception:
            pass

        try:
            # Cambiar título del panel derecho si existe un QLabel con 'Carrito'
            for lbl in self.panel_der.findChildren(QLabel):
                try:
                    t = lbl.text() or ""
                    if 'Carrito' in t:
                        lbl.setText(t.replace('Ventas', 'Compras'))
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Ajustar etiqueta de cliente a proveedor y botón de cambio si existen
        try:
            if hasattr(self, 'lbl_cliente'):
                try:
                    self.lbl_cliente.setText('👤 Proveedor General')
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, 'btn_cambiar'):
                try:
                    self.btn_cambiar.setText('Cambiar Proveedor')
                    self.btn_cambiar.setToolTip('Seleccionar proveedor')
                    # connect to provider manager
                    self.btn_cambiar.clicked.disconnect()
                    self.btn_cambiar.clicked.connect(lambda: self._seleccionar_cliente('proveedores'))
                except Exception:
                    pass
        except Exception:
            pass

        # Reconfigurar botón de cierre/registro para que abra registro de entradas (no cierre de ventas)
        try:
            if hasattr(self, 'btn_cierre_diario'):
                try:
                    from modules.registro_compras import DialogoRegistroCompras
                    self.btn_cierre_diario.setText('Registro de Entradas')
                    self.btn_cierre_diario.setToolTip('Mostrar registro de entradas')
                    try:
                        self.btn_cierre_diario.clicked.disconnect()
                    except Exception:
                        pass
                    self.btn_cierre_diario.clicked.connect(lambda: DialogoRegistroCompras(self.db, parent=self).exec_())
                except Exception:
                    # leave as-is if dialog cannot be imported
                    pass
        except Exception:
            pass

        # Reemplazar campos 'Precio' y 'Depto' por controles editables (Precio de compra y % IVA)
        try:
            # Crear controles editables
            self.spin_precio_compra = QDoubleSpinBox()
            self.spin_precio_compra.setDecimals(2)
            self.spin_precio_compra.setSingleStep(0.01)
            self.spin_precio_compra.setRange(0, 999999999.99)
            self.spin_precio_compra.setValue(0.0)
            try:
                from modules.ui_scaling import scale_px
                self.spin_precio_compra.setFixedWidth(scale_px(120))
            except Exception:
                self.spin_precio_compra.setFixedWidth(120)

            self.currency_combo = QComboBox()
            self.currency_combo.addItems(['Bs', '$'])
            # track current currency of precio input for conversions
            self._precio_moneda_current = 'Bs'

            self.spin_iva = QDoubleSpinBox()
            self.spin_iva.setDecimals(2)
            self.spin_iva.setRange(0, 100)
            self.spin_iva.setValue(16)
            self.spin_iva.setSuffix('%')

            # Buscar el QGridLayout que contiene las etiquetas Stock/Precio/Depto
            card_layout = self.card_producto.layout()
            grid_layout = None
            for i in range(card_layout.count()):
                item = card_layout.itemAt(i)
                if item:
                    try:
                        sublayout = item.layout()
                    except Exception:
                        sublayout = None
                    if sublayout and type(sublayout).__name__ == 'QGridLayout':
                        grid_layout = sublayout
                        break
            # Si se encontró, reemplazar widgets en (1,1) y (2,1) por los controles editables
            if grid_layout is not None:
                try:
                    # actualizar texto de la etiqueta izquierda para IVA
                    try:
                        left_label_item = grid_layout.itemAtPosition(2, 0)
                        if left_label_item:
                            try:
                                lbl_widget = left_label_item.widget()
                                if isinstance(lbl_widget, QLabel):
                                    lbl_widget.setText('IVA (%):')
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # remover widgets viejos si existen
                    try:
                        grid_layout.removeWidget(self.lbl_prod_precio)
                        self.lbl_prod_precio.setParent(None)
                    except Exception:
                        pass
                    try:
                        grid_layout.removeWidget(self.lbl_prod_depto)
                        self.lbl_prod_depto.setParent(None)
                    except Exception:
                        pass
                    # agregar precio (spin + currency) en fila 1, columna 1
                    price_container = QHBoxLayout()
                    price_container.setSpacing(6)
                    price_container.addWidget(self.spin_precio_compra)
                    price_container.addWidget(self.currency_combo)
                    grid_layout.addLayout(price_container, 1, 1)
                    # agregar iva en fila 2, columna 1
                    grid_layout.addWidget(self.spin_iva, 2, 1)
                except Exception as e:
                    print('Error inserting purchase widgets into grid:', e)
            else:
                # fallback: insertar al final del card_layout
                price_layout = QHBoxLayout()
                price_layout.addWidget(QLabel('Precio compra:'))
                price_layout.addWidget(self.spin_precio_compra)
                price_layout.addWidget(self.currency_combo)
                price_layout.addWidget(QLabel('IVA:'))
                price_layout.addWidget(self.spin_iva)
                card_layout.addLayout(price_layout)
        except Exception as e:
            print('Error configuring purchase inputs:', e)

    def _cargar_productos(self):
        try:
            # Load products with purchase cost and related fields for compras
            if getattr(self, 'include_out_of_stock', False):
                rows = self.db.fetchall("""
                    SELECT id, codigo, nombre, descripcion, departamento, stock, unidad,
                           precio_final, precio_final_bs, imagen, iva, costo_compra, costo, ganancia, moneda
                    FROM productos
                    ORDER BY nombre
                """) or []
            else:
                rows = self.db.fetchall("""
                    SELECT id, codigo, nombre, descripcion, departamento, stock, unidad,
                           precio_final, precio_final_bs, imagen, iva, costo_compra, costo, ganancia, moneda
                    FROM productos
                    WHERE stock > 0
                    ORDER BY nombre
                """) or []
            self.productos_db = rows
        except Exception as e:
            print(f"Error cargando productos (compras): {e}")
            try:
                QMessageBox.warning(self, "Error", f"No se pudieron cargar productos: {e}")
            except Exception:
                pass

    def _actualizar_precio_producto(self):
        """Sobrescribe para poblar los controles de precio/moneda/iva al seleccionar producto."""
        if not self.producto_seleccionado:
            return
        try:
            # Prefer mostrar costo_compra (o costo histórico) en USD cuando esté disponible
            costo_compra = float(self.producto_seleccionado.get('costo_compra') or self.producto_seleccionado.get('costo') or 0)
            precio_usd = float(self.producto_seleccionado.get('precio_final', 0) or 0)
            # precio final en bs si existe
            precio_bs_db = None
            try:
                pb = self.producto_seleccionado.get('precio_final_bs')
                if pb is not None:
                    precio_bs_db = float(pb)
            except Exception:
                precio_bs_db = None

            if costo_compra and costo_compra > 0:
                # default to showing costo_compra in USD
                self.spin_precio_compra.setValue(costo_compra)
                self.currency_combo.setCurrentText('$')
            elif precio_bs_db and precio_bs_db > 0:
                self.spin_precio_compra.setValue(precio_bs_db)
                self.currency_combo.setCurrentText('Bs')
            elif precio_usd and self.tasa_bcv:
                try:
                    self.spin_precio_compra.setValue(precio_usd * self.tasa_bcv)
                    self.currency_combo.setCurrentText('Bs')
                except Exception:
                    self.spin_precio_compra.setValue(precio_usd)
                    self.currency_combo.setCurrentText('$')
            else:
                # fallback
                try:
                    self.spin_precio_compra.setValue(precio_usd if precio_usd > 0 else 0.0)
                    self.currency_combo.setCurrentText('$' if precio_usd > 0 else 'Bs')
                except Exception:
                    self.spin_precio_compra.setValue(0.0)
                    self.currency_combo.setCurrentText('Bs')

            iva_pct = float(self.producto_seleccionado.get('iva', 16) or 0)
            try:
                self.spin_iva.setValue(iva_pct)
            except Exception:
                pass
            # update product price label below search to reflect selected purchase price and currency
            try:
                cur = self.currency_combo.currentText() if hasattr(self, 'currency_combo') else 'Bs'
                price = float(self.spin_precio_compra.value())
                if cur == '$':
                    self.lbl_prod_precio.setText(f"{price:,.4f} $")
                else:
                    self.lbl_prod_precio.setText(f"{price:,.2f} Bs")
            except Exception:
                pass
        except Exception as e:
            print('Error actualizando precio de compra:', e)
        # store current currency of precio input for later conversions
        try:
            self._precio_moneda_current = self.currency_combo.currentText() if hasattr(self, 'currency_combo') else 'Bs'
        except Exception:
            self._precio_moneda_current = 'Bs'
        # connect currency change handler once
        try:
            if not getattr(self, '_currency_connected', False):
                self.currency_combo.currentTextChanged.connect(self._on_currency_changed)
                self._currency_connected = True
        except Exception:
            pass

    def _on_currency_changed(self, new_cur):
        try:
            prev = getattr(self, '_precio_moneda_current', None) or 'Bs'
            if prev == new_cur:
                return
            cur_val = float(self.spin_precio_compra.value())
            if prev == 'Bs' and new_cur == '$':
                if self.tasa_bcv and float(self.tasa_bcv):
                    new_val = cur_val / float(self.tasa_bcv)
                else:
                    new_val = cur_val
                # set with 4 decimals for USD and smaller step
                self.spin_precio_compra.blockSignals(True)
                self.spin_precio_compra.setDecimals(4)
                try:
                    self.spin_precio_compra.setSingleStep(0.0001)
                except Exception:
                    pass
                self.spin_precio_compra.setValue(round(new_val, 4))
                self.spin_precio_compra.blockSignals(False)
                self.lbl_prod_precio.setText(f"{self.spin_precio_compra.value():,.4f} $")
            elif prev == '$' and new_cur == 'Bs':
                if self.tasa_bcv and float(self.tasa_bcv):
                    new_val = cur_val * float(self.tasa_bcv)
                else:
                    new_val = cur_val
                self.spin_precio_compra.blockSignals(True)
                self.spin_precio_compra.setDecimals(2)
                try:
                    self.spin_precio_compra.setSingleStep(0.01)
                except Exception:
                    pass
                self.spin_precio_compra.setValue(round(new_val, 2))
                self.spin_precio_compra.blockSignals(False)
                self.lbl_prod_precio.setText(f"{self.spin_precio_compra.value():,.2f} Bs")
            else:
                # fallback: just update label and decimals according to currency
                if new_cur == '$':
                    self.spin_precio_compra.setDecimals(4)
                    self.lbl_prod_precio.setText(f"{cur_val:,.4f} $")
                else:
                    self.spin_precio_compra.setDecimals(2)
                    self.lbl_prod_precio.setText(f"{cur_val:,.2f} Bs")
            self._precio_moneda_current = new_cur
        except Exception:
            pass

    def _agregar_al_carrito(self):
        """Sobrescribe _agregar_al_carrito para usar precio de compra e IVA editables."""
        if not self.producto_seleccionado:
            return
        try:
            # ensure typed quantity is committed
            try:
                self.spin_cantidad.interpretText()
            except Exception:
                pass
            cantidad = float(self.spin_cantidad.value())
            # Para compras no validamos stock (porque se incrementará)
            try:
                stock = float(self.producto_seleccionado.get('stock', 0) or 0)
            except Exception:
                stock = 0.0

            # Leer inputs de precio/iva/moneda
            precio_input = float(self.spin_precio_compra.value())
            iva_pct = float(self.spin_iva.value()) if hasattr(self, 'spin_iva') else float(self.producto_seleccionado.get('iva', 16) or 0)
            moneda = self.currency_combo.currentText() if hasattr(self, 'currency_combo') else 'Bs'

            if moneda == '$':
                if not self.tasa_bcv:
                    QMessageBox.critical(self, "Error", "No hay tasa BCV disponible para convertir USD a Bs")
                    return
                precio_bs = precio_input * self.tasa_bcv
                precio_usd = precio_input
            else:
                precio_bs = precio_input
                precio_usd = (precio_bs / self.tasa_bcv) if (self.tasa_bcv and float(self.tasa_bcv)) else 0.0

            # Compute IVA and store both base cost and price-with-IVA
            costo_compra_usd = precio_usd
            costo_compra_bs = precio_bs
            precio_con_iva_usd = costo_compra_usd * (1.0 + iva_pct / 100.0)
            precio_con_iva_bs = costo_compra_bs * (1.0 + iva_pct / 100.0)

            # Si ya existe el producto en carrito, actualizar cantidad y precio (sobrescribir precio con el actual)
            for i, item in enumerate(self.carrito):
                if item['id'] == self.producto_seleccionado.get('id'):
                    nueva_cantidad = item['cantidad'] + cantidad
                    item['cantidad'] = nueva_cantidad
                    item['costo_compra_usd'] = costo_compra_usd
                    item['costo_compra_bs'] = costo_compra_bs
                    item['precio_unitario_usd'] = precio_con_iva_usd
                    item['precio_unitario_bs'] = precio_con_iva_bs
                    item['iva'] = iva_pct
                    item['subtotal_bs'] = nueva_cantidad * precio_con_iva_bs
                    self._actualizar_cards_carrito()
                    self._calcular_totales()
                    self.search_input.clear()
                    self.lista_resultados.hide()
                    self.spin_cantidad.setValue(1)
                    return

            nuevo_item = {
                'id': self.producto_seleccionado.get('id'),
                'codigo': self.producto_seleccionado.get('codigo'),
                'nombre': self.producto_seleccionado.get('nombre'),
                'cantidad': cantidad,
                'unidad': self.producto_seleccionado.get('unidad', 'und'),
                'costo_compra_usd': costo_compra_usd,
                'costo_compra_bs': costo_compra_bs,
                'precio_unitario_usd': precio_con_iva_usd,
                'precio_unitario_bs': precio_con_iva_bs,
                'iva': iva_pct,
                'subtotal_bs': cantidad * precio_con_iva_bs,
                'imagen': self.producto_seleccionado.get('imagen'),
                'stock_original': 999999
            }
            self.carrito.append(nuevo_item)
            self._actualizar_cards_carrito()
            self._calcular_totales()
            self.search_input.clear()
            self.lista_resultados.hide()
            self.spin_cantidad.setValue(1)
        except Exception as e:
            print(f"Error agregando al carrito de compras: {e}")
            QMessageBox.critical(self, "Error", f"Error al agregar producto: {e}")

    def _completar_venta(self, resultado_pago):
        """Al completar el pago en modo compras, registrar movimientos 'Entrada'."""
        try:
            compra_data = {
                'numero_factura': self.numero_factura,
                'fecha_hora': __import__('datetime').datetime.now().isoformat(),
                'cliente': self.cliente_actual or {'nombre': 'Proveedor', 'cedula': 'N/A'},
                'productos': self.carrito.copy(),
                'totales': self.totales,
                'pagos': resultado_pago['detalle_pagos'],
                'cambio': resultado_pago['cambio'],
                'tasa_bcv': self.tasa_bcv,
                'modo': 'compra'
            }
            # Insertar movimientos tipo 'Entrada'
            for item in self.carrito:
                try:
                    # determinar precios unitarios guardados en el item
                    precio_unitario_bs = float(item.get('precio_unitario_bs', 0.0) or 0.0)
                    precio_unitario_usd = float(item.get('precio_unitario_usd', 0.0) or 0.0)
                    cantidad = float(item.get('cantidad', 0.0) or 0.0)

                    # 1) Actualizar costo de compra en la tabla productos (en USD) si hubo cambio
                    try:
                        prod = self.db.fetchone("SELECT id, costo_compra, iva, ganancia, moneda FROM productos WHERE id = ?", (int(item['id']),))
                        if prod:
                            current_costo = float(prod.get('costo_compra') or 0.0)
                            # prefer iva from cart item when available (allow 0% as valid value)
                            try:
                                if 'iva' in item and item.get('iva') is not None:
                                    iva_db = float(item.get('iva'))
                                else:
                                    iva_db = float(prod.get('iva') or 0.0)
                            except Exception:
                                iva_db = float(prod.get('iva') or 0.0)
                            ganancia_db = float(prod.get('ganancia') or 0.0)

                            # determinar nuevo costo en USD prefiriendo campo explícito en el item
                            new_costo_usd = float(item.get('costo_compra_usd') or 0.0)
                            if new_costo_usd == 0 and precio_unitario_bs and self.tasa_bcv:
                                try:
                                    new_costo_usd = precio_unitario_bs / float(self.tasa_bcv)
                                except Exception:
                                    new_costo_usd = 0.0

                            # Si hay diferencia significativa, actualizar costos y precios asociados
                                            # Si hay diferencia significativa en costo o en IVA, actualizar costos y precios asociados
                            try:
                                prod_iva_db = float(prod.get('iva') or 0.0)
                            except Exception:
                                prod_iva_db = 0.0
                            # Use new cost if provided, otherwise keep current cost to allow IVA-only updates
                            update_costo = new_costo_usd if new_costo_usd > 0 else current_costo
                            if (abs(update_costo - current_costo) > 1e-6) or (abs(iva_db - prod_iva_db) > 1e-6):
                                try:
                                    # recalcular precio final (USD) usando fórmula existente: (costo_compra * (1+iva)) * (1+ganancia)
                                    new_precio_final_usd = round((update_costo * (1.0 + (iva_db / 100.0))) * (1.0 + (ganancia_db / 100.0)), 4)
                                except Exception:
                                    new_precio_final_usd = new_costo_usd
                                try:
                                    new_precio_final_bs = round(new_precio_final_usd * float(self.tasa_bcv), 2) if self.tasa_bcv else None
                                except Exception:
                                    new_precio_final_bs = None

                                try:
                                    cur = self.db.conn.cursor()
                                    if new_precio_final_bs is not None:
                                        cur.execute(
                                            """UPDATE productos SET costo_compra = ?, iva = ?, precio_final = ?, precio_final_bs = ?, bcv_tasa = ?, moneda = '$' WHERE id = ?""",
                                            (float(update_costo), float(iva_db), float(new_precio_final_usd), float(new_precio_final_bs), float(self.tasa_bcv if self.tasa_bcv else 0.0), int(item['id']))
                                        )
                                    else:
                                        cur.execute(
                                            """UPDATE productos SET costo_compra = ?, iva = ?, precio_final = ?, bcv_tasa = ?, moneda = '$' WHERE id = ?""",
                                            (float(update_costo), float(iva_db), float(new_precio_final_usd), float(self.tasa_bcv if self.tasa_bcv else 0.0), int(item['id']))
                                        )
                                    self.db.conn.commit()
                                except Exception as e:
                                    print('Error actualizando producto con nuevo precio de compra:', e)
                    except Exception as e:
                        print('Error comprobando/actualizando precio de producto:', e)

                    # 2) Registrar movimiento de entrada y actualizar stock
                    if hasattr(self.db, 'insert_movimiento'):
                        # registrar costo como subtotal en Bs (consistente con ventas)
                        self.db.insert_movimiento('Entrada', int(item['id']), float(cantidad), float(item.get('subtotal_bs', 0.0)), item.get('imagen'), f"Compra {self.numero_factura}")
                    else:
                        # fallback manual
                        cur = self.db.conn.cursor()
                        fecha = __import__('datetime').datetime.now().isoformat(timespec='seconds')
                        prod = self.db.fetchone("SELECT id,codigo,nombre,departamento FROM productos WHERE id = ?", (item['id'],))
                        codigo = prod.get('codigo') if prod else None
                        nombre = prod.get('nombre') if prod else None
                        departamento = prod.get('departamento') if prod else None
                        cur.execute("INSERT INTO movimientos (codigo_producto, producto_id, producto_nombre, departamento, tipo, cantidad, costo, fecha, imagen, motivo) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                    (codigo, int(item['id']), nombre, departamento, 'Entrada', float(cantidad), float(item.get('subtotal_bs', 0.0)), fecha, item.get('imagen'), f"Entrada {self.numero_factura}"))
                        cur.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (float(cantidad), int(item['id'])))
                        self.db.conn.commit()
                except Exception as e:
                    print('Error registrando movimiento de compra:', e)

            # Emitir señal y avisar
            try:
                self.venta_completada.emit(compra_data)
            except Exception:
                pass

            QMessageBox.information(self, "✅ Entrada Registrada", f"Registro de entrada {self.numero_factura} procesado exitosamente\nTotal: {self.totales['total_bs']:,.2f} Bs")
            try:
                self._guardar_factura_pdf(compra_data)
            except Exception as e:
                print(f"Error generando PDF de compra: {e}")
            QTimer.singleShot(0, self._nueva_venta)
        except Exception as e:
            print(f"Error completando compra: {e}")
            QMessageBox.critical(self, "Error", f"Error al completar compra: {e}")

    def _nueva_venta(self):
        # reutiliza la limpieza original y ajusta texto del encabezado a compra
        try:
            super()._nueva_venta()
        except Exception:
            # fallback: limpiar manualmente
            self.carrito = []
            self.cliente_actual = None
            self.numero_factura = self._generar_factura()
            self.totales = None
        try:
            if hasattr(self, 'lbl_factura'):
                try:
                    self.lbl_factura.setText(f"Registro de compra {self.numero_factura}")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._refresh_ui_post_sale()
        except Exception:
            pass
        try:
            if hasattr(self, 'lbl_factura'):
                try:
                    self.lbl_factura.setText(f"Registro de Entrada {self.numero_factura}")
                except Exception:
                    pass
        except Exception:
            pass

    def _construir_html_factura(self, venta_data):
        # reutilizar HTML de ventas y reemplazar frase por 'Registro de Entrada'
        try:
            html = super()._construir_html_factura(venta_data)
            return html.replace('Registro de venta', 'Registro de Entrada')
        except Exception:
            return super()._construir_html_factura(venta_data)

    def _guardar_factura_pdf(self, venta_data):
        # Guardar PDF de entradas en carpeta 'entradas' dentro del directorio de registros
        try:
            import os, datetime, re
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            try:
                from modules import config as app_config
                pdf_base = app_config.get_pdf_dir()
            except Exception:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                pdf_base = os.path.join(base_dir, 'registros')
            os.makedirs(pdf_base, exist_ok=True)
            entradas_root = os.path.join(pdf_base, 'entradas')
            os.makedirs(entradas_root, exist_ok=True)
            ym = datetime.datetime.now().strftime('%Y-%m')
            invoices_dir = os.path.join(entradas_root, ym)
            os.makedirs(invoices_dir, exist_ok=True)

            # header data
            company = 'Empresa'
            rif = ''
            try:
                from modules import config as app_config
                company = app_config.get_company_name() or company
                rif = app_config.get_company_rif() or rif
            except Exception:
                pass
            try:
                if hasattr(self, 'parent_dashboard') and self.parent_dashboard is not None:
                    company = self.parent_dashboard.left_company_name.text() or company
                    rif = self.parent_dashboard.left_company_rif.text() or rif
            except Exception:
                pass
            safe_company = re.sub(r'[^A-Za-z0-9_-]', '_', company.strip()) if company else 'Empresa'
            safe_rif = re.sub(r'[^A-Za-z0-9_-]', '_', (rif or '').strip())
            filename = f"{safe_company}_{safe_rif}_{venta_data.get('numero_factura','')}.pdf"
            filepath = os.path.join(invoices_dir, filename)

            try:
                pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
                font_main = "DejaVu"
            except Exception:
                font_main = "Helvetica"
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name="Header", fontName=font_main, fontSize=15, alignment=1, spaceAfter=8, spaceBefore=4, textColor=colors.HexColor("#5E3DB3")))
            styles.add(ParagraphStyle(name="Meta", fontName=font_main, fontSize=10, alignment=0))
            styles.add(ParagraphStyle(name="TableCell", fontName=font_main, fontSize=10, spaceAfter=2, spaceBefore=2))
            styles.add(ParagraphStyle(name="Total", fontName=font_main, fontSize=12, spaceAfter=3, spaceBefore=8, alignment=2, textColor=colors.HexColor("#00C853")))

            doc = SimpleDocTemplate(filepath, pagesize=A4, leftMargin=32, rightMargin=32, topMargin=28, bottomMargin=22)
            elements = []
            elements.append(Paragraph(f"<b>{company}</b>", styles["Header"]))
            elements.append(Paragraph(f"RIF: {rif}", styles["Meta"]))
            cliente = venta_data.get('cliente', {})
            elements.append(Paragraph(f"Proveedor: {cliente.get('nombre', 'Proveedor')} | Cédula/RIF: {cliente.get('cedula','N/A')}", styles["Meta"]))
            elements.append(Paragraph(f"Fecha: {venta_data.get('fecha_hora','')}", styles["Meta"]))

            # table
            productos = venta_data.get('productos', [])
            data = [["Código", "Producto", "Cantidad", "Precio (Bs)", "Subtotal (Bs)"]]
            for p in productos:
                codigo = p.get('codigo','')
                nombre = p.get('nombre','')
                cantidad = p.get('cantidad',0)
                precio = p.get('precio_unitario_bs') or p.get('subtotal_bs',0.0)
                subtotal = p.get('subtotal_bs',0.0)
                data.append([codigo, nombre, cantidad, f"{float(precio):,.2f}", f"{float(subtotal):,.2f}"])
            table = Table(data, hAlign='LEFT')
            table.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.2, colors.HexColor("#DDDDDD")),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#FFF3E0")),
                ("ALIGN", (2,1), (2,-1), "RIGHT"),
            ]))
            elements.append(table)
            elements.append(Paragraph(f"Total: {float(venta_data.get('totales',{}).get('total_bs',0.0)):,.2f} Bs", styles["Total"]))
            doc.build(elements)
            print(f"Factura de entrada guardada: {filepath}")
        except Exception as e:
            print(f"Error guardando PDF de compra: {e}")
