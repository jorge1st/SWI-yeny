from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QMessageBox, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
import sqlite3
import os

PRIMARY      = "#6B4ED6"
PRIMARY_LIGHT= "#8E6BE6"
PRIMARY_DARK = "#5A3FC7"
ACCENT       = "#00C853"
DANGER       = "#E25555"
BORDER       = "#E8E3F5"
BACKGROUND   = "#F8F6FF"
SURFACE      = "#FFFFFF"
TEXT_PRIMARY = "#222222"
TEXT_SECONDARY = "#666666"

class ClientesDB:
    def __init__(self, db_path="clientes.db"):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cedula TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                telefono TEXT,
                email TEXT,
                direccion TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()
    def guardar_cliente(self, cedula, nombre, telefono="", email="", direccion=""):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clientes WHERE cedula = ?", (cedula,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE clientes 
                    SET nombre = ?, telefono = ?, email = ?, direccion = ?
                    WHERE cedula = ?
                """, (nombre, telefono, email, direccion, cedula))
            else:
                cursor.execute("""
                    INSERT INTO clientes (cedula, nombre, telefono, email, direccion)
                    VALUES (?, ?, ?, ?, ?)
                """, (cedula, nombre, telefono, email, direccion))
            conn.commit()
            conn.close()
            return True, "Cliente guardado exitosamente"
        except sqlite3.IntegrityError:
            return False, "La cédula ya está registrada"
        except Exception as e:
            return False, f"Error: {str(e)}"
    def obtener_clientes(self, activos_only=True):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if activos_only:
                cursor.execute("""
                    SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro 
                    FROM clientes 
                    WHERE activo = 1 
                    ORDER BY nombre
                """)
            else:
                cursor.execute("""
                    SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro 
                    FROM clientes 
                    ORDER BY nombre
                """)
            rows = cursor.fetchall()
            conn.close()
            clientes = []
            for row in rows:
                clientes.append({
                    'id': row[0],
                    'cedula': row[1],
                    'nombre': row[2],
                    'telefono': row[3],
                    'email': row[4],
                    'direccion': row[5],
                    'fecha_registro': row[6]
                })
            return clientes
        except Exception as e:
            print(f"Error obteniendo clientes: {e}")
            return []
    def buscar_clientes(self, texto):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            search = f"%{texto}%"
            cursor.execute("""
                SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro 
                FROM clientes 
                WHERE activo = 1 
                AND (nombre LIKE ? OR cedula LIKE ?)
                ORDER BY nombre
            """, (search, search))
            rows = cursor.fetchall()
            conn.close()
            clientes = []
            for row in rows:
                clientes.append({
                    'id': row[0],
                    'cedula': row[1],
                    'nombre': row[2],
                    'telefono': row[3],
                    'email': row[4],
                    'direccion': row[5],
                    'fecha_registro': row[6]
                })
            return clientes
        except Exception as e:
            print(f"Error buscando clientes: {e}")
            return []
    def eliminar_cliente(self, cedula):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE clientes SET activo = 0 WHERE cedula = ?", (cedula,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error eliminando cliente: {e}")
            return False
    def obtener_por_cedula(self, cedula):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, cedula, nombre, telefono, email, direccion 
                FROM clientes 
                WHERE cedula = ? AND activo = 1
            """, (cedula,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    'id': row[0],
                    'cedula': row[1],
                    'nombre': row[2],
                    'telefono': row[3],
                    'email': row[4],
                    'direccion': row[5]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo cliente: {e}")
            return None

class DialogoClientesFrecuentes(QDialog):
    cliente_seleccionado = pyqtSignal(dict)
    def __init__(self, parent=None, cliente_actual=None):
        super().__init__(parent)
        try:
            self.setObjectName("clientes_manager")
        except Exception:
            pass
        self.setWindowTitle("Clientes Frecuentes")
        self.setMinimumSize(700, 560)
        self.db = ClientesDB()
        self.cliente_actual = cliente_actual
        self._build_ui()
        self._cargar_clientes()
    def _get_input_style(self):
        return """
            QLineEdit {
                border: 1px solid #E8E3F5;
                border-radius: 14px;
                padding: 6px 10px;
                min-height: 26px;
                font-size: 13px;
                color: #181818;
                background: #FFFFFF;
            }
            QLineEdit:focus {
                border: 2px solid #6B4ED6;
                background: #F3F0FC;
            }
            QLineEdit::placeholder {
                color: #888888;
                font-size: 13px;
            }
        """
    def _get_labelbox_style(self):
        return """
            QLabel {
                background: #FFFFFF;
                border-radius: 14px;
                font-size: 13px;
                color: #6B4ED6;
                padding: 6px 10px;
                min-height: 26px;
                font-weight: 700;
            }
        """
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(13)

        header = QLabel("👥 Gestión de Clientes")
        header.setStyleSheet(f"font-size:19px;font-weight:700;color:{PRIMARY};padding-bottom:8px;")
        layout.addWidget(header)
        tabs_layout = QHBoxLayout()
        self.btn_tab_seleccionar = QPushButton("📋 Seleccionar Cliente")
        self.btn_tab_seleccionar.setCheckable(True)
        self.btn_tab_seleccionar.setChecked(True)
        self.btn_tab_seleccionar.setStyleSheet(self._get_tab_style(True))
        self.btn_tab_seleccionar.clicked.connect(lambda: self._cambiar_tab('seleccionar'))
        self.btn_tab_nuevo = QPushButton("➕ Nuevo Cliente")
        self.btn_tab_nuevo.setCheckable(True)
        self.btn_tab_nuevo.setStyleSheet(self._get_tab_style(False))
        self.btn_tab_nuevo.clicked.connect(lambda: self._cambiar_tab('nuevo'))
        tabs_layout.addWidget(self.btn_tab_seleccionar)
        tabs_layout.addWidget(self.btn_tab_nuevo)
        tabs_layout.addStretch()
        layout.addLayout(tabs_layout)
        self.stack = QWidget()
        self.stack_layout = QVBoxLayout(self.stack)
        self.stack_layout.setContentsMargins(0,0,0,0)
        # PANEL SELECCIONAR MODIFICADO
        self.panel_seleccionar = QWidget()
        sel_layout = QVBoxLayout(self.panel_seleccionar)
        sel_layout.setContentsMargins(0,0,0,0)
        sel_layout.setSpacing(7)
        search_row = QHBoxLayout()
        search_lbl = QLabel("🔍 Buscar:")
        search_lbl.setStyleSheet("font-size:13px;color:#6B4ED6;font-weight:600;padding-right:6px;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre o cédula...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #E8E3F5;
                border-radius: 13px;
                padding:6px 12px;
                font-size:12px;
                background:#FFF;
                min-height:24px;
            }
            QLineEdit:focus {
                border: 2px solid #8E6BE6;
                background:#F3F0FC;
            }
        """)
        self.search_input.textChanged.connect(self._filtrar_clientes)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self.search_input)
        sel_layout.addLayout(search_row)
        # Lista de clientes: tabla compacta y espaciosa, con boton corregido
        self.tabla_clientes = QTableWidget()
        self.tabla_clientes.setColumnCount(4)
        self.tabla_clientes.setHorizontalHeaderLabels(["Cédula", "Nombre", "Teléfono", "Acción"])
        self.tabla_clientes.setStyleSheet(f"""
            QTableWidget {{
                border: 1.3px solid {BORDER};
                border-radius: 12px;
                background: {SURFACE};
                font-size: 12px;
                color: #222;
            }}
            QTableWidget::item {{
                padding: 6px 6px;
            }}
            QTableWidget::item:selected {{
                background: #EDE7F6;
                color: #4A3BA5;
            }}
            QHeaderView::section {{
                background: {PRIMARY};
                color: white;
                padding: 7px 5px;
                font-weight: 700;
                border-radius: 8px;
                font-size:12px;
            }}
        """)
        self.tabla_clientes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tabla_clientes.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_clientes.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabla_clientes.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tabla_clientes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_clientes.setAlternatingRowColors(True)
        self.tabla_clientes.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla_clientes.cellDoubleClicked.connect(self._seleccionar_de_tabla)
        sel_layout.addWidget(self.tabla_clientes, 30)
        btn_row = QHBoxLayout()
        self.btn_eliminar = QPushButton("🗑 Eliminar")
        self.btn_eliminar.setStyleSheet("""
            QPushButton {
                background:#fff;
                color:#E25555;
                border:1.3px solid #E25555;
                border-radius:9px;
                padding:6px 16px;
                font-weight:600;
                font-size:14px;
            }
            QPushButton:hover {
                background: #E25555;
                color: #fff;
            }
        """)
        self.btn_eliminar.clicked.connect(self._eliminar_cliente)
        self.btn_seleccionar = QPushButton("✔ Seleccionar Cliente")
        self.btn_seleccionar.setStyleSheet("""
            QPushButton {
                background:#00C853;
                color:#fff;
                font-weight:700;
                font-size:15px;
                border-radius:9px;
                padding:6px 18px;
            }
            QPushButton:hover {
                filter:brightness(0.92);
                background:#007C2A;
            }
        """)
        self.btn_seleccionar.clicked.connect(self._seleccionar_actual)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_eliminar)
        btn_row.addWidget(self.btn_seleccionar)
        sel_layout.addLayout(btn_row)

        # PANEL NUEVO CLIENTE igual que antes
        self.panel_nuevo = QWidget()
        nuevo_layout = QVBoxLayout(self.panel_nuevo)
        nuevo_layout.setContentsMargins(0,0,0,0)
        nuevo_layout.setSpacing(7)
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background: #F3F0FC;
                border-radius: 16px;
                border: 1px solid #E8E3F5;
                padding: 12px 6px;
            }
        """)
        form_layout = QGridLayout(form_frame)
        form_layout.setVerticalSpacing(13)
        form_layout.setHorizontalSpacing(18)
        labels = [
            "Cédula/RIF:*",
            "Nombre/Razón Social:*",
            "Teléfono:",
            "Email:",
            "Dirección:"
        ]
        for i, lbl in enumerate(labels):
            lab = QLabel(lbl)
            lab.setStyleSheet(self._get_labelbox_style())
            form_layout.addWidget(lab, i, 0)
        self.input_cedula = QLineEdit()
        self.input_cedula.setPlaceholderText("V-12345678 o J-12345678")
        self.input_cedula.setStyleSheet(self._get_input_style())
        form_layout.addWidget(self.input_cedula, 0, 1)
        self.input_nombre = QLineEdit()
        self.input_nombre.setPlaceholderText("Nombre completo")
        self.input_nombre.setStyleSheet(self._get_input_style())
        form_layout.addWidget(self.input_nombre, 1, 1)
        self.input_telefono = QLineEdit()
        self.input_telefono.setPlaceholderText("0412-1234567")
        self.input_telefono.setStyleSheet(self._get_input_style())
        form_layout.addWidget(self.input_telefono, 2, 1)
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("cliente@email.com")
        self.input_email.setStyleSheet(self._get_input_style())
        form_layout.addWidget(self.input_email, 3, 1)
        self.input_direccion = QLineEdit()
        self.input_direccion.setPlaceholderText("Dirección completa")
        self.input_direccion.setStyleSheet(self._get_input_style())
        form_layout.addWidget(self.input_direccion, 4, 1)
        nuevo_layout.addWidget(form_frame)
        nuevo_layout.addSpacing(4)
        self.btn_guardar = QPushButton("💾 Guardar Cliente")
        self.btn_guardar.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY};
                color: white;
                border-radius: 12px;
                padding: 9px 18px;
                font-weight: 750;
                font-size: 14px;
                margin-top:8px;
            }}
            QPushButton:hover {{
                background: {PRIMARY_DARK};
            }}
        """)
        self.btn_guardar.clicked.connect(self._guardar_nuevo)
        nuevo_layout.addWidget(self.btn_guardar, alignment=Qt.AlignCenter)
        nuevo_layout.addStretch()
        self.stack_layout.addWidget(self.panel_seleccionar)
        self.panel_nuevo.hide()
        self.stack_layout.addWidget(self.panel_nuevo)
        layout.addWidget(self.stack)
        btn_cerrar = QPushButton("✕ Cerrar")
        btn_cerrar.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 7px 18px;
                font-size:12px;
            }}
            QPushButton:hover {{
                background: {BORDER};
            }}
        """)
        btn_cerrar.clicked.connect(self.reject)
        layout.addWidget(btn_cerrar, alignment=Qt.AlignRight)

    def _get_tab_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: {PRIMARY};
                    color: white;
                    border-radius: 9px;
                    padding: 8px 22px;
                    font-weight: 700;
                    font-size: 13px;
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_SECONDARY};
                    border: 1px solid {BORDER};
                    border-radius: 9px;
                    padding: 8px 22px;
                    font-weight: 700;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background: {BACKGROUND};
                    color: {PRIMARY};
                }}
            """

    def _cambiar_tab(self, tab):
        if tab == 'seleccionar':
            self.btn_tab_seleccionar.setChecked(True)
            self.btn_tab_seleccionar.setStyleSheet(self._get_tab_style(True))
            self.btn_tab_nuevo.setChecked(False)
            self.btn_tab_nuevo.setStyleSheet(self._get_tab_style(False))
            self.panel_seleccionar.show()
            self.panel_nuevo.hide()
        else:
            self.btn_tab_nuevo.setChecked(True)
            self.btn_tab_nuevo.setStyleSheet(self._get_tab_style(True))
            self.btn_tab_seleccionar.setChecked(False)
            self.btn_tab_seleccionar.setStyleSheet(self._get_tab_style(False))
            self.panel_seleccionar.hide()
            self.panel_nuevo.show()

    def _cargar_clientes(self):
        clientes = self.db.obtener_clientes()
        self._llenar_tabla(clientes)

    def _llenar_tabla(self, clientes):
        self.tabla_clientes.setRowCount(len(clientes))
        self.tabla_clientes.setColumnWidth(3, 120)
        for i, cliente in enumerate(clientes):
            item_cedula = QTableWidgetItem(cliente['cedula'])
            item_nombre = QTableWidgetItem(cliente['nombre'])
            item_telefono = QTableWidgetItem(cliente['telefono'] or "")
            self.tabla_clientes.setItem(i, 0, item_cedula)
            self.tabla_clientes.setItem(i, 1, item_nombre)
            self.tabla_clientes.setItem(i, 2, item_telefono)
            btn = QPushButton("Seleccionar")
            try:
                from modules.ui_scaling import scale_px

                btn.setMinimumHeight(scale_px(34))
                btn.setMinimumWidth(scale_px(98))
                btn.setMaximumHeight(scale_px(38))
            except Exception:
                btn.setMinimumHeight(34)
                btn.setMinimumWidth(98)
                btn.setMaximumHeight(38)
            btn.setStyleSheet("""
                QPushButton {
                    background: #8E6BE6;
                    color: white;
                    border-radius:9px;
                    font-size:13px;
                    padding:5px 16px;
                }
                QPushButton:hover {
                    background:#6B4ED6;
                }
            """)
            btn.clicked.connect(lambda checked, c=cliente: self._seleccionar_cliente(c))
            self.tabla_clientes.setCellWidget(i, 3, btn)
            self.tabla_clientes.setRowHeight(i, 40)
        self.tabla_clientes.resizeColumnsToContents()

    def _filtrar_clientes(self, texto):
        if len(texto) < 2:
            self._cargar_clientes()
            return
        clientes = self.db.buscar_clientes(texto)
        self._llenar_tabla(clientes)

    def _seleccionar_de_tabla(self, row, column):
        cedula = self.tabla_clientes.item(row, 0).text()
        cliente = self.db.obtener_por_cedula(cedula)
        if cliente:
            self._seleccionar_cliente(cliente)

    def _seleccionar_actual(self):
        selected = self.tabla_clientes.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Selección", "Por favor seleccione un cliente de la lista")
            return
        row = selected[0].row()
        cedula = self.tabla_clientes.item(row, 0).text()
        cliente = self.db.obtener_por_cedula(cedula)
        if cliente:
            self._seleccionar_cliente(cliente)

    def _seleccionar_cliente(self, cliente):
        self.cliente_seleccionado.emit(cliente)
        self.accept()

    def _guardar_nuevo(self):
        cedula = self.input_cedula.text().strip()
        nombre = self.input_nombre.text().strip()
        telefono = self.input_telefono.text().strip()
        email = self.input_email.text().strip()
        direccion = self.input_direccion.text().strip()
        if not cedula or not nombre:
            QMessageBox.warning(self, "Campos Requeridos", "Cédula y Nombre son obligatorios")
            return
        success, msg = self.db.guardar_cliente(cedula, nombre, telefono, email, direccion)
        if success:
            QMessageBox.information(self, "Éxito", msg)
            self.input_cedula.clear()
            self.input_nombre.clear()
            self.input_telefono.clear()
            self.input_email.clear()
            self.input_direccion.clear()
            self._cambiar_tab('seleccionar')
            self._cargar_clientes()
            cliente = self.db.obtener_por_cedula(cedula)
            if cliente:
                self._seleccionar_cliente(cliente)
        else:
            QMessageBox.warning(self, "Error", msg)

    def _eliminar_cliente(self):
        selected = self.tabla_clientes.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Selección", "Por favor seleccione un cliente para eliminar")
            return
        row = selected[0].row()
        cedula = self.tabla_clientes.item(row, 0).text()
        nombre = self.tabla_clientes.item(row, 1).text()
        resp = QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Está seguro de eliminar a {nombre} ({cedula})?",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp == QMessageBox.Yes:
            if self.db.eliminar_cliente(cedula):
                QMessageBox.information(self, "Éxito", "Cliente eliminado correctamente")
                self._cargar_clientes()
            else:
                QMessageBox.warning(self, "Error", "No se pudo eliminar el cliente")

    def get_cliente(self):
        return None

