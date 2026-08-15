"""
Tarjetas de Producto para el Carrito — versión compacta
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QDoubleSpinBox, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap

import os
from modules.ventas_carrito_constants import *

class ProductoCard(QWidget):
    """Tarjeta visual de producto para el carrito - Versión compacta"""
    cantidad_cambiada = pyqtSignal(int, float)
    eliminar_solicitado = pyqtSignal(int)

    def __init__(self, index, item_data, parent=None):
        super().__init__(parent)
        self.index = index
        self.data = item_data
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE};
                border-radius: 10px;
                border: 1.2px solid {BORDER};
            }}
            QWidget:hover {{
                border: 1.5px solid {PRIMARY};
                background: {PRIMARY_LIGHT}10;
            }}
        """)
        # Sombra más sutil
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(107, 78, 214, 10))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)  # Reducido de 18,16,18,16
        layout.setSpacing(12)  # Reducido de 18
        try:
            from modules.ui_scaling import scale_px

            self.setMinimumHeight(scale_px(60))  # Reducido de 82
        except Exception:
            self.setMinimumHeight(60)  # Reducido de 82
        try:
            from modules.ui_scaling import scale_px

            self.setMaximumHeight(scale_px(75))
        except Exception:
            self.setMaximumHeight(75)

        # Imagen más pequeña
        self.lbl_img = QLabel()
        try:
            from modules.ui_scaling import scale_px

            self.lbl_img.setFixedSize(scale_px(45), scale_px(45))  # Reducido de 58,58
        except Exception:
            self.lbl_img.setFixedSize(45, 45)  # Reducido de 58,58
        self.lbl_img.setStyleSheet(f"""
            background: {BACKGROUND};
            border-radius: 8px;
            border: 1px solid {BORDER};
        """)
        self.lbl_img.setAlignment(Qt.AlignCenter)
        img_path = self.data.get('imagen')
        if img_path and os.path.exists(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                try:
                    from modules.ui_scaling import scale_px

                    scaled = pix.scaled(scale_px(42), scale_px(42), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                except Exception:
                    scaled = pix.scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_img.setPixmap(scaled)
        else:
            self.lbl_img.setText("📦")
            self.lbl_img.setStyleSheet(self.lbl_img.styleSheet() + "font-size: 22px; color: #C2C2C2;")

        layout.addWidget(self.lbl_img)

        # Info principal más compacta
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)  # Reducido de 5

        self.lbl_nombre = QLabel(self.data['nombre'])
        self.lbl_nombre.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {TEXT_PRIMARY};")
        self.lbl_nombre.setWordWrap(True)
        info_layout.addWidget(self.lbl_nombre)

        self.lbl_codigo = QLabel(f"{self.data['codigo']} • {self.data['precio_unitario_bs']:,.2f} Bs")
        self.lbl_codigo.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        info_layout.addWidget(self.lbl_codigo)

        layout.addLayout(info_layout, 3)

        # Cantidad más compacta
        cantidad_spin = QDoubleSpinBox()
        cantidad_spin.setDecimals(3)
        # Ensure maximum is sensible (avoid min>max when stock_original == 0)
        max_stock = self.data.get('stock_original', 999999)
        try:
            max_stock = float(max_stock) if max_stock is not None else 0.0
        except Exception:
            max_stock = 0.0
        if max_stock <= 0:
            max_stock = 9999
        cantidad_spin.setRange(0.001, max_stock)
        cantidad_spin.setValue(self.data['cantidad'])
        cantidad_spin.setSuffix(f" {self.data.get('unidad', 'und')}")
        # Step by whole units by default, allow decimals by typing
        cantidad_spin.setSingleStep(1)
        # Format display to hide trailing zeros when integer
        def _format_cantidad_display():
            try:
                v = cantidad_spin.value()
                if float(v).is_integer():
                    cantidad_spin.lineEdit().setText(str(int(round(v))))
                else:
                    txt = f"{v:.3f}".rstrip('0').rstrip('.')
                    cantidad_spin.lineEdit().setText(txt)
            except Exception:
                pass
        cantidad_spin.valueChanged.connect(lambda v: _format_cantidad_display())
        cantidad_spin.editingFinished.connect(_format_cantidad_display)
        try:
            _format_cantidad_display()
        except Exception:
            pass
        try:
            from modules.ui_scaling import scale_px

            cantidad_spin.setFixedWidth(scale_px(80))  # Reducido de 90
        except Exception:
            cantidad_spin.setFixedWidth(80)  # Reducido de 90
        try:
            from modules.ui_scaling import scale_px

            cantidad_spin.setFixedHeight(scale_px(28))  # Reducido de 34
        except Exception:
            cantidad_spin.setFixedHeight(28)  # Reducido de 34
        cantidad_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.2px solid {PRIMARY};
                border-radius: 6px;
                padding: 2px;
                font-size: 13px;
                background: {SURFACE};
            }}
        """)
        cantidad_spin.valueChanged.connect(lambda v: self.cantidad_cambiada.emit(self.index, v))
        layout.addWidget(cantidad_spin)

        # Subtotal más compacto
        self.lbl_subtotal = QLabel(f"{self.data['subtotal_bs']:,.2f}")
        self.lbl_subtotal.setStyleSheet(f"font-weight: bold; font-size: 15px; color: {PRIMARY_DARK};")
        self.lbl_subtotal.setAlignment(Qt.AlignRight)
        try:
            from modules.ui_scaling import scale_px

            self.lbl_subtotal.setFixedWidth(scale_px(75))  # Reducido de 89
        except Exception:
            self.lbl_subtotal.setFixedWidth(75)  # Reducido de 89
        layout.addWidget(self.lbl_subtotal)

        # Botón eliminar más pequeño
        btn_eliminar = QPushButton("✕")
        try:
            from modules.ui_scaling import scale_px

            btn_eliminar.setFixedSize(scale_px(24), scale_px(24))  # Reducido de 30,30
        except Exception:
            btn_eliminar.setFixedSize(24, 24)  # Reducido de 30,30
        btn_eliminar.setStyleSheet(f"""
            QPushButton {{
                background: #FFEEEE;
                border-radius: 6px;
                font-size: 16px;
                color: {DANGER};
                border: 1px solid {DANGER};
            }}
            QPushButton:hover {{
                background: {DANGER};
                color: #fff;
            }}
        """)
        btn_eliminar.clicked.connect(lambda: self.eliminar_solicitado.emit(self.index))
        layout.addWidget(btn_eliminar, alignment=Qt.AlignTop)

    def actualizar_subtotal(self, nueva_cantidad):
        nuevo_subtotal = nueva_cantidad * self.data['precio_unitario_bs']
        self.lbl_subtotal.setText(f"{nuevo_subtotal:,.2f}")
        return nuevo_subtotal

