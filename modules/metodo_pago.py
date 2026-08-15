from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QLineEdit, QPushButton,
    QCheckBox, QFrame, QGroupBox, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from decimal import Decimal

PRIMARY = "#6B4ED6"
PRIMARY_LIGHT = "#8E6BE6"
PRIMARY_DARK = "#5A3FC7"
ACCENT = "#00C853"
WARNING = "#FF9800"
DANGER = "#E25555"
BACKGROUND = "#F8F6FF"
SURFACE = "#FFFFFF"
TEXT_PRIMARY = "#333333"
TEXT_SECONDARY = "#666666"
BORDER = "#E8E3F5"

class DialogoMetodosPago(QDialog):
    """Diálogo emergente para seleccionar métodos de pago - profesional, modular"""
    def __init__(self, total_bs, total_usd, tasa_bcv, parent=None):
        super().__init__(parent)
        self.total_bs = Decimal(str(total_bs))
        self.total_usd = Decimal(str(total_usd)) if total_usd else Decimal('0')
        self.tasa_bcv = tasa_bcv
        self.pagado = False
        self.detalle_pagos = []
        self.cambio = Decimal('0')
        self.metodos_widgets = {}
        self.setWindowTitle("💳 Métodos de Pago")
        try:
            from modules.ui_scaling import scale_px

            self.setMinimumWidth(scale_px(450))
        except Exception:
            self.setMinimumWidth(450)
        try:
            from modules.ui_scaling import scale_px

            self.setMaximumWidth(scale_px(600))
        except Exception:
            self.setMaximumWidth(600)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {BACKGROUND};
            }}
            QGroupBox {{
                font-weight: 700;
                border: 2px solid {BORDER};
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                color: {PRIMARY};
            }}
            QCheckBox {{ font-size: 13px; font-weight: 600; color: {TEXT_PRIMARY}; spacing: 8px; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 5px; border: 2px solid {BORDER}; }}
            QCheckBox::indicator:checked {{ background: {PRIMARY}; border: 2px solid {PRIMARY}; }}
            QDoubleSpinBox {{ border: 2px solid {BORDER}; border-radius: 6px; padding: 6px; font-size: 13px; min-width: 100px; }}
            QLineEdit {{ border: 2px solid {BORDER}; border-radius: 6px; padding: 6px; font-size: 12px; }}
            QLabel {{ color: {TEXT_PRIMARY}; }}
        """)
        self._build_ui()
        self._actualizar_display()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)
        # Header
        header = QFrame()
        header.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PRIMARY}, stop:1 {PRIMARY_DARK}); border-radius: 12px;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(5)
        lbl_titulo = QLabel("Resumen de Pago")
        lbl_titulo.setStyleSheet("color: white; font-size: 17px; font-weight: 700;")
        header_layout.addWidget(lbl_titulo)
        self.lbl_total = QLabel(f"Total: {float(self.total_bs):,.2f} Bs")
        self.lbl_total.setStyleSheet("color: white; font-size: 22px; font-weight: 800;")
        header_layout.addWidget(self.lbl_total)
        if self.tasa_bcv and self.total_usd > 0:
            lbl_usd = QLabel(f"≈ {float(self.total_usd):,.4f} $ (Tasa: {self.tasa_bcv:,.2f})")
            lbl_usd.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px;")
            header_layout.addWidget(lbl_usd)
        main_layout.addWidget(header)
        # Métodos de pago
        metodos_config = [
            ("Efectivo Bs", "💵", True),
            ("Punto de Venta", "💳", False),
            ("Biopago", "📱", False),
            ("Pago Móvil", "📲", False),
            ("Efectivo USD", "💰", False),
            ("Transferencia", "🏦", False),
            ("Zelle", "🌐", False),
        ]
        metodos_group = QGroupBox("Método(s)")
        metodos_layout = QVBoxLayout(metodos_group)
        metodos_layout.setSpacing(8)
        for nombre, icono, activo in metodos_config:
            widget_metodo = self._crear_widget_metodo(nombre, icono)
            metodos_layout.addWidget(widget_metodo)
            if activo:
                self._activar_metodo(nombre)
        metodos_layout.addStretch()
        # Scroll para métodos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setWidget(metodos_group)
        main_layout.addWidget(scroll, 1)
        # Estado pago/resumen
        resumen_group = QGroupBox("Estado del Pago")
        resumen_layout = QHBoxLayout(resumen_group)
        resumen_layout.setSpacing(12)
        self.lbl_pagado = QLabel("Pagado: 0.00 Bs")
        self.lbl_pagado.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_PRIMARY};")
        resumen_layout.addWidget(self.lbl_pagado)
        self.lbl_restante = QLabel(f"Restante: {float(self.total_bs):,.2f} Bs")
        self.lbl_restante.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {WARNING};")
        resumen_layout.addWidget(self.lbl_restante)
        self.lbl_cambio = QLabel("")
        self.lbl_cambio.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {ACCENT};")
        self.lbl_cambio.hide()
        resumen_layout.addWidget(self.lbl_cambio)
        main_layout.addWidget(resumen_group)
        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_cancelar = QPushButton("❌ Cancelar")
        btn_cancelar.setStyleSheet(f"background: transparent; color: {DANGER}; border: 2px solid {DANGER}; border-radius: 8px; padding: 7px 19px; font-size: 13px;")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)
        btn_layout.addStretch()
        self.btn_completar = QPushButton("✅ Completar")
        self.btn_completar.setEnabled(False)
        self.btn_completar.setStyleSheet(f"background: {ACCENT}; color: white; border-radius: 8px; padding: 8px 30px;font-size:13px; font-weight:700;")
        self.btn_completar.clicked.connect(self._completar)
        btn_layout.addWidget(self.btn_completar)
        main_layout.addLayout(btn_layout)

    def _crear_widget_metodo(self, nombre, icono):
        frame = QFrame()
        frame.setStyleSheet(f"background: {SURFACE}; border-radius: 8px; border: 1px solid {BORDER};")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
        check = QCheckBox(f"{icono} {nombre}")
        check.setStyleSheet("font-size: 13px; font-weight: 600;")
        check.stateChanged.connect(lambda state, n=nombre: self._on_check_changed(n, state))
        layout.addWidget(check, 1)
        input_monto = QDoubleSpinBox()
        input_monto.setDecimals(2)
        input_monto.setRange(0, 999999999.99)
        input_monto.setSuffix(" $" if ("USD" in nombre or nombre.strip().lower() == "zelle") else " Bs")
        input_monto.setEnabled(False)
        try:
            from modules.ui_scaling import scale_px

            input_monto.setFixedWidth(scale_px(110))
        except Exception:
            input_monto.setFixedWidth(110)
        input_monto.valueChanged.connect(self._recalcular)
        layout.addWidget(input_monto)
        input_ref = QLineEdit()
        input_ref.setPlaceholderText("Ref." if "Efectivo" in nombre else "Ref. *")
        input_ref.setEnabled(False)
        try:
            from modules.ui_scaling import scale_px

            input_ref.setFixedWidth(scale_px(100))
        except Exception:
            input_ref.setFixedWidth(100)
        input_ref.textChanged.connect(self._recalcular)
        layout.addWidget(input_ref)
        self.metodos_widgets[nombre] = {
            'check': check,
            'monto': input_monto,
            'referencia': input_ref,
            'frame': frame
        }
        return frame

    def _on_check_changed(self, nombre, state):
        if nombre not in self.metodos_widgets:
            return
        widgets = self.metodos_widgets[nombre]
        activo = state == Qt.Checked
        widgets['monto'].setEnabled(activo)
        widgets['referencia'].setEnabled(activo)
        if activo:
            widgets['frame'].setStyleSheet(f"background: #EDE7F6; border-radius: 8px; border: 2px solid {PRIMARY};")
            restante = self._calcular_restante()
            if restante > 0:
                widgets['monto'].setValue(float(restante))
            widgets['monto'].setFocus()
            widgets['monto'].selectAll()
        else:
            widgets['frame'].setStyleSheet(f"background: {SURFACE}; border-radius: 8px; border: 1px solid {BORDER};")
            widgets['monto'].setValue(0)
        self._recalcular()

    def _activar_metodo(self, nombre):
        if nombre in self.metodos_widgets:
            self.metodos_widgets[nombre]['check'].setChecked(True)

    def _calcular_restante(self):
        total_pagado = Decimal('0')
        for nombre, widgets in self.metodos_widgets.items():
            if widgets['check'].isChecked():
                monto = Decimal(str(widgets['monto'].value()))
                if ("USD" in nombre or nombre.strip().lower() == "zelle") and self.tasa_bcv:
                    monto = monto * Decimal(str(self.tasa_bcv))
                total_pagado += monto
        return max(Decimal('0'), self.total_bs - total_pagado)

    def _recalcular(self):
        total_pagado = Decimal('0')
        detalle = []
        for nombre, widgets in self.metodos_widgets.items():
            if widgets['check'].isChecked():
                monto = Decimal(str(widgets['monto'].value()))
                ref = widgets['referencia'].text().strip()
                monto_bs = monto
                if ("USD" in nombre or nombre.strip().lower() == "zelle") and self.tasa_bcv:
                    monto_bs = monto * Decimal(str(self.tasa_bcv))
                total_pagado += monto_bs
                if monto > 0:
                    detalle.append({
                        'metodo': nombre,
                        'monto': float(monto),
                        'monto_bs': float(monto_bs),
                        'referencia': ref
                    })
        restante = self.total_bs - total_pagado
        if hasattr(self, 'lbl_pagado'):
            self.lbl_pagado.setText(f"Pagado: {float(total_pagado):,.2f} Bs")
            if restante > Decimal('0.01'):
                self.lbl_restante.setText(f"Falta: {float(restante):,.2f} Bs")
                self.lbl_restante.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {WARNING};")
                self.lbl_cambio.hide()
                self.btn_completar.setEnabled(False)
            elif restante < Decimal('-0.01'):
                self.lbl_restante.setText("✓ Pago completo")
                self.lbl_restante.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {ACCENT};")
                self.lbl_cambio.setText(f"Cambio: {float(abs(restante)):,.2f} Bs")
                self.lbl_cambio.show()
                self.btn_completar.setEnabled(True)
            else:
                self.lbl_restante.setText("✓ Pago exacto")
                self.lbl_restante.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {ACCENT};")
                self.lbl_cambio.hide()
                self.btn_completar.setEnabled(True)
        self.detalle_pagos = detalle
        self.cambio = max(Decimal('0'), -restante)

    def _completar(self):
        self.pagado = True
        self.accept()

    def get_resultado(self):
        return {
            'pagado': self.pagado,
            'detalle_pagos': self.detalle_pagos,
            'total_pagado_bs': float(sum(p['monto_bs'] for p in self.detalle_pagos)),
            'cambio': float(self.cambio)
        }

    def _actualizar_display(self):
        self._recalcular()

