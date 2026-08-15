"""
Módulo integrador de ventas - Versión refactorizada
Este módulo ahora solo actúa como punto de entrada que usa:
- VentasCarritoWidget (de ventas_carrito.py) para el carrito
- DialogoMetodosPago (de metodo_pago.py) para el pago
Mantiene compatibilidad hacia atrás con el código existente.
"""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal

# Importar el widget de carrito que ya incluye todo
from modules.ventas_carrito import VentasCarritoWidget

# Mantener compatibilidad: exportar las clases que esperan otros módulos
from modules.metodo_pago import DialogoMetodosPago
from modules.ventas_carrito_constants import (
    PRIMARY, PRIMARY_LIGHT, PRIMARY_DARK, ACCENT, WARNING, 
    DANGER, BACKGROUND, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, BORDER
)
from modules.ventas_carrito_cards import ProductoCard

# Exportar clases de clientes para compatibilidad
try:
    from modules.clientes_manager import ClientesDB, DialogoClientesFrecuentes
except ImportError:
    ClientesDB = None
    DialogoClientesFrecuentes = None


class VentasIntegradoWidget(VentasCarritoWidget):
    """
    Widget de ventas integrado - Wrapper para mantener compatibilidad
    Hereda todo de VentasCarritoWidget, no añade funcionalidad nueva
    """
    # Las señales ya están definidas en el padre, pero las repetimos para claridad
    venta_completada = pyqtSignal(dict)
    volver_solicitado = pyqtSignal()

    def __init__(self, db=None, parent=None):
        # Llamar al inicializador del padre que tiene toda la lógica
        super().__init__(db=db, parent=parent)
        # No necesita código adicional, todo está en VentasCarritoWidget

