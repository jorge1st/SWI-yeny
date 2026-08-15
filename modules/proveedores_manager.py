from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
from PyQt5.QtCore import pyqtSignal

import sqlite3
import os

try:
    from modules.clientes_manager import PRIMARY
except Exception:
    PRIMARY = "#6B4ED6"

class ProveedoresDB:
    def __init__(self, db_path="proveedores.db"):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proveedores (
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
    def guardar_proveedor(self, cedula, nombre, telefono="", email="", direccion=""):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM proveedores WHERE cedula = ?", (cedula,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE proveedores
                    SET nombre = ?, telefono = ?, email = ?, direccion = ?
                    WHERE cedula = ?
                """, (nombre, telefono, email, direccion, cedula))
            else:
                cursor.execute("""
                    INSERT INTO proveedores (cedula, nombre, telefono, email, direccion)
                    VALUES (?, ?, ?, ?, ?)
                """, (cedula, nombre, telefono, email, direccion))
            conn.commit()
            conn.close()
            return True, "Proveedor guardado exitosamente"
        except sqlite3.IntegrityError:
            return False, "La cédula ya está registrada"
        except Exception as e:
            return False, f"Error: {str(e)}"
    def obtener_proveedores(self, activos_only=True):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if activos_only:
                cursor.execute("""
                    SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro
                    FROM proveedores
                    WHERE activo = 1
                    ORDER BY nombre
                """)
            else:
                cursor.execute("""
                    SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro
                    FROM proveedores
                    ORDER BY nombre
                """)
            rows = cursor.fetchall()
            conn.close()
            provs = []
            for row in rows:
                provs.append({
                    'id': row[0], 'cedula': row[1], 'nombre': row[2], 'telefono': row[3], 'email': row[4], 'direccion': row[5], 'fecha_registro': row[6]
                })
            return provs
        except Exception as e:
            print(f"Error obteniendo proveedores: {e}")
            return []
    def buscar_proveedores(self, texto):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            search = f"%{texto}%"
            cursor.execute("""
                SELECT id, cedula, nombre, telefono, email, direccion, fecha_registro
                FROM proveedores
                WHERE activo = 1 AND (nombre LIKE ? OR cedula LIKE ?)
                ORDER BY nombre
            """, (search, search))
            rows = cursor.fetchall()
            conn.close()
            provs = []
            for row in rows:
                provs.append({
                    'id': row[0], 'cedula': row[1], 'nombre': row[2], 'telefono': row[3], 'email': row[4], 'direccion': row[5], 'fecha_registro': row[6]
                })
            return provs
        except Exception as e:
            print(f"Error buscando proveedores: {e}")
            return []
    def eliminar_proveedor(self, cedula):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE cedula = ?", (cedula,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error eliminando proveedor: {e}")
            return False
    def obtener_por_cedula(self, cedula):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, cedula, nombre, telefono, email, direccion
                FROM proveedores
                WHERE cedula = ? AND activo = 1
            """, (cedula,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {'id': row[0], 'cedula': row[1], 'nombre': row[2], 'telefono': row[3], 'email': row[4], 'direccion': row[5]}
            return None
        except Exception as e:
            print(f"Error obteniendo proveedor: {e}")
            return None


PRIMARY = PRIMARY

class DialogoProveedores(QDialog):
    proveedor_seleccionado = pyqtSignal(dict)

    def __init__(self, parent=None, proveedor_actual=None):
        super().__init__(parent)
        self.setWindowTitle("Proveedores")
        self.setMinimumSize(700, 560)
        self.db = ProveedoresDB()
        self.proveedor_actual = proveedor_actual
        self._build_ui()
        self._cargar_proveedores()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel("👥 Gestión de Proveedores")
        header.setStyleSheet(f"font-size:19px;font-weight:700;color:{PRIMARY};padding-bottom:8px;")
        layout.addWidget(header)
        # Form para añadir nuevo proveedor
        form_row = QHBoxLayout()
        self.input_nombre = QLineEdit()
        self.input_nombre.setPlaceholderText("Nombre")
        self.input_cedula = QLineEdit()
        self.input_cedula.setPlaceholderText("Cédula / RIF")
        self.input_telefono = QLineEdit()
        self.input_telefono.setPlaceholderText("Teléfono")
        self.input_direccion = QLineEdit()
        self.input_direccion.setPlaceholderText("Dirección")
        btn_add = QPushButton("Añadir Proveedor")
        btn_add.clicked.connect(self._guardar_nuevo_proveedor)
        form_row.addWidget(self.input_nombre)
        form_row.addWidget(self.input_cedula)
        form_row.addWidget(self.input_telefono)
        form_row.addWidget(self.input_direccion)
        form_row.addWidget(btn_add)
        layout.addLayout(form_row)
        # simple search + table
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre o cédula...")
        self.search_input.textChanged.connect(self._filtrar_proveedores)
        search_row.addWidget(self.search_input)
        layout.addLayout(search_row)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["Cédula", "Nombre", "Teléfono", "Dirección", "Acción"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.cellDoubleClicked.connect(self._seleccionar_de_tabla)
        layout.addWidget(self.tabla)

    def _cargar_proveedores(self):
        try:
            rows = self.db.obtener_proveedores(activos_only=True)
            self._llenar_tabla(rows)
        except Exception as e:
            print('Error cargando proveedores:', e)

    def _llenar_tabla(self, proveedores):
        self.tabla.setRowCount(len(proveedores))
        for i, prov in enumerate(proveedores):
            self.tabla.setItem(i, 0, QTableWidgetItem(prov.get('cedula','')))
            self.tabla.setItem(i, 1, QTableWidgetItem(prov.get('nombre','')))
            self.tabla.setItem(i, 2, QTableWidgetItem(prov.get('telefono','') or ''))
            self.tabla.setItem(i, 3, QTableWidgetItem(prov.get('direccion','') or ''))
            btn = QPushButton('Seleccionar')
            btn.clicked.connect(lambda checked, p=prov: self._seleccionar_proveedor(p))
            self.tabla.setCellWidget(i, 4, btn)

    def _guardar_nuevo_proveedor(self):
        try:
            nombre = self.input_nombre.text().strip()
            cedula = self.input_cedula.text().strip()
            telefono = self.input_telefono.text().strip()
            direccion = self.input_direccion.text().strip()
            if not nombre or not cedula:
                QMessageBox.warning(self, "Datos incompletos", "Nombre y Cédula/RIF son requeridos.")
                return
            ok, msg = self.db.guardar_proveedor(cedula, nombre, telefono, "", direccion)
            if ok:
                QMessageBox.information(self, "Guardado", msg)
                try:
                    self.input_nombre.clear()
                    self.input_cedula.clear()
                    self.input_telefono.clear()
                    self.input_direccion.clear()
                except Exception:
                    pass
                self._cargar_proveedores()
            else:
                QMessageBox.warning(self, "Error", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar proveedor: {e}")

    def _filtrar_proveedores(self, texto):
        try:
            rows = self.db.buscar_proveedores(texto)
            self._llenar_tabla(rows)
        except Exception as e:
            print('Error filtrando proveedores:', e)

    def _seleccionar_de_tabla(self, row, col):
        cedula = self.tabla.item(row, 0).text()
        prov = self.db.obtener_por_cedula(cedula)
        if prov:
            self._seleccionar_proveedor(prov)

    def _seleccionar_proveedor(self, prov):
        self.proveedor_seleccionado.emit(prov)
        self.accept()
