"""
Módulo de Carrito de Ventas - Versión Profesional Mejorada
Lógica principal del carrito de ventas - MODERNO Y VISUAL
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QFrame, QGridLayout,
    QScrollArea, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect, QMessageBox, QInputDialog, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap, QTextDocument, QKeySequence, QFont
from PyQt5.QtPrintSupport import QPrinter

from db_manager import DBManager
import datetime
import os
import re
import time

from modules.ventas_carrito_constants import (
    PRIMARY, PRIMARY_LIGHT, PRIMARY_DARK, ACCENT, WARNING,
    DANGER, BACKGROUND, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, BORDER, CARD_RADIUS
)
from modules.ventas_carrito_cards import ProductoCard

class VentasCarritoWidget(QWidget):
    """
    Widget principal del carrito de ventas - Estética profesional
    """
    salida_completada = pyqtSignal(dict)
    volver_solicitado = pyqtSignal()

    def __init__(self, db=None, parent=None, include_out_of_stock=False):
        super().__init__(parent)
        self.db = db or DBManager()
        self.parent_dashboard = parent
        # feature flags
        self.include_out_of_stock = bool(include_out_of_stock)

        # Estado
        self.carrito = []
        self.cliente_actual = None
        self.tasa_bcv = None
        self.numero_factura = self._generar_factura()
        self.productos_db = []
        self.producto_seleccionado = None
        self.totales = None

        self._build_ui()
        self._aplicar_estilos_globales()
        QTimer.singleShot(100, self._cargar_datos_iniciales)

        # modo: 'Venta' o 'Salida' (afecta textos visibles). Por defecto 'Venta'.
        self.modo = 'Salida'

    def set_mode(self, modo: str):
        """Establece el modo del carrito y actualiza etiquetas visibles."""
        try:
            modo_norm = 'Salida' if str(modo).lower().startswith('sal') else 'Venta'
            self.modo = modo_norm
            # actualizar título del carrito si existe
            try:
                if hasattr(self, 'titulo_carrito_label') and self.titulo_carrito_label:
                    if self.modo == 'Salida':
                        self.titulo_carrito_label.setText('🛒 Carrito de Salida')
                    else:
                        self.titulo_carrito_label.setText('🛒 Carrito')
            except Exception:
                pass
            # actualizar etiqueta factura (junto al botón volver)
            try:
                if hasattr(self, 'lbl_factura') and self.lbl_factura:
                    if self.modo == 'Salida':
                        # mostrar texto fijo sin número según solicitud
                        self.lbl_factura.setText('Registro de Salidas')
                    else:
                        self.lbl_factura.setText(f"Registro de venta {self.numero_factura}")
            except Exception:
                pass
        except Exception:
            pass

        # Barcode scanner buffer and app-level event filter so scanners work without focusing the search field
        self._barcode_buf = ""
        self._barcode_last_ts = None
        self._barcode_last_delta = None
        self._barcode_max_inter_key = 0.15  # seconds between keys considered as scanner
        self._barcode_reset_timeout = 0.9   # reset buffer after this many seconds of inactivity
        self._barcode_min_length = 3        # minimum code length to consider as barcode when Enter pressed
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.installEventFilter(self)
        except Exception:
            pass

        # Timer to process buffer if scanner doesn't send Enter (inactivity-based fallback)
        try:
            self._barcode_check_timer = QTimer(self)
            self._barcode_check_timer.timeout.connect(self._barcode_check_tick)
            self._barcode_check_timer.start(200)
        except Exception:
            self._barcode_check_timer = None

        # Focus watchdog: keep the search input focused while sales widget is active
        try:
            self._focus_timer = QTimer(self)
            self._focus_timer.timeout.connect(self._ensure_search_focus)
            self._focus_timer.start(400)
        except Exception:
            self._focus_timer = None

        self.timer_tasa = QTimer(self)
        self.timer_tasa.timeout.connect(self._actualizar_tasa)
        self.timer_tasa.start(120000)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 8, 4, 8)
        main_layout.setSpacing(8)

        # Panel izquierdo: Búsqueda
        self.panel_izq = self._crear_panel_izquierdo()
        main_layout.addWidget(self.panel_izq, 0)

        # Panel derecho: Carrito
        self.panel_der = self._crear_panel_derecho()
        main_layout.addWidget(self.panel_der, 1)

    def _crear_panel_izquierdo(self):
        panel = QFrame()
        panel.setObjectName("panel_izq")
        try:
            from modules.ui_scaling import scale_px

            panel.setFixedWidth(scale_px(410))
        except Exception:
            panel.setFixedWidth(410)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        btn_volver = QPushButton("← Volver")
        try:
            from modules.ui_scaling import scale_px

            btn_volver.setFixedHeight(scale_px(48))
        except Exception:
            btn_volver.setFixedHeight(48)
        btn_volver.setStyleSheet(f"""
            QPushButton {{
                background: {BORDER};
                color: {PRIMARY_DARK};
                border-radius: 12px;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background: {PRIMARY_LIGHT};
                color: white;
            }}
        """)
        btn_volver.clicked.connect(self._volver_dashboard)
        header.addWidget(btn_volver)
        header.addStretch()
        self.lbl_factura = QLabel(f"Registro {self.numero_factura}")
        self.lbl_factura.setStyleSheet(f"""
            background: {PRIMARY};
            color: white;
            border-radius: 11px;
            padding: 8px 18px;
            font-weight: 800;
            font-size: 17px;
            letter-spacing:1px;
        """)
        header.addWidget(self.lbl_factura)
        layout.addLayout(header)

        titulo = QLabel("🔍 Buscar Productos")
        titulo.setStyleSheet(f"font-size: 19px; font-weight: bold; color: {PRIMARY_DARK}; padding-top:6px;")
        layout.addWidget(titulo)

        # Buscar
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border-radius: 11px;
                border: 1.8px solid {BORDER};
            }}
        """)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(8, 8, 8, 8)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Escriba para buscar...")
        try:
            from modules.ui_scaling import scale_px

            self.search_input.setFixedHeight(scale_px(38))
        except Exception:
            self.search_input.setFixedHeight(38)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1.2px solid {BORDER};
                border-radius: 6px;
                padding: 9px;
                font-size: 16px;
                background: {SURFACE};
            }}
            QLineEdit:focus {{
                border: 1.8px solid {PRIMARY};
            }}
        """)
        self.search_input.textChanged.connect(self._filtrar_productos)
        self.search_input.returnPressed.connect(self._handle_search_return)
        self.search_input.installEventFilter(self)
        search_layout.addWidget(self.search_input)

        self.lista_resultados = QListWidget()
        try:
            from modules.ui_scaling import scale_px

            self.lista_resultados.setMaximumHeight(scale_px(140))
        except Exception:
            self.lista_resultados.setMaximumHeight(140)
        self.lista_resultados.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {BORDER};
                border-radius: 5px;
                background: {SURFACE};
                font-size: 15px;
            }}
            QListWidget::item {{
                padding: 7px 7px;
                border-bottom: 1.3px solid {BORDER};
            }}
            QListWidget::item:selected {{
                background: {PRIMARY_LIGHT};
                color: white;
            }}
            QListWidget::item:hover {{
                background: {BACKGROUND};
            }}
        """)
        self.lista_resultados.itemClicked.connect(self._on_producto_seleccionado_lista)
        self.lista_resultados.hide()
        search_layout.addWidget(self.lista_resultados)
        layout.addWidget(search_frame)

        # Card de producto
        self.card_producto = QFrame()
        self.card_producto.setStyleSheet(f"""
            QFrame {{
                background: {BACKGROUND};
                border-radius: 13px;
                border: 1.7px solid {BORDER};
            }}
        """)
        card_layout = QVBoxLayout(self.card_producto)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(9)

        self.lbl_prod_nombre = QLabel("Seleccione un producto")
        self.lbl_prod_nombre.setStyleSheet(f"font-weight: bold; font-size: 15.5px; color: {TEXT_PRIMARY};")
        self.lbl_prod_nombre.setWordWrap(True)
        card_layout.addWidget(self.lbl_prod_nombre)

        info_grid = QGridLayout()
        info_grid.setSpacing(7)
        info_grid.setColumnStretch(1, 1)
        self.lbl_prod_stock = QLabel("--")
        self.lbl_prod_precio = QLabel("--")
        self.lbl_prod_depto = QLabel("--")
        info_grid.addWidget(QLabel("Stock:"), 0, 0)
        info_grid.addWidget(self.lbl_prod_stock, 0, 1)
        info_grid.addWidget(QLabel("Precio:"), 1, 0)
        info_grid.addWidget(self.lbl_prod_precio, 1, 1)
        info_grid.addWidget(QLabel("Depto:"), 2, 0)
        info_grid.addWidget(self.lbl_prod_depto, 2, 1)
        card_layout.addLayout(info_grid)

        self.lbl_prod_imagen = QLabel()
        try:
            from modules.ui_scaling import scale_px

            self.lbl_prod_imagen.setFixedSize(scale_px(82), scale_px(62))
        except Exception:
            self.lbl_prod_imagen.setFixedSize(82, 62)
        self.lbl_prod_imagen.setStyleSheet(f"""
            background: {SURFACE};
            border-radius: 10px;
            border: 1.3px solid {BORDER};
        """)
        self.lbl_prod_imagen.setAlignment(Qt.AlignCenter)
        self.lbl_prod_imagen.setText("📷")
        self.lbl_prod_imagen.setStyleSheet(self.lbl_prod_imagen.styleSheet() + "font-size: 32px; color: #CCC;")
        card_layout.addWidget(self.lbl_prod_imagen, alignment=Qt.AlignCenter)

        cantidad_row = QHBoxLayout()
        cantidad_row.addWidget(QLabel("Cantidad:"))
        self.spin_cantidad = QDoubleSpinBox()
        self.spin_cantidad.setDecimals(3)
        self.spin_cantidad.setRange(0.001, 9999)
        self.spin_cantidad.setValue(1)
        try:
            from modules.ui_scaling import scale_px

            self.spin_cantidad.setFixedWidth(scale_px(106))
        except Exception:
            self.spin_cantidad.setFixedWidth(106)
        try:
            from modules.ui_scaling import scale_px

            self.spin_cantidad.setFixedHeight(scale_px(36))
        except Exception:
            self.spin_cantidad.setFixedHeight(36)
        self.spin_cantidad.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.6px solid {PRIMARY_LIGHT};
                border-radius: 8px;
                padding: 6px;
                font-size: 15px;
            }}
        """)
        cantidad_row.addWidget(self.spin_cantidad)
        cantidad_row.addStretch()
        card_layout.addLayout(cantidad_row)

        self.btn_agregar = QPushButton("＋ Agregar al Carrito")
        self.btn_agregar.setEnabled(False)
        try:
            from modules.ui_scaling import scale_px

            self.btn_agregar.setFixedHeight(scale_px(44))
        except Exception:
            self.btn_agregar.setFixedHeight(44)
        self.btn_agregar.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY_DARK};
                color: white;
                border-radius: 12px;
                font-weight: bold;
                font-size: 19px;
                padding: 13px 0;
            }}
            QPushButton:disabled {{
                background: #E7E7E7;
                color: #BBB;
            }}
            QPushButton:hover:enabled {{
                background: {ACCENT};
            }}
        """)
        self.btn_agregar.clicked.connect(self._agregar_al_carrito)
        card_layout.addWidget(self.btn_agregar)

        self.card_producto.hide()
        layout.addWidget(self.card_producto)
        layout.addStretch()
        return panel

    def _crear_panel_derecho(self):
        panel = QFrame()
        panel.setObjectName("panel_der")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(10)

        # Header compacto
        header = QHBoxLayout()
        self.titulo_carrito_label = QLabel("🛒 Carrito")
        self.titulo_carrito_label.setStyleSheet(f"font-size: 22px; font-weight:900; color: {PRIMARY}; padding:8px 0;")
        header.addWidget(self.titulo_carrito_label)
        header.addStretch()

        self.lbl_cliente = QLabel("👤 Cliente General")
        self.lbl_cliente.setStyleSheet(f"""
            background: {BACKGROUND};
            color: {TEXT_PRIMARY};
            border-radius: 10px;
            padding: 8px 20px;
            font-size: 16px;
            font-weight: bold;
        """)
        header.addWidget(self.lbl_cliente)

        self.btn_cambiar = QPushButton("Cambiar Cliente")
        try:
            from modules.ui_scaling import scale_px

            self.btn_cambiar.setFixedHeight(scale_px(36))
        except Exception:
            self.btn_cambiar.setFixedHeight(36)
        self.btn_cambiar.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY_LIGHT};
                color: {PRIMARY_DARK};
                border-radius: 11px;
                padding: 8px 17px;
                font-size: 15px;
                font-weight: bold;
                border:1.7px solid {PRIMARY_DARK};
            }}
            QPushButton:hover {{
                background: {ACCENT};
                color: white;
                border: 2.3px solid {ACCENT};
            }}
        """)
        self.btn_cambiar.clicked.connect(lambda: self._seleccionar_cliente('clientes'))
        header.addWidget(self.btn_cambiar)
        layout.addLayout(header)

        # Área carrito - AHORA CON MÁS ESPACIO
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.container_carrito = QWidget()
        self.layout_carrito = QVBoxLayout(self.container_carrito)
        self.layout_carrito.setContentsMargins(0, 0, 0, 0)
        self.layout_carrito.setSpacing(5)
        self.layout_carrito.addStretch()

        scroll.setWidget(self.container_carrito)
        layout.addWidget(scroll, 1)

        self.lbl_carrito_vacio = QLabel("🛒\nEl carrito está vacío\nBusque y agregue productos")
        self.lbl_carrito_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_carrito_vacio.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 18px;
            padding: 22px;
            font-weight: bold;
        """)
        self.layout_carrito.insertWidget(0, self.lbl_carrito_vacio)

        # PANEL INFERIOR COMPACTO: Totales a la derecha, botones a la izquierda
        bottom_panel = QHBoxLayout()
        bottom_panel.setSpacing(12)

        # IZQUIERDA: Botones de acción
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(8)

        self.btn_siguiente = QPushButton("💳 Pagar")
        self.btn_siguiente.setEnabled(False)
        try:
            from modules.ui_scaling import scale_px

            self.btn_siguiente.setFixedHeight(scale_px(42))
        except Exception:
            self.btn_siguiente.setFixedHeight(42)
        try:
            from modules.ui_scaling import scale_px

            self.btn_siguiente.setFixedWidth(scale_px(140))
        except Exception:
            self.btn_siguiente.setFixedWidth(140)
        self.btn_siguiente.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
            }}
            QPushButton:disabled {{
                background: #B2E5B7;
            }}
            QPushButton:hover:enabled {{
                background: #22B822;
            }}
        """)
        self.btn_siguiente.clicked.connect(self._abrir_dialogo_pago)
        buttons_layout.addWidget(self.btn_siguiente)
        # Shortcut: Ctrl+P para abrir el diálogo de pago
        try:
            self._shortcut_pagar = QShortcut(QKeySequence("Ctrl+P"), self)
            self._shortcut_pagar.activated.connect(self._abrir_dialogo_pago)
        except Exception:
            pass

        btn_cancelar = QPushButton("✗ Cancelar")
        try:
            from modules.ui_scaling import scale_px

            btn_cancelar.setFixedHeight(scale_px(36))
        except Exception:
            btn_cancelar.setFixedHeight(36)
        try:
            from modules.ui_scaling import scale_px

            btn_cancelar.setFixedWidth(scale_px(140))
        except Exception:
            btn_cancelar.setFixedWidth(140)
        btn_cancelar.setStyleSheet(f"""
            QPushButton {{
                background: #FFFAF9;
                color: {DANGER};
                border: 1.5px solid {DANGER};
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #FFE6E7;
            }}
        """)
        btn_cancelar.clicked.connect(self._cancelar_venta)
        buttons_layout.addWidget(btn_cancelar)

        self.btn_cierre_diario = QPushButton("Cierre Diario")
        try:
            from modules.ui_scaling import scale_px

            self.btn_cierre_diario.setFixedHeight(scale_px(36))
        except Exception:
            self.btn_cierre_diario.setFixedHeight(36)
        try:
            from modules.ui_scaling import scale_px

            self.btn_cierre_diario.setFixedWidth(scale_px(140))
        except Exception:
            self.btn_cierre_diario.setFixedWidth(140)
        self.btn_cierre_diario.setToolTip("Generar PDF con todas las salidas del día")
        try:
            self.btn_cierre_diario.clicked.connect(self._on_cierre_diario)
        except Exception:
            pass
        buttons_layout.addWidget(self.btn_cierre_diario)
        buttons_layout.addStretch()

        bottom_panel.addLayout(buttons_layout)

        # DERECHA: Resumen compacto de totales
        self.frame_totales = QFrame()
        self.frame_totales.setStyleSheet(f"""
            QFrame {{
                background: {SURFACE};
                border-radius: 10px;
                border: 1.5px solid {BORDER};
            }}
        """)
        t_layout = QVBoxLayout(self.frame_totales)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(4)

        # Subtotal, IVA y Descuento
        details_layout = QHBoxLayout()
        details_layout.setSpacing(15)

        # Subtotal
        sub_layout = QHBoxLayout()
        lbl_sub = QLabel("Sub:")
        lbl_sub.setStyleSheet("font-size: 13px; color: {TEXT_SECONDARY};")
        sub_layout.addWidget(lbl_sub)
        self.val_subtotal = QLabel("0.00")
        self.val_subtotal.setStyleSheet("font-weight: bold; font-size: 14px;")
        sub_layout.addWidget(self.val_subtotal)
        sub_layout.addWidget(QLabel("Bs"))
        details_layout.addLayout(sub_layout)

        # IVA
        iva_layout = QHBoxLayout()
        lbl_iva = QLabel("IVA:")
        lbl_iva.setStyleSheet("font-size: 13px; color: {TEXT_SECONDARY};")
        iva_layout.addWidget(lbl_iva)
        self.val_iva = QLabel("0.00")
        self.val_iva.setStyleSheet("font-weight: bold; font-size: 14px; color:#883;")
        iva_layout.addWidget(self.val_iva)
        iva_layout.addWidget(QLabel("Bs"))
        details_layout.addLayout(iva_layout)

        # Descuento
        desc_layout = QHBoxLayout()
        lbl_desc = QLabel("Desc:")
        lbl_desc.setStyleSheet("font-size: 13px; color: {TEXT_SECONDARY};")
        desc_layout.addWidget(lbl_desc)
        self.spin_descuento = QDoubleSpinBox()
        self.spin_descuento.setRange(0, 100)
        self.spin_descuento.setSuffix("%")
        self.spin_descuento.setValue(0)
        try:
            from modules.ui_scaling import scale_px

            self.spin_descuento.setFixedWidth(scale_px(60))
        except Exception:
            self.spin_descuento.setFixedWidth(60)
        try:
            from modules.ui_scaling import scale_px

            self.spin_descuento.setFixedHeight(scale_px(22))
        except Exception:
            self.spin_descuento.setFixedHeight(22)
        self.spin_descuento.setStyleSheet("font-size: 12px;")
        self.spin_descuento.valueChanged.connect(self._calcular_totales)
        desc_layout.addWidget(self.spin_descuento)
        desc_layout.addWidget(QLabel("="))
        self.val_descuento = QLabel("0.00")
        self.val_descuento.setStyleSheet(f"color: {WARNING}; font-weight: bold; font-size: 14px;")
        desc_layout.addWidget(self.val_descuento)
        details_layout.addLayout(desc_layout)

        t_layout.addLayout(details_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        t_layout.addWidget(line)

        # TOTAL principal
        total_layout = QHBoxLayout()
        lbl_total = QLabel("TOTAL:")
        lbl_total.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 18px;")
        total_layout.addWidget(lbl_total)
        total_layout.addStretch()
        self.val_total = QLabel("0.00 Bs")
        self.val_total.setStyleSheet(f"color: {PRIMARY_DARK}; font-weight: 900; font-size: 22px;")
        total_layout.addWidget(self.val_total)
        t_layout.addLayout(total_layout)

        usd_layout = QHBoxLayout()
        self.val_usd = QLabel("≈ 0.00 $")
        self.val_usd.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        usd_layout.addWidget(self.val_usd)
        usd_layout.addStretch()
        self.lbl_tasa_info = QLabel("BCV: --")
        self.lbl_tasa_info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        usd_layout.addWidget(self.lbl_tasa_info)
        t_layout.addLayout(usd_layout)

        bottom_panel.addWidget(self.frame_totales, 1)

        layout.addLayout(bottom_panel)

        return panel

    def _aplicar_estilos_globales(self):
        for panel in [self.panel_izq, self.panel_der]:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(22)
            shadow.setColor(QColor(107, 78, 214, 20))
            shadow.setOffset(0, 4)
            panel.setGraphicsEffect(shadow)
            panel.setStyleSheet(f"""
                QFrame#{panel.objectName()} {{
                    background: {SURFACE};
                    border-radius: 17px;
                    border: 1.8px solid {BORDER};
                }}
            """)

    def _cargar_datos_iniciales(self):
        self._actualizar_tasa()
        self._cargar_productos()

    def _actualizar_tasa(self):
        try:
            from main import get_current_bcv_rate
            rate, ts = get_current_bcv_rate()
            if rate:
                self.tasa_bcv = float(rate)
                self.lbl_tasa_info.setText(f"BCV: {self.tasa_bcv:,.2f}")
                if self.producto_seleccionado:
                    self._actualizar_precio_producto()
            else:
                self.lbl_tasa_info.setText("BCV: --")
        except Exception as e:
            print(f"Error obteniendo tasa BCV: {e}")
            self.lbl_tasa_info.setText("BCV: Error")

    def _cargar_productos(self):
        try:
            rows = self.db.fetchall("""
                SELECT id, codigo, nombre, departamento, stock, unidad,
                       precio_final, precio_final_bs, imagen, iva
                FROM productos
                WHERE stock > 0
                ORDER BY nombre
            """) or []
            self.productos_db = rows
        except Exception as e:
            print(f"Error cargando productos: {e}")
            QMessageBox.warning(self, "Error", f"No se pudieron cargar productos: {e}")

    def _filtrar_productos(self, texto):
        texto = texto.lower().strip()
        self.lista_resultados.clear()

        if len(texto) < 2:
            self.lista_resultados.hide()
            return

        productos = [
            p for p in self.productos_db
            if texto in (p.get('nombre', '') or '').lower()
            or texto in (p.get('codigo', '') or '').lower()
        ][:15]

        if not productos:
            self.lista_resultados.hide()
            return

        for p in productos:
            nombre = p.get('nombre', 'Sin nombre')
            codigo = p.get('codigo', 'N/A')
            stock = float(p.get('stock', 0) or 0)
            precio_usd = float(p.get('precio_final', 0) or 0)
            iva_pct = float(p.get('iva', 16))
            if self.tasa_bcv and precio_usd > 0:
                precio_bs = precio_usd * self.tasa_bcv
                precio_str = f"{precio_bs:,.2f} Bs"
            else:
                precio_str = f"{precio_usd:.4f} $"
            display = f"{nombre}\n  {codigo} • Stock: {stock:.2f} • {precio_str}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, p)
            self.lista_resultados.addItem(item)

        self.lista_resultados.show()

    def _mostrar_todos_productos(self):
        try:
            self.lista_resultados.clear()
            productos = sorted(self.productos_db or [], key=lambda p: (p.get('nombre') or '').lower())
            for p in productos:
                nombre = p.get('nombre', 'Sin nombre')
                codigo = p.get('codigo', 'N/A')
                stock = float(p.get('stock', 0) or 0)
                precio_usd = float(p.get('precio_final', 0) or 0)
                if self.tasa_bcv and precio_usd > 0:
                    precio_bs = precio_usd * self.tasa_bcv
                    precio_str = f"{precio_bs:,.2f} Bs"
                else:
                    precio_str = f"{precio_usd:.4f} $"
                display = f"{nombre}\n  {codigo} • Stock: {stock:.2f} • {precio_str}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, p)
                self.lista_resultados.addItem(item)
            if productos:
                self.lista_resultados.show()
        except Exception as e:
            print(f"Error mostrando productos: {e}")

    def eventFilter(self, obj, event):
        try:
            from PyQt5.QtCore import QEvent
            # Barcode scanner capture: accumulate fast keypresses globally while this widget is visible
            if event.type() == QEvent.KeyPress:
                try:
                    if self.isVisible() and self.window() and self.window().isActiveWindow():
                        key = event.key()
                        text = event.text()
                        now = time.monotonic()
                        # Enter -> try to process buffer
                        if key in (Qt.Key_Return, Qt.Key_Enter):
                            if getattr(self, "_barcode_buf", ""):
                                buf = getattr(self, "_barcode_buf", "")
                                last_delta = getattr(self, "_barcode_last_delta", None)
                                # Process as barcode if buffer is long enough OR timing suggests scanner
                                if len(buf) >= getattr(self, "_barcode_min_length", 3) or (last_delta is not None and last_delta < getattr(self, "_barcode_max_inter_key", 0.15)):
                                    code = buf
                                    QTimer.singleShot(0, lambda c=code: self._process_barcode(c))
                                    self._barcode_buf = ""
                                    self._barcode_last_ts = None
                                    self._barcode_last_delta = None
                                    return True
                                else:
                                    # Not a scanner input; reset buffer
                                    self._barcode_buf = ""
                                    self._barcode_last_ts = None
                                    self._barcode_last_delta = None
                        else:
                            if text and len(text) == 1:
                                if not getattr(self, "_barcode_last_ts", None):
                                    self._barcode_buf = text
                                    self._barcode_last_ts = now
                                    self._barcode_last_delta = None
                                else:
                                    delta = now - self._barcode_last_ts
                                    if delta > getattr(self, "_barcode_reset_timeout", 0.9):
                                        self._barcode_buf = text
                                    else:
                                        self._barcode_buf = getattr(self, "_barcode_buf", "") + text
                                    self._barcode_last_delta = delta
                                    self._barcode_last_ts = now
                except Exception:
                    pass
            # existing behavior: show all products when focusing or clicking search input
            if obj is self.search_input and event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
                self._mostrar_todos_productos()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _process_barcode(self, code):
        try:
            code = str(code).strip()
            if not code:
                return
            # try DB lookup
            prod = None
            try:
                prod = self.db.get_producto_by_codigo(code)
            except Exception:
                prod = None
            if not prod:
                # fallback to in-memory list
                for p in (self.productos_db or []):
                    if (p.get('codigo') or '').strip().lower() == code.lower():
                        prod = p
                        break
            if not prod:
                print(f"Barcode not found: {code}")
                return
            # select and add with quantity 1
            self.producto_seleccionado = prod
            try:
                self.card_producto.show()
                self.btn_agregar.setEnabled(True)
            except Exception:
                pass
            nombre = prod.get('nombre', 'Sin nombre')
            stock = float(prod.get('stock', 0) or 0)
            unidad = prod.get('unidad', 'und')
            try:
                self.lbl_prod_nombre.setText(nombre)
                self.lbl_prod_stock.setText(f"{stock:.3f} {unidad}")
                # If this widget is configured to include_out_of_stock (used by Compras), allow large quantities
                if getattr(self, 'include_out_of_stock', False):
                    self.spin_cantidad.setMaximum(999999)
                else:
                    self.spin_cantidad.setMaximum(stock)
                self.lbl_prod_depto.setText(prod.get('departamento', 'Sin departamento'))
                self._actualizar_precio_producto()
                self._cargar_imagen_producto(prod)
                # set qty 1 and add
                self.spin_cantidad.setValue(1)
                self._agregar_al_carrito()
            except Exception as e:
                print('Error al agregar producto escaneado:', e)
        except Exception as e:
            print('Error procesando barcode:', e)

    def _barcode_check_tick(self):
        try:
            buf = getattr(self, "_barcode_buf", "")
            last_ts = getattr(self, "_barcode_last_ts", None)
            if buf and last_ts:
                now = time.monotonic()
                if (now - last_ts) > getattr(self, "_barcode_reset_timeout", 0.9):
                    if len(buf) >= getattr(self, "_barcode_min_length", 3):
                        QTimer.singleShot(0, lambda c=buf: self._process_barcode(c))
                    # reset buffer after processing or timeout
                    self._barcode_buf = ""
                    self._barcode_last_ts = None
                    self._barcode_last_delta = None
        except Exception:
            pass

    def _ensure_search_focus(self):
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if not app:
                return
            # Only ensure focus when the sales widget is visible and its window is active
            if not self.isVisible():
                return
            win = self.window()
            if not win or not win.isActiveWindow():
                return
            try:
                fw = app.focusWidget()
            except Exception:
                fw = None
            # If search_input already has focus, nothing to do
            if fw is self.search_input:
                return
            # Do not steal focus if the user is editing another input (spinbox, lineedit, combo, text)
            try:
                from PyQt5.QtWidgets import QLineEdit, QAbstractSpinBox, QComboBox, QTextEdit, QPlainTextEdit
                if isinstance(fw, (QLineEdit, QAbstractSpinBox, QComboBox, QTextEdit, QPlainTextEdit)):
                    return
            except Exception:
                pass
            # Force focus so barcode scanners always type into the search box (fallback)
            try:
                self.search_input.setFocus()
                try:
                    self.search_input.selectAll()
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_producto_seleccionado_lista(self, item):
        producto = item.data(Qt.UserRole)
        if not producto:
            return
        self.producto_seleccionado = producto
        self.card_producto.show()
        self.btn_agregar.setEnabled(True)
        self.lista_resultados.hide()
        nombre = producto.get('nombre', 'Sin nombre')
        self.lbl_prod_nombre.setText(nombre)
        stock = float(producto.get('stock', 0) or 0)
        unidad = producto.get('unidad', 'und')
        self.lbl_prod_stock.setText(f"{stock:.3f} {unidad}")
        # Allow quantity entry when used for compras (include_out_of_stock=True) — allow large quantities
        if getattr(self, 'include_out_of_stock', False):
            max_qty = 999999
        else:
            max_qty = stock if stock > 0 else 0
        self.spin_cantidad.setMaximum(max_qty)
        self.lbl_prod_depto.setText(producto.get('departamento', 'Sin departamento'))
        self._actualizar_precio_producto()
        self._cargar_imagen_producto(producto)
        self.spin_cantidad.setFocus()
        self.spin_cantidad.selectAll()

    def _actualizar_precio_producto(self):
        if not self.producto_seleccionado:
            return
        try:
            precio_usd = float(self.producto_seleccionado.get('precio_final', 0) or 0)
            if self.tasa_bcv and precio_usd > 0:
                precio_bs = precio_usd * self.tasa_bcv
                self.lbl_prod_precio.setText(f"{precio_bs:,.2f} Bs")
            else:
                self.lbl_prod_precio.setText(f"{precio_usd:.4f} $")
        except Exception as e:
            print(f"Error actualizando precio: {e}")
            self.lbl_prod_precio.setText("Error")

    def _cargar_imagen_producto(self, producto):
        try:
            img_path = producto.get('imagen')
            if img_path and os.path.exists(img_path):
                pix = QPixmap(img_path)
                if not pix.isNull():
                    scaled = pix.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.lbl_prod_imagen.setPixmap(scaled)
                    self.lbl_prod_imagen.setText("")
                else:
                    self.lbl_prod_imagen.setText("📷")
                    self.lbl_prod_imagen.setPixmap(QPixmap())
            else:
                self.lbl_prod_imagen.setText("📷")
                self.lbl_prod_imagen.setPixmap(QPixmap())
        except Exception as e:
            print(f"Error cargando imagen: {e}")
            self.lbl_prod_imagen.setText("📷")

    def _agregar_al_carrito(self):
        if not self.producto_seleccionado:
            return
        try:
            cantidad = self.spin_cantidad.value()
            stock = float(self.producto_seleccionado.get('stock', 0) or 0)
            if cantidad > stock:
                QMessageBox.warning(self, "Stock insuficiente", f"Solo hay {stock:.3f} disponibles")
                return
            precio_usd = float(self.producto_seleccionado.get('precio_final', 0) or 0)
            iva_pct = float(self.producto_seleccionado.get('iva', 16))
            if not self.tasa_bcv:
                QMessageBox.critical(self, "Error", "No hay tasa BCV disponible")
                return
            precio_bs = precio_usd * self.tasa_bcv
            for i, item in enumerate(self.carrito):
                if item['id'] == self.producto_seleccionado.get('id'):
                    nueva_cantidad = item['cantidad'] + cantidad
                    if nueva_cantidad > stock:
                        QMessageBox.warning(self, "Stock insuficiente",
                                          f"Ya tiene {item['cantidad']} en carrito")
                        return
                    item['cantidad'] = nueva_cantidad
                    item['subtotal_bs'] = nueva_cantidad * precio_bs
                    item['precio_unitario_usd'] = precio_usd
                    item['iva'] = iva_pct
                    self._actualizar_cards_carrito()
                    self._calcular_totales()
                    return
            nuevo_item = {
                'id': self.producto_seleccionado.get('id'),
                'codigo': self.producto_seleccionado.get('codigo', 'N/A'),
                'nombre': self.producto_seleccionado.get('nombre', 'Sin nombre'),
                'cantidad': cantidad,
                'unidad': self.producto_seleccionado.get('unidad', 'und'),
                'precio_unitario_usd': precio_usd,
                'precio_unitario_bs': precio_bs,
                'iva': iva_pct,
                'subtotal_bs': cantidad * precio_bs,
                'imagen': self.producto_seleccionado.get('imagen'),
                'stock_original': stock
            }
            self.carrito.append(nuevo_item)
            self._actualizar_cards_carrito()
            self._calcular_totales()
            self.search_input.clear()
            self.lista_resultados.hide()
            self.spin_cantidad.setValue(1)
        except Exception as e:
            print(f"Error agregando al carrito: {e}")
            QMessageBox.critical(self, "Error", f"Error al agregar producto: {e}")

    def _handle_search_return(self):
        try:
            if hasattr(self, 'lista_resultados') and self.lista_resultados.isVisible() and self.lista_resultados.count() > 0:
                item = self.lista_resultados.item(0)
                if item:
                    # Select first result
                    self._on_producto_seleccionado_lista(item)
                    # If the input likely came from a barcode scanner (fast Enter), add 1 unit automatically
                    try:
                        self.spin_cantidad.setValue(1)
                        self._agregar_al_carrito()
                    except Exception:
                        pass
                    return
            if hasattr(self, 'card_producto') and self.card_producto.isVisible() and hasattr(self, 'btn_agregar') and self.btn_agregar.isEnabled():
                self._agregar_al_carrito()
        except Exception:
            pass

    def _construir_html_factura(self, venta_data):
        company = "Empresa"
        rif = ""
        try:
            if hasattr(self, 'parent_dashboard') and self.parent_dashboard is not None:
                try:
                    company = self.parent_dashboard.left_company_name.text()
                    rif = self.parent_dashboard.left_company_rif.text()
                except Exception:
                    pass
        except Exception:
            pass
        fecha = venta_data.get('fecha_hora', '')
        numero = venta_data.get('numero_factura', '')
        productos = venta_data.get('productos', [])
        pagos = venta_data.get('pagos', [])
        cambio = venta_data.get('cambio', 0.0)
        totales = venta_data.get('totales', {})
        total_bs = totales.get('total_bs', 0.0)

        html = f"""
        <html>
        <head>
        <meta charset='utf-8'>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 12px; color:#222 }}
            .header {{ text-align: left; margin-bottom: 12px }}
            table {{ width:100%; border-collapse: collapse; margin-top: 8px }}
            th, td {{ border:1px solid #DDD; padding:6px; text-align:left }}
            th {{ background:#F5F5F5 }}
        </style>
        </head>
        <body>
        <div class='header'>
            <h2>{company}</h2>
            <div>RIF: {rif}</div>
            <div>{'Registro de Salida' if getattr(self, 'modo', 'Venta') == 'Salida' else 'Registro de venta'}: {numero}</div>
            <div>Fecha: {fecha}</div>
        </div>
        <table>
            <tr><th>Código</th><th>Producto</th><th>Cantidad</th><th>Precio (Bs)</th><th>IVA (%)</th><th>IVA (Bs)</th><th>Subtotal (Bs)</th></tr>
        """
        for p in productos:
            codigo = p.get('codigo','')
            nombre = p.get('nombre','')
            cantidad = p.get('cantidad')
            precio_unit_bs = float(p.get('precio_unitario_bs') or 0.0)
            iva_pct = float(p.get('iva') or 0.0)
            precio_sin_iva = precio_unit_bs / (1 + iva_pct/100) if iva_pct else precio_unit_bs
            iva_unit_bs = precio_unit_bs - precio_sin_iva
            subtotal = p.get('subtotal_bs',0.0)
            html += f"<tr><td>{codigo}</td><td>{nombre}</td><td>{cantidad}</td><td>{precio_unit_bs:,.2f}</td><td>{iva_pct:.2f}%</td><td>{iva_unit_bs:,.2f}</td><td>{float(subtotal):,.2f}</td></tr>"
        html += f"</table><h3>Subtotal: {float(totales.get('subtotal_bs',0)):,.2f} Bs</h3><h3>IVA: {float(totales.get('iva_bs',0)):,.2f} Bs</h3><h2>Total: {float(total_bs):,.2f} Bs</h2>"
        if pagos:
            html += "<h4>Pagos:</h4><ul>"
            for pay in pagos:
                html += f"<li>{pay.get('metodo')}: {pay.get('monto',0.0)} ({pay.get('referencia','')})</li>"
            html += "</ul>"
        html += f"<div>Cambio: {float(cambio):,.2f} Bs</div>"
        html += "</body></html>"
        return html

    def _guardar_factura_pdf(self, venta_data):
            try:
                import os
                import datetime
                import re
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont

                # 1. Ruta base y nombre de archivo (usar configuración si existe)
                try:
                    from modules import config as app_config
                    pdf_base = app_config.get_pdf_dir()
                except Exception:
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                    pdf_base = os.path.join(base_dir, 'registros')
                invoices_root = os.path.abspath(pdf_base)
                os.makedirs(invoices_root, exist_ok=True)
                ym = datetime.datetime.now().strftime('%Y-%m')
                invoices_dir = os.path.join(invoices_root, ym)
                os.makedirs(invoices_dir, exist_ok=True)

                # 2. Datos de encabezado (empresa, RIF) — preferir configuración del instalador
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

                # 3. Configuración de estilos/fonts
                try:
                    pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
                    font_main = "DejaVu"
                except Exception:
                    font_main = "Helvetica"

                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(
                    name="Header", fontName=font_main, fontSize=15, alignment=1, spaceAfter=8,
                    spaceBefore=4, textColor=colors.HexColor("#5E3DB3")))
                styles.add(ParagraphStyle(
                    name="Meta", fontName=font_main, fontSize=10, alignment=0))
                styles.add(ParagraphStyle(
                    name="TableCell", fontName=font_main, fontSize=10, spaceAfter=2, spaceBefore=2))
                styles.add(ParagraphStyle(
                    name="TableCellBold", fontName=font_main, fontSize=10,
                    spaceAfter=2, spaceBefore=2, textColor=colors.HexColor("#5E3DB3")))
                styles.add(ParagraphStyle(
                    name="Total", fontName=font_main, fontSize=12, spaceAfter=3,
                    spaceBefore=8, alignment=2, textColor=colors.HexColor("#00C853")))

                doc = SimpleDocTemplate(filepath, pagesize=A4,
                                       leftMargin=32, rightMargin=32, topMargin=28, bottomMargin=22)
                elements = []

                # 4. Encabezado de la factura
                elements.append(Paragraph(f"<b>{company}</b>", styles["Header"]))
                elements.append(Paragraph(f"RIF: {rif}", styles["Meta"]))
                cliente = venta_data.get("cliente", {})
                elements.append(Paragraph(
                    f"Cliente: {cliente.get('nombre', 'General')} | "
                    f"Cédula/RIF: {cliente.get('cedula', 'N/A')}", styles["Meta"]))
                elements.append(Paragraph(
                    f"Fecha: {venta_data.get('fecha_hora', '')}   |   "
                    f"{('Registro de Salida' if getattr(self, 'modo', 'Venta') == 'Salida' else 'Registro de venta')}: <b>{venta_data.get('numero_factura', '')}</b>", styles["Meta"]))
                elements.append(Spacer(1, 12))

                # 5. Tabla de productos
                productos = venta_data.get('productos', [])
                tabla_data = [
                    [Paragraph("<b>Código</b>", styles["TableCellBold"]),
                     Paragraph("<b>Nombre</b>", styles["TableCellBold"]),
                     Paragraph("<b>Cant.</b>", styles["TableCellBold"]),
                     Paragraph("<b>Precio (Bs)</b>", styles["TableCellBold"]),
                     Paragraph("<b>IVA (%)</b>", styles["TableCellBold"]),
                     Paragraph("<b>IVA (Bs)</b>", styles["TableCellBold"]),
                     Paragraph("<b>Subtotal (Bs)</b>", styles["TableCellBold"])]
                ]
                for p in productos:
                    precio_unit_bs = float(p.get('precio_unitario_bs') or 0.0)
                    iva_pct = float(p.get('iva') or 0.0)
                    precio_sin_iva = precio_unit_bs / (1 + iva_pct/100) if iva_pct else precio_unit_bs
                    iva_unit_bs = precio_unit_bs - precio_sin_iva
                    tabla_data.append([
                        Paragraph(str(p.get('codigo', '')), styles["TableCell"]),
                        Paragraph(str(p.get('nombre', '')), styles["TableCell"]),
                        Paragraph(f"{float(p.get('cantidad')):,.2f}", styles["TableCell"]),
                        Paragraph(f"{precio_unit_bs:,.2f}", styles["TableCell"]),
                        Paragraph(f"{iva_pct:.2f}%", styles["TableCell"]),
                        Paragraph(f"{iva_unit_bs:,.2f}", styles["TableCell"]),
                        Paragraph(f"{float(p.get('subtotal_bs')):,.2f}", styles["TableCell"])
                    ])

                tabla = Table(tabla_data, colWidths=[56, 170, 46, 72, 72])
                tabla.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBB")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE7F6")),
                    ("FONTNAME", (0, 0), (-1, -1), font_main),
                    ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (4, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5)
                ]))
                elements.append(tabla)
                elements.append(Spacer(1, 10))

                # 6. Totales/resumen
                totales = venta_data.get('totales', {})
                elements.append(Paragraph(
                    f"<b>Subtotal:</b> {float(totales.get('subtotal_bs', 0)):,.2f} Bs", styles["TableCell"]))
                elements.append(Paragraph(
                    f"<b>IVA:</b> {float(totales.get('iva_bs', 0)):,.2f} Bs", styles["TableCell"]))
                if totales.get('descuento_bs', 0):
                    elements.append(Paragraph(
                        f"<b>Descuento:</b> {float(totales.get('descuento_bs', 0)):,.2f} Bs", styles["TableCell"]))
                elements.append(Paragraph(
                    f"<b>TOTAL COMPRA:</b>  "
                    f"<font color='#00C853'><b>{float(totales.get('total_bs', 0)):,.2f} Bs</b></font>",
                    styles["Total"]))

                # 7. Pago (desglose)
                pagos = venta_data.get('pagos', [])
                if pagos:
                    elements.append(Spacer(1, 8))
                    elements.append(Paragraph("<b>Métodos de Pago:</b>", styles["TableCellBold"]))
                    tabla_pagos_data = [["Método", "Monto (Bs)", "Referencia"]]
                    for p in pagos:
                        monto_pago = float(p.get('monto_bs', p.get('monto', 0)))
                        tabla_pagos_data.append([
                            Paragraph(str(p.get('metodo', '')), styles["TableCell"]),
                            Paragraph(f"{monto_pago:,.2f}", styles["TableCell"]),
                            Paragraph(str(p.get('referencia', '')), styles["TableCell"])
                        ])
                    tabla_pagos = Table(tabla_pagos_data, colWidths=[96, 68, 180])
                    tabla_pagos.setStyle(TableStyle([
                        ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#DDDDDD")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF3E0")),
                        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ]))
                    elements.append(tabla_pagos)

                # 8. Cambio si aplica
                elements.append(Spacer(1, 7))
                cambio = venta_data.get('cambio', 0.0)
                if cambio and cambio > 0.01:
                    elements.append(Paragraph(
                        f"<b>Cambio entregado:</b> {float(cambio):,.2f} Bs", styles["TableCell"]))

                # 9. Pie final
                elements.append(Spacer(1, 14))


                # 10. Generar PDF
                doc.build(elements)
                print(f"Registro guardado: {filepath}")

            except Exception as e:
                print(f"Error guardando PDF de registro: {e}")
    
    def _on_cierre_diario(self):
        try:
            from modules.cierre_diario import DialogoCierreDiario
            dlg = DialogoCierreDiario(self.db, parent=self, tipo='Salida', title='Salidas del día')
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Cierre Diario", f"No se pudo abrir Cierre Diario: {e}")

    def _actualizar_cards_carrito(self):
        widgets_to_delete = []
        empty_present = False
        for i in range(self.layout_carrito.count()):
            item = self.layout_carrito.itemAt(i)
            if not item:
                continue
            w = item.widget()
            if not w:
                continue
            if w is self.lbl_carrito_vacio:
                empty_present = True
                continue
            widgets_to_delete.append(w)
        for w in widgets_to_delete:
            try:
                self.layout_carrito.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass
        if not self.carrito:
            if not empty_present:
                try:
                    self.layout_carrito.insertWidget(0, self.lbl_carrito_vacio)
                except Exception:
                    pass
            self.lbl_carrito_vacio.show()
            self.btn_siguiente.setEnabled(False)
        else:
            if empty_present:
                try:
                    self.layout_carrito.removeWidget(self.lbl_carrito_vacio)
                except Exception:
                    pass
            self.lbl_carrito_vacio.hide()
            for i, item_data in enumerate(self.carrito):
                try:
                    card = ProductoCard(i, item_data, self.container_carrito)
                    card.cantidad_cambiada.connect(self._on_cantidad_cambiada)
                    card.eliminar_solicitado.connect(self._eliminar_item)
                    self.layout_carrito.insertWidget(i, card)
                except Exception as e:
                    print(f"Error creando card: {e}")
            self.btn_siguiente.setEnabled(True)

    def _on_cantidad_cambiada(self, index, nueva_cantidad):
        if 0 <= index < len(self.carrito):
            item = self.carrito[index]
            stock_max = item.get('stock_original', 999999)
            if nueva_cantidad > stock_max:
                QMessageBox.warning(self, "Stock insuficiente", f"Máximo disponible: {stock_max}")
                self._actualizar_cards_carrito()
                return
            item['cantidad'] = nueva_cantidad
            item['subtotal_bs'] = nueva_cantidad * item['precio_unitario_bs']
            # Update the visual card subtotal if present
            try:
                w = None
                # layout_carrito widgets are inserted in the same order as self.carrito
                it = self.layout_carrito.itemAt(index)
                if it:
                    w = it.widget()
                if w and hasattr(w, 'actualizar_subtotal'):
                    try:
                        w.actualizar_subtotal(nueva_cantidad)
                    except Exception:
                        pass
            except Exception:
                pass
            self._calcular_totales()

    def _eliminar_item(self, index):
        if 0 <= index < len(self.carrito):
            del self.carrito[index]
            self._actualizar_cards_carrito()
            self._calcular_totales()

    def _calcular_totales(self):
        try:
            subtotal = 0.0
            iva_total = 0.0
            total = 0.0
            tasa_bcv = self.tasa_bcv if self.tasa_bcv else 0.0

            for item in self.carrito:
                precio_final_usd = float(item.get('precio_unitario_usd', 0.0))
                iva_pct = float(item.get('iva', 16))
                cantidad = float(item.get('cantidad', 0.0))

                precio_sin_iva_usd = precio_final_usd / (1 + iva_pct / 100)
                iva_unit_usd = precio_final_usd - precio_sin_iva_usd

                precio_sin_iva_bs = precio_sin_iva_usd * tasa_bcv
                iva_unit_bs = iva_unit_usd * tasa_bcv
                precio_final_bs = precio_final_usd * tasa_bcv

                subtotal += precio_sin_iva_bs * cantidad
                iva_total += iva_unit_bs * cantidad
                total += precio_final_bs * cantidad

            descuento_pct = self.spin_descuento.value() if hasattr(self, 'spin_descuento') else 0.0
            descuento = (subtotal + iva_total) * (descuento_pct / 100)
            total_final = total - descuento

            self.val_subtotal.setText(f"{subtotal:,.2f}")
            self.val_iva.setText(f"{iva_total:,.2f}")
            self.val_descuento.setText(f"{descuento:,.2f}")
            self.val_total.setText(f"{total_final:,.2f} Bs")

            if tasa_bcv > 0:
                total_usd = total_final / tasa_bcv
                self.val_usd.setText(f"≈ {total_usd:.2f} $")
            else:
                self.val_usd.setText("≈ -- $")

            self.totales = {
                'subtotal_bs': subtotal,
                'iva_bs': iva_total,
                'descuento_pct': descuento_pct,
                'descuento_bs': descuento,
                'total_bs': total_final
            }
        except Exception as e:
            print(f"Error calculando totales: {e}")

    def _abrir_dialogo_pago(self):
        if not self.carrito or not self.totales:
            return
        try:
            from modules.metodo_pago import DialogoMetodosPago
            total_bs = self.totales['total_bs']
            total_usd = self.totales['total_bs'] / self.tasa_bcv if self.tasa_bcv else 0
            dialogo = DialogoMetodosPago(
                total_bs=total_bs,
                total_usd=total_usd,
                tasa_bcv=self.tasa_bcv,
                parent=self
            )
            if dialogo.exec_() == DialogoMetodosPago.Accepted:
                resultado = dialogo.get_resultado()
                if resultado['pagado']:
                    self._completar_venta(resultado)
        except Exception as e:
            print(f"Error en diálogo de pago: {e}")
            QMessageBox.critical(self, "Error", f"Error en pago: {e}")

    def _completar_venta(self, resultado_pago):
        try:
            venta_data = {
                'numero_factura': self.numero_factura,
                'fecha_hora': datetime.datetime.now().isoformat(),
                'cliente': self.cliente_actual or {'nombre': 'General', 'cedula': 'N/A'},
                'productos': self.carrito.copy(),
                'totales': self.totales,
                'pagos': resultado_pago['detalle_pagos'],
                'cambio': resultado_pago['cambio'],
                'tasa_bcv': self.tasa_bcv
            }
            for item in self.carrito:
                self.db.insert_movimiento(
                    tipo="Salida",
                    producto_id=item['id'],
                    cantidad=item['cantidad'],
                    costo=item['subtotal_bs'],
                    imagen=item.get('imagen'),
                    motivo=f"Venta {self.numero_factura}"
                )
            self.venta_completada.emit(venta_data)
            QMessageBox.information(
                self,
                ("✅ Salida Completada" if getattr(self, 'modo', 'Venta') == 'Salida' else "✅ Venta Completada"),
                (f"Registro de salida {self.numero_factura} procesado exitosamente\n" if getattr(self, 'modo', 'Venta') == 'Salida' else f"Registro de venta {self.numero_factura} procesado exitosamente\n")
                + f"Total: {self.totales['total_bs']:,.2f} Bs"
            )
            try:
                self._guardar_factura_pdf(venta_data)
            except Exception as e:
                print(f"Error guardando PDF de registro: {e}")
            QTimer.singleShot(0, self._nueva_venta)
        except Exception as e:
            print(f"Error completando venta: {e}")
            QMessageBox.critical(self, "Error", f"Error al completar venta: {e}")

    def _seleccionar_cliente(self, manager_type='clientes'):
        """manager_type: 'clientes' or 'proveedores' - selects dialog implementation dynamically"""
        try:
            if manager_type == 'proveedores':
                from modules.proveedores_manager import DialogoProveedores as DialogoManager
                dialog = DialogoManager(self, self.cliente_actual)
                dialog.proveedor_seleccionado.connect(self._on_cliente_seleccionado)
            else:
                from modules.clientes_manager import DialogoClientesFrecuentes as DialogoManager
                dialog = DialogoManager(self, self.cliente_actual)
                dialog.cliente_seleccionado.connect(self._on_cliente_seleccionado)
            if dialog.exec_() == DialogoManager.Accepted:
                pass
        except Exception as e:
            print(f"Error abriendo gestor ({manager_type}): {e}")
            nombre, ok = QInputDialog.getText(self, "Cliente/Proveedor", "Nombre:")
            if ok and nombre:
                cedula, ok2 = QInputDialog.getText(self, "Cliente/Proveedor", "Cédula (opcional):")
                self.cliente_actual = {
                    'nombre': nombre,
                    'cedula': cedula if ok2 and cedula else 'N/A'
                }
                self.lbl_cliente.setText(f"👤 {nombre[:20]}")

    def _on_cliente_seleccionado(self, cliente):
        self.cliente_actual = cliente
        nombre = cliente.get('nombre', 'General')
        cedula = cliente.get('cedula', 'N/A')
        display = f"👤 {nombre[:15]}"
        if cedula and cedula != 'N/A':
            display += f" ({cedula})"
        self.lbl_cliente.setText(display)
        self.lbl_cliente.setToolTip(f"{nombre}\nCédula: {cedula}")
        print(f"Cliente seleccionado: {nombre} - {cedula}")

    def _nueva_venta(self):
        self.carrito = []
        self.cliente_actual = None
        self.numero_factura = self._generar_factura()
        self.totales = None
        try:
            lbl_factura = getattr(self, 'lbl_factura', None)
            lbl_cliente = getattr(self, 'lbl_cliente', None)
            if lbl_factura is not None:
                try:
                    import sip
                    if not sip.isdeleted(lbl_factura):
                        if getattr(self, 'modo', 'Venta') == 'Salida':
                            lbl_factura.setText('Registro de Salidas')
                        else:
                            lbl_factura.setText(f"Registro de venta {self.numero_factura}")
                except Exception:
                    try:
                        if getattr(self, 'modo', 'Venta') == 'Salida':
                            lbl_factura.setText('Registro de Salidas')
                        else:
                            lbl_factura.setText(f"Registro de venta {self.numero_factura}")
                    except Exception:
                        pass
            if lbl_cliente is not None:
                try:
                    import sip
                    if not sip.isdeleted(lbl_cliente):
                        lbl_cliente.setText("👤 Cliente General")
                except Exception:
                    try:
                        lbl_cliente.setText("👤 Cliente General")
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            QTimer.singleShot(0, self._refresh_ui_post_sale)
        except Exception:
            try:
                self._refresh_ui_post_sale()
            except Exception:
                pass

    def _refresh_ui_post_sale(self):
        try:
            self._actualizar_cards_carrito()
        except Exception as e:
            print(f"Error updating cart UI post sale: {e}")
        try:
            self._calcular_totales()
        except Exception as e:
            print(f"Error calculating totals post sale: {e}")
        try:
            self._cargar_productos()
        except Exception:
            pass

    def _cancelar_venta(self):
        if not self.carrito:
            self._volver_dashboard()
            return
        # Mensajes adaptados al modo (Venta/Salida)
        title = "Cancelar Salida" if getattr(self, 'modo', 'Venta') == 'Salida' else "Cancelar Venta"
        text = ("¿Está seguro de cancelar esta salida?\nSe perderán todos los productos del carrito." if getattr(self, 'modo', 'Venta') == 'Salida' 
                else "¿Está seguro de cancelar esta venta?\nSe perderán todos los productos del carrito.")
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        btn_si = msg.addButton("Sí", QMessageBox.YesRole)
        btn_no = msg.addButton("No", QMessageBox.NoRole)
        msg.setDefaultButton(btn_si)
        msg.exec_()
        if msg.clickedButton() == btn_si:
            self._nueva_venta()

    def _volver_dashboard(self):
        if self.carrito:
            mode = getattr(self, 'modo', 'Venta')
            text = "Hay productos en el carrito. ¿Desea salir sin completar la salida?" if mode == 'Salida' else "Hay productos en el carrito. ¿Desea salir sin completar la venta?"
            msg = QMessageBox(self)
            msg.setWindowTitle("Salir")
            msg.setText(text)
            btn_si = msg.addButton("Sí", QMessageBox.YesRole)
            btn_no = msg.addButton("No", QMessageBox.NoRole)
            msg.setDefaultButton(btn_si)
            msg.exec_()
            if msg.clickedButton() != btn_si:
                return
        # Detener timer de tasa si existe
        try:
            if hasattr(self, 'timer_tasa') and self.timer_tasa:
                self.timer_tasa.stop()
        except Exception:
            pass
        if self.parent_dashboard and hasattr(self.parent_dashboard, 'restore_dashboard_view'):
            self.parent_dashboard.restore_dashboard_view()
        else:
            self.volver_solicitado.emit()

    def _generar_factura(self):
        fecha = datetime.datetime.now()
        return f"REG-{fecha:%Y%m%d-%H%M%S}"

    def closeEvent(self, event):
        try:
            if hasattr(self, 'timer_tasa') and self.timer_tasa:
                self.timer_tasa.stop()
        except Exception:
            pass
        event.accept()


