# modules/dashboard.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QMessageBox, QInputDialog,
    QLayout, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, QDate, QTimer, QSize
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QFontMetrics
from db_manager import DBManager
import datetime
from decimal import Decimal, ROUND_HALF_UP, getcontext
import os
import sys
import sys

# Optional qtawesome (vector icons). Install with: pip install qtawesome
try:
    import qtawesome as qta
    _HAVE_QTA = True
except Exception:
    qta = None
    _HAVE_QTA = False

# Try to import the NotificationManager; if unavailable, continue without notifications.
try:
    from modules.notification import NotificationManager
    _HAVE_NOTIFICATION = True
except Exception:
    NotificationManager = None
    _HAVE_NOTIFICATION = False

getcontext().prec = 28
DEBUG = False

try:
    from modules.ui_scaling import scale_px, get_ui_scale
except Exception:
    # fallback to identity functions if ui_scaling missing
    def scale_px(x):
        try:
            return int(x)
        except Exception:
            return x
    def get_ui_scale():
        return 1.0

def D(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')

def format_usd_decimal(d: Decimal) -> str:
    try:
        return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,} $"
    except Exception:
        try:
            return f"{float(d):,.2f} $"
        except Exception:
            return "-- $"

def format_bs_decimal(d: Decimal) -> str:
    try:
        return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,} Bs"
    except Exception:
        try:
            return f"{float(d):,.2f} Bs"
        except Exception:
            return "-- Bs"

def get_current_bcv_rate_safe():
    """
    Intenta obtener la tasa BCV desde main.get_current_bcv_rate().
    Devuelve (rate_decimal, timestamp_str) o (None, None) si no está disponible.
    """
    try:
        from main import get_current_bcv_rate
        r, ts = get_current_bcv_rate()
        return (D(r), ts) if r is not None else (None, ts)
    except Exception:
        return (None, None)

def _find_bcv_logo():
    """
    Busca una imagen dentro de la carpeta Logo_BCV en varias ubicaciones para
    soportar ejecución desde el código fuente y desde ejecutables creados con
    PyInstaller (onefile o onefolder). Retorna la ruta del primer archivo de
    imagen encontrado o None.
    """
    import sys

    candidates = []
    # 1) If running from PyInstaller onefile, resources are in _MEIPASS
    base_meipass = getattr(sys, '_MEIPASS', None)
    if base_meipass:
        candidates.append(os.path.join(base_meipass, 'Logo_BCV'))
    # 2) The directory where this module lives (useful for development installs)
    try:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(module_dir, 'Logo_BCV'))
    except Exception:
        pass
    # 3) Current working directory (normal run)
    candidates.append(os.path.join(os.path.abspath(os.getcwd()), 'Logo_BCV'))
    # 4) PyInstaller (onefolder) may place data inside an "_internal" folder
    candidates.append(os.path.join(os.path.abspath(os.getcwd()), '_internal', 'Logo_BCV'))
    # 5) Executable directory (when running as bundle) and its _internal
    try:
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'executable', None) else None
        if exe_dir:
            candidates.append(os.path.join(exe_dir, 'Logo_BCV'))
            candidates.append(os.path.join(exe_dir, '_internal', 'Logo_BCV'))
    except Exception:
        pass

    seen = set()
    for folder in candidates:
        if not folder or folder in seen:
            continue
        seen.add(folder)
        try:
            if os.path.isdir(folder):
                for fname in os.listdir(folder):
                    f = fname.lower()
                    if f.endswith((".png", ".jpg", ".jpeg", ".bmp", ".svg")):
                        return os.path.join(folder, fname)
        except Exception:
            continue
    # As a last resort, try to find a folder named Logo_BCV one level up from cwd
    try:
        parent = os.path.abspath(os.path.join(os.path.abspath(os.getcwd()), '..'))
        alt = os.path.join(parent, 'Logo_BCV')
        if os.path.isdir(alt):
            for fname in os.listdir(alt):
                f = fname.lower()
                if f.endswith((".png", ".jpg", ".jpeg", ".bmp", ".svg")):
                    return os.path.join(alt, fname)
    except Exception:
        pass
    return None

# ---------------- Icon helpers (drawn at runtime with QPainter or via qtawesome) ----------------
def make_symbol_icon(symbol: str, bg: str = "#D9CBFF", fg: str = "#4A3BA5", size: int = 64, radius: int = 12) -> QIcon:
    """
    Crea un QIcon dibujado en tiempo de ejecución:
    - fondo redondeado con color `bg`
    - símbolo centrado (texto) con color `fg`
    - size: tamaño del pixmap (cuadrado)
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    rect = pix.rect()
    # fondo redondeado
    color = QColor(bg)
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(rect, radius, radius)
    # símbolo centrado
    font = QFont("Segoe UI Symbol")
    font.setBold(True)
    font.setPixelSize(max(10, int(size * 0.42)))
    p.setFont(font)
    p.setPen(QColor(fg))
    p.drawText(rect, Qt.AlignCenter, symbol)
    p.end()
    return QIcon(pix)

def make_letter_circle_icon(letter: str, bg: str = "#D9CBFF", fg: str = "#4A3BA5", size: int = 56) -> QIcon:
    """
    Icono con círculo de fondo y una letra (ideal para fallback de departamentos).
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    rect = pix.rect()
    # círculo
    color = QColor(bg)
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    margin = int(size * 0.06)
    p.drawEllipse(rect.adjusted(margin, margin, -margin, -margin))
    # letra
    font = QFont("Segoe UI")
    font.setBold(True)
    font.setPixelSize(int(size * 0.42))
    p.setFont(font)
    p.setPen(QColor(fg))
    p.drawText(rect, Qt.AlignCenter, letter.upper()[:1])
    p.end()
    return QIcon(pix)

def _try_qta_icon(name: str, color: str = "#4A3BA5", size: int = 24) -> QIcon:
    """
    Intenta construir un icono con qtawesome; prueba varios prefijos comunes.
    Devuelve QIcon si tiene éxito, o None si no es posible.
    """
    if not _HAVE_QTA:
        return None
    prefixes = ["fa5s", "fa5r", "fa", "mdi", "ion", "ti"]  # intentar varios sets
    for p in prefixes:
        key = f"{p}.{name}"
        try:
            ic = qta.icon(key, color=color)
            return ic
        except Exception:
            continue
    # también probar con el nombre tal cual
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None

def get_icon_for_button(name: str, fallback_symbol: str = "•", fg: str = "#4A3BA5", bg_for_painter: str = "#D9CBFF", size_px: int = 48) -> QIcon:
    """
    Helper central: intenta crear icono vía qtawesome; si no está disponible, dibuja uno simple.
    `name` es el nombre semántico del icono (ej. 'plus', 'chart-line').
    """
    ic = _try_qta_icon(name, color=fg, size=int(size_px * 0.8))
    if ic:
        return ic
    # fallback: símbolo pintado dentro de un fondo redondeado
    return make_symbol_icon(fallback_symbol, bg=bg_for_painter, fg=fg, size=size_px, radius=max(8, int(size_px*0.22)))

# ---------------- Icon mappings ----------------
_ICON_MAP = {
    "Ingresar Producto": ("plus", "+"),
    "Registro General": ("list-alt", "≡"),
    "Registro de Entradas": ("arrow-down", "↓"),
    "Registro de Salidas": ("arrow-up", "↑"),
    "Registro de Ventas": ("cash-register", "💰"),  # NUEVO ICONO PARA VENTAS
    "Sistema de Ventas": ("shopping-cart", "🛒"),
    "Utilidad": ("archive", "☐"),
    "Gráficos por mes": ("chart-bar", "↗"),
    "Inventario bajo": ("exclamation-triangle", "⚠"),
    "Acerca del sistema": ("info-circle", "ℹ"),
    "Salir": ("sign-out-alt", "⎋"),
    "Actualizar tasa": ("sync", "⟳"),
    "Ingresar manual": ("pencil-alt", "✎")
}

class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # nombre para permitir scoping via QSS (styles/modules/dashboard.qss)
        try:
            self.setObjectName("dashboard")
        except Exception:
            pass
        self.db = DBManager()
        self.setWindowTitle("Panel Principal - Minimarket ChiChi N-K, C.A , J-5099900-7")
        try:
            self.resize(scale_px(1200), scale_px(720))
            self.setMinimumSize(scale_px(980), scale_px(640))
        except Exception:
            self.resize(1200, 720)
            self.setMinimumSize(980, 640)

        # currency shown for total valorizado: 'Bs' or '$'
        self._total_currency = 'Bs'

        # notification manager instance (provide self as parent so the floating widget positions relative to Dashboard)
        self.notification_mgr = NotificationManager.instance(parent=self, days=3, auto_collapse_ms=3000) if _HAVE_NOTIFICATION else None

        # Keep central layout as attribute so we can replace main content later
        central = QWidget()
        central.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(central)
        self.central_layout = QHBoxLayout(central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.central_layout.setSizeConstraint(QLayout.SetNoConstraint)

        # ======= Sidebar =======
        sidebar = QFrame()
        try:
            sidebar.setFixedWidth(scale_px(220))
        except Exception:
            sidebar.setFixedWidth(220)
        # Sidebar visuals moved to styles/modules/dashboard.qss
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        try:
            side_layout.setContentsMargins(scale_px(20), scale_px(20), scale_px(20), scale_px(20))
            side_layout.setSpacing(scale_px(10))
        except Exception:
            side_layout.setContentsMargins(20, 20, 20, 20)
            side_layout.setSpacing(10)

        self.sidebar_title = QLabel("MENÚ")
        try:
            self.sidebar_title.setStyleSheet(f"font-weight:bold; font-size:{scale_px(20)}px; color:white;")
        except Exception:
            self.sidebar_title.setStyleSheet("font-weight:bold; font-size:20px; color:white;")
        side_layout.addWidget(self.sidebar_title)
        try:
            side_layout.addSpacing(scale_px(6))
        except Exception:
            side_layout.addSpacing(6)

        # sidebar buttons
        btn_graf = QPushButton("Gráficos por mes")
        btn_graf.clicked.connect(self.open_graficos)
        btn_cad = QPushButton("Fecha de caducidad")
        btn_cad.clicked.connect(self.open_caducidad)
        # force a newline so the label doesn't get clipped
        btn_cad._display_override = "Fecha de\ncaducidad"
        btn_about = QPushButton("Acerca del sistema")
        btn_about.clicked.connect(self.open_acerca)
        btn_theme = QPushButton("Temas")
        btn_theme.clicked.connect(self.open_theme_editor)
        btn_exit = QPushButton("Salir")
        btn_exit.clicked.connect(self.cerrar_sesion)

        sidebar_buttons = [
            (btn_graf, "Gráficos por mes"),
            (btn_cad, "Inventario bajo"),
            (btn_about, "Acerca del sistema"),
            (btn_theme, "Temas"),
            (btn_exit, "Salir")
        ]
        for b, key in sidebar_buttons:
            name, fallback = _ICON_MAP.get(key, (None, "•"))
            icon = get_icon_for_button(name or key, fallback_symbol=fallback, fg="#FFFFFF", bg_for_painter="#6F4BD6", size_px=40)
            b.setIcon(icon)
            try:
                b.setIconSize(QSize(scale_px(28), scale_px(28)))
            except Exception:
                b.setIconSize(QSize(28, 28))
            # sidebar button visuals moved to QSS; tag with property for selector
            b.setProperty("role", "sidebar")
            b.setFlat(True)
            b.setCursor(Qt.PointingHandCursor)
            side_layout.addWidget(b)

        side_layout.addStretch()
        self.central_layout.addWidget(sidebar)

        # ======= Main Area (dashboard container) =======
        self.dashboard_container = QWidget()
        self.dashboard_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout = QVBoxLayout(self.dashboard_container)
        try:
            self.main_layout.setContentsMargins(scale_px(28), scale_px(12), scale_px(28), scale_px(20))
            self.main_layout.setSpacing(scale_px(12))
        except Exception:
            self.main_layout.setContentsMargins(28, 12, 28, 20)
            self.main_layout.setSpacing(12)

        # ======= BCV BOX (rounded + logo) =======
        self.bcv_box = QFrame()
        self.bcv_box.setObjectName("bcv_box")
        # Restore BCV box width to previous visual size (approximate original)
        try:
            self.bcv_box.setFixedWidth(scale_px(420))
        except Exception:
            self.bcv_box.setFixedWidth(420)
        bcv_layout = QVBoxLayout(self.bcv_box)
        try:
            bcv_layout.setContentsMargins(scale_px(16), scale_px(12), scale_px(16), scale_px(12))
            bcv_layout.setSpacing(scale_px(8))
        except Exception:
            bcv_layout.setContentsMargins(16, 12, 16, 12)
            bcv_layout.setSpacing(8)

        top_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        bcv_label = QLabel("Tasa BCV (USD → Bs)")
        bcv_label.setObjectName("bcv_label")
        self.bcv_value = QLabel("--")
        self.bcv_value.setObjectName("bcv_value")
        self.bcv_time = QLabel("")
        self.bcv_time.setObjectName("bcv_time")
        left_col.addWidget(bcv_label)
        left_col.addWidget(self.bcv_value)
        left_col.addWidget(self.bcv_time)
        top_row.addLayout(left_col)

        # Right: logo label (no transparency, larger)
        logo_label = QLabel()
        logo_label.setObjectName("bcv_logo_label")
        logo_label.setAlignment(Qt.AlignCenter)
        try:
            logo_label.setFixedSize(scale_px(160), scale_px(100))
        except Exception:
            logo_label.setFixedSize(160, 100)

        logo_path = _find_bcv_logo()
        self._logo_pix = None
        if logo_path:
            try:
                pix = QPixmap(logo_path)
                if not pix.isNull():
                    self._logo_pix = pix
                    scaled = self._logo_pix.scaled(scale_px(150), scale_px(90), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    logo_label.setPixmap(scaled)
            except Exception:
                pass

        top_row.addWidget(logo_label, alignment=Qt.AlignRight)
        bcv_layout.addLayout(top_row)

        # Buttons inside BCV box
        btn_row = QHBoxLayout()
        self.btn_bcv_update = QPushButton("Actualizar tasa")
        self.btn_bcv_update.setStyleSheet("background:#8E6BE6; color:white; border-radius:8px; font-weight:700;")
        self.btn_bcv_update.setCursor(Qt.PointingHandCursor)
        self.btn_bcv_manual = QPushButton("Ingresar manual")
        self.btn_bcv_manual.setStyleSheet("background:#8E6BE6; color:white; border-radius:8px; font-weight:700;")
        self.btn_bcv_manual.setCursor(Qt.PointingHandCursor)

        # icons for BCV buttons
        name_upd, fb_upd = _ICON_MAP.get("Actualizar tasa", ("sync", "⟳"))
        name_man, fb_man = _ICON_MAP.get("Ingresar manual", ("pencil-alt", "✎"))
        ic_upd = get_icon_for_button(name_upd, fallback_symbol=fb_upd, fg="#FFFFFF", bg_for_painter="#6F4BD6", size_px=44)
        ic_man = get_icon_for_button(name_man, fallback_symbol=fb_man, fg="#FFFFFF", bg_for_painter="#6F4BD6", size_px=44)
        self.btn_bcv_update.setIcon(ic_upd)
        try:
            self.btn_bcv_update.setIconSize(QSize(scale_px(22), scale_px(22)))
        except Exception:
            self.btn_bcv_update.setIconSize(QSize(22, 22))
        self.btn_bcv_manual.setIcon(ic_man)
        try:
            self.btn_bcv_manual.setIconSize(QSize(scale_px(22), scale_px(22)))
        except Exception:
            self.btn_bcv_manual.setIconSize(QSize(22, 22))

        btn_row.addStretch()
        btn_row.addWidget(self.btn_bcv_update)
        btn_row.addWidget(self.btn_bcv_manual)
        bcv_layout.addLayout(btn_row)

        # ---- Now create a header_row that places Company info to the LEFT of the BCV box ----
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)

        # LEFT area: company name and RIF (larger), placed to the left of the BCV box
        left_header = QVBoxLayout()
        left_header.setSpacing(2)
        # Increase the font size so the left area is prominent and fills the empty space
        self.left_company_name = QLabel("Minimarket ChiChi N-K, C.A")
        self.left_company_rif = QLabel("RIF: J-5099900-7")
        try:
            self.left_company_name.setStyleSheet(f"font-size:{scale_px(28)}px; font-weight:900; color:#5E3DB3;")
            self.left_company_rif.setStyleSheet(f"font-size:{scale_px(16)}px; font-weight:800; color:#5E3DB3;")
        except Exception:
            self.left_company_name.setStyleSheet("font-size:28px; font-weight:900; color:#5E3DB3;")
            self.left_company_rif.setStyleSheet("font-size:16px; font-weight:800; color:#5E3DB3;")
        left_header.addWidget(self.left_company_name)
        left_header.addWidget(self.left_company_rif)
        # Add a small spacer to align vertically with BCV box
        left_widget = QWidget()
        left_widget.setLayout(left_header)
        left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Add left company area and BCV box to header_row
        header_row.addWidget(left_widget, 1)
        header_row.addWidget(self.bcv_box, 0, Qt.AlignRight)

        # Add this composed header_row into main layout
        self.main_layout.addLayout(header_row)

        # ======= Main Content (menu + departments) =======
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        try:
            content_layout.setSpacing(scale_px(36))
            content_layout.setContentsMargins(0, scale_px(2), 0, 0)
        except Exception:
            content_layout.setSpacing(36)
            content_layout.setContentsMargins(0, 2, 0, 0)

        # Menú principal con iconos en 2 o 3 columnas
        menu_section = QVBoxLayout()
        menu_section.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.menu_title = QLabel("Menú")
        self.menu_title.setObjectName("menu_title")
        self.menu_title.setAlignment(Qt.AlignCenter)
        try:
            self.menu_title.setFixedHeight(scale_px(42))
        except Exception:
            self.menu_title.setFixedHeight(42)

        menu_items = [
            ("Ingresar Producto", "fa5s.plus"),
            ("Registro General", "fa5s.list-alt"),
            ("Entrada", "fa5s.arrow-down"),
            ("Salida", "fa5s.shopping-cart"),
            ("Utilidad", "fa5s.archive")
        ]

        menu_buttons = []
        for label, icon_name in menu_items:
            display_label = {"Ingresar Producto": "Ingresar\nProducto", "Registro General": "Registro\nGeneral", "Entrada": "Entrada", "Salida": "Salida", "Sistema de Ventas": "Sistema de\nVentas"}.get(label, label)
            btn = QPushButton(display_label)
            # keep plain label for internal use
            btn._orig_text = label
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setFixedHeight(65)
            try:
                # Si tienes qtawesome o tu función personalizada para iconos
                import qtawesome as qta
                btn.setIcon(qta.icon(icon_name, color="#4A3BA5"))
                btn.setIconSize(QSize(36, 36))
            except Exception:
                # Si prefieres un icono generado, usa tu get_icon_for_button aquí
                pass
            # menu button visuals moved to QSS
            btn.setProperty("role", "menu_button")
            menu_buttons.append(btn)

        try:
            w = self.width()
            if w > 2400:
                num_cols = 4
            elif w > 1600:
                num_cols = 3
            else:
                num_cols = 2
        except Exception:
            num_cols = 2
        menu_grid = QGridLayout()
        try:
            menu_grid.setHorizontalSpacing(scale_px(28))
            menu_grid.setVerticalSpacing(scale_px(18))
            menu_grid.setContentsMargins(scale_px(12), scale_px(12), scale_px(12), scale_px(12))
            menu_grid.setAlignment(Qt.AlignCenter)
        except Exception:
            menu_grid.setHorizontalSpacing(28)
            menu_grid.setVerticalSpacing(18)
            menu_grid.setContentsMargins(12, 12, 12, 12)
            try:
                menu_grid.setAlignment(Qt.AlignCenter)
            except Exception:
                pass
        for i, btn in enumerate(menu_buttons):
            row = i // num_cols
            col = i % num_cols
            menu_grid.addWidget(btn, row, col)
        if len(menu_buttons) % num_cols != 0:
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            menu_grid.addWidget(spacer, len(menu_buttons)//num_cols, len(menu_buttons)%num_cols)
        self.menu_buttons = menu_buttons
        self.menu_grid = menu_grid
        menu_section.addWidget(self.menu_title)
        menu_section.addLayout(menu_grid)
        menu_section.addStretch()
        # Restaurar conexiones de menú (asignar acciones a los botones)
        try:
            menu_actions = [
                self.open_productos,
                self.open_registro_general,
                self.open_entradas,  # ahora abre el Carrito de Compras o la vista correspondiente
                self.open_ventas,
                self.open_inventory
            ]
            for btn, action in zip(menu_buttons, menu_actions):
                btn.clicked.connect(action)
        except Exception:
            pass
        content_layout.addLayout(menu_section, 1)

        # Departamentos con iconos en 2 o 3 columnas
        dept_section = QVBoxLayout()
        dept_section.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.dept_title = QLabel("Departamentos")
        self.dept_title.setObjectName("dept_title")
        self.dept_title.setAlignment(Qt.AlignCenter)
        try:
            self.dept_title.setFixedHeight(scale_px(42))
        except Exception:
            self.dept_title.setFixedHeight(42)

        departamentos = [
            ("Productos de Limpieza", "fa5s.soap"),
            ("Confiteria", "fa5s.candy-cane"),
            ("Lacteos", "fa5s.cheese"),
            ("Aseo Personal", "fa5s.bath"),
            ("Vivieres", "fa5s.shopping-basket"),
            ("Bebidas", "fa5s.wine-glass-alt"),
            ("Farmacia", "fa5s.pills"),
            ("Bisuteria", "fa5s.gem"),
            ("Ferreteria", "fa5s.wrench")
        ]
        # label splits (use both accented and unaccented keys for safety)
        _DEPT_LABEL_SPLITS = {
            "Productos de Limpieza": "Productos\nde Limpieza",
            "Confitería": "Confitería",
            "Confiteria": "Confitería",
            "Lácteos": "Lácteos",
            "Lacteos": "Lácteos",
            "Aseo Personal": "Aseo\nPersonal",
            "Víveres": "Víveres",
            "Vivieres": "Víveres",
            "Bebidas": "Bebidas",
            "Farmacia": "Farmacia",
            "Bisuteria": "Bisuteria",
            "Ferreteria": "Ferretería",
            "Ferretería": "Ferretería"
        }

        # For layout: force 3 columns (3x3)
        num_cols = 3
        dept_buttons = []
        for label, icon_name in departamentos:
            # use explicit mapping for line breaks / accents
            display_label = _DEPT_LABEL_SPLITS.get(label, _DEPT_LABEL_SPLITS.get(label.strip(), label))

            btn = QPushButton(display_label)
            # keep plain label for callbacks
            btn._orig_text = label
            # store explicit display override (may contain newline) so reflow doesn't undo it
            btn._display_override = display_label
            # uniform fixed size so buttons don't stretch horizontally
            try:
                w = scale_px(200)
                h = scale_px(90)
            except Exception:
                w = 200
                h = 90
            btn.setFixedSize(w, h)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            try:
                import qtawesome as qta
                btn.setIcon(qta.icon(icon_name, color="#4A3BA5"))
                btn.setIconSize(QSize(36, 36))
            except Exception:
                pass
            # department button visuals moved to QSS
            btn.setProperty("role", "dept_button")
            dept_buttons.append(btn)

        dep_grid = QGridLayout()
        try:
            dep_grid.setHorizontalSpacing(scale_px(28))
            dep_grid.setVerticalSpacing(scale_px(18))
            dep_grid.setContentsMargins(scale_px(12), scale_px(12), scale_px(12), scale_px(12))
        except Exception:
            dep_grid.setHorizontalSpacing(28)
            dep_grid.setVerticalSpacing(18)
            dep_grid.setContentsMargins(12, 12, 12, 12)
        # prevent columns from stretching to fill parent
        try:
            for ci in range(num_cols):
                dep_grid.setColumnStretch(ci, 0)
        except Exception:
            pass
        for i, btn in enumerate(dept_buttons):
            row = i // num_cols
            col = i % num_cols
            dep_grid.addWidget(btn, row, col)
        if len(dept_buttons) % num_cols != 0:
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            dep_grid.addWidget(spacer, len(dept_buttons)//num_cols, len(dept_buttons)%num_cols)
        self.dept_buttons = dept_buttons
        self.dep_grid = dep_grid
        dept_section.addWidget(self.dept_title)
        dept_section.addLayout(dep_grid)
        dept_section.addStretch()
        # Restaurar conexiones de departamentos
        try:
            for (label, _), btn in zip(departamentos, dept_buttons):
                btn.clicked.connect(lambda checked, dep=label: self.open_reporte_filtrado(dep))
        except Exception:
            pass
        content_layout.addLayout(dept_section, 1)

        self.main_layout.addWidget(content_frame, alignment=Qt.AlignTop)
        self.main_layout.addStretch()
        self.central_layout.addWidget(self.dashboard_container, 1)
        # --------------- FIN DEL BLOQUE PARA REMPLAZO ------------------

        # Keep a reference to the currently shown widget
        self._current_content_widget = self.dashboard_container

        # connect BCV buttons
        self.btn_bcv_update.clicked.connect(self.update_bcv_from_web)
        self.btn_bcv_manual.clicked.connect(self.set_bcv_manual)

        # initial refreshes: ensure BCV is displayed immediately if available
        self._refresh_bcv_display()
        self.refresh_totals()

        # Timer: refresh expiry badge periodically
        self._expiry_timer = QTimer(self)
        self._expiry_timer.setInterval(10 * 1000)  # 10 seconds
        if self.notification_mgr:
            self._expiry_timer.timeout.connect(lambda: self.notification_mgr.evaluate_and_show(self.db))
        else:
            self._expiry_timer.timeout.connect(self._noop)
        self._expiry_timer.start()

        QTimer.singleShot(500, lambda: self.notification_mgr.evaluate_and_show(self.db) if self.notification_mgr else None)
        try:
            self.apply_layout_scale()
        except Exception:
            pass

    def _noop(self):
        pass

    def apply_layout_scale(self):
        try:
            try:
                ds = get_ui_scale()
            except Exception:
                ds = 1.0
            base_w, base_h = 1200.0, 720.0
            try:
                ls = max(1.0, min(self.width() / base_w, self.height() / base_h))
            except Exception:
                ls = 1.0
            cs = float(ds) * float(ls)
            # Sidebar
            try:
                sidebar = self.central_layout.itemAt(0).widget()
                if sidebar:
                    sidebar.setFixedWidth(int(220 * cs))
            except Exception:
                pass
            # Sidebar title
            try:
                if hasattr(self, 'sidebar_title'):
                    self.sidebar_title.setStyleSheet(f"font-weight:bold; font-size:{int(20*cs)}px; color:white;")
            except Exception:
                pass

            # Sidebar buttons: resize icons and adjust text to avoid truncation
            try:
                sidebar = self.central_layout.itemAt(0).widget() if self.central_layout.count() > 0 else None
                if sidebar:
                    sb_btns = [w for w in sidebar.findChildren(QPushButton) if isinstance(w, QPushButton)]
                    sidebar_w = sidebar.width() if sidebar.width() > 0 else int(220 * cs)
                    for b in sb_btns:
                        try:
                            # remember original text once
                            if not hasattr(b, '_orig_text'):
                                b._orig_text = b.text()
                            orig = b._orig_text.replace('\n', ' ')

                            # pick sizes
                            font_px = max(11, int(15 * cs))
                            icon_px = max(16, min(int(28 * cs), int(sidebar_w * 0.14)))

                            # measure and split if needed
                            qf = QFont()
                            qf.setPixelSize(font_px)
                            fm = QFontMetrics(qf)
                            padding_lr = int(12 * cs)
                            allowed_w = max(60, sidebar_w - icon_px - padding_lr - 8)

                            def _split_sidebar(txt):
                                if fm.horizontalAdvance(txt) <= allowed_w:
                                    return txt
                                words = txt.split()
                                for i in range(1, len(words)):
                                    l1 = ' '.join(words[:i])
                                    l2 = ' '.join(words[i:])
                                    if fm.horizontalAdvance(l1) <= allowed_w and fm.horizontalAdvance(l2) <= allowed_w:
                                        return l1 + '\n' + l2
                                mid = len(txt) // 2
                                left = txt.rfind(' ', 0, mid)
                                right = txt.find(' ', mid)
                                idx = left if left != -1 else right
                                if idx != -1:
                                    return txt[:idx] + '\n' + txt[idx+1:]
                                return fm.elidedText(txt, Qt.ElideRight, allowed_w)

                            display_override = getattr(b, '_display_override', None)
                            if display_override:
                                if b.text() != display_override:
                                    b.setText(display_override)
                                try:
                                    b.setIconSize(QSize(icon_px, icon_px))
                                except Exception:
                                    pass
                                b.setStyleSheet(f"background:transparent; color:white; padding:{int(8*cs)}px; font-size:{font_px}px; text-align:left;")
                            else:
                                new_text = _split_sidebar(orig)

                                b.setIconSize(QSize(icon_px, icon_px))
                                # only change text when the original doesn't fit, otherwise restore original if needed
                                try:
                                    if fm.horizontalAdvance(orig) > allowed_w:
                                        if new_text != b.text():
                                            b.setText(new_text)
                                    else:
                                        if b.text() != orig:
                                            b.setText(orig)
                                except Exception:
                                    # fallback: always set
                                    if new_text != b.text():
                                        b.setText(new_text)
                                b.setStyleSheet(f"background:transparent; color:white; padding:{int(8*cs)}px; font-size:{font_px}px; text-align:left;")
                        except Exception:
                            pass
            except Exception:
                pass

            # Main margins
            try:
                self.main_layout.setContentsMargins(int(28*cs), int(12*cs), int(28*cs), int(20*cs))
                self.main_layout.setSpacing(int(12*cs))
            except Exception:
                pass
            # BCV box and logo
            try:
                if hasattr(self, 'bcv_box'):
                    self.bcv_box.setFixedWidth(int(420*cs))
                logo_label = self.findChild(QLabel, "bcv_logo_label")
                if getattr(self, '_logo_pix', None) and logo_label:
                    logo_label.setFixedSize(int(160*cs), int(100*cs))
                    scaled = self._logo_pix.scaled(int(150*cs), int(90*cs), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    logo_label.setPixmap(scaled)
            except Exception:
                pass
            # BCV buttons
            try:
                self.btn_bcv_update.setIconSize(QSize(int(22*cs), int(22*cs)))
                self.btn_bcv_manual.setIconSize(QSize(int(22*cs), int(22*cs)))
            except Exception:
                pass
            # Company fonts
            try:
                self.left_company_name.setStyleSheet(f"font-size:{int(28*cs)}px; font-weight:900; color:#5E3DB3;")
                self.left_company_rif.setStyleSheet(f"font-size:{int(16*cs)}px; font-weight:800; color:#5E3DB3;")
            except Exception:
                pass
            # Columns
            menu_num_cols = 2
            dept_num_cols = 3
            # Menu buttons
            try:
                if hasattr(self, 'menu_buttons') and hasattr(self, 'menu_grid'):
                    # compute available width per column
                    try:
                        sidebar_w = sidebar.width() if sidebar is not None else int(220 * cs)
                        center_w = max(400, self.width() - sidebar_w - int(40 * cs))
                        gm = self.menu_grid
                        gm_m = gm.contentsMargins()
                        spacing_h = gm.horizontalSpacing()
                        left_right = gm_m.left() + gm_m.right()
                        col_w = max(160, int((center_w - left_right - (menu_num_cols - 1) * spacing_h) / menu_num_cols))
                    except Exception:
                        col_w = max(160, int((self.width() - int(220*cs)) / menu_num_cols))

                    for btn in self.menu_buttons:
                        try:
                            h = int(90 * cs)
                            btn.setFixedHeight(h)
                            padding_v = max(4, int(8 * cs))
                            content_h = max(18, h - 2 * padding_v)
                            icon_px = max(18, min(int(44 * cs), int(content_h * 0.55), int(col_w * 0.18)))
                            font_px = max(10, min(int(20 * cs), int(content_h * 0.30), int(col_w * 0.12)))
                            lr_pad = max(8, int(12 * cs))
                            border_rad = max(8, int(18 * cs))

                            btn.setIconSize(QSize(icon_px, icon_px))

                            # determine original text (avoid stacking newlines)
                            orig = getattr(btn, '_orig_text', btn.text()).replace('\n', ' ')

                            # measure and split if needed
                            qf = QFont()
                            qf.setPixelSize(font_px)
                            fm = QFontMetrics(qf)
                            allowed_w = col_w - icon_px - lr_pad - 12
                            if allowed_w < 40:
                                allowed_w = max(40, int(col_w * 0.6))

                            def _split_text(txt):
                                if fm.horizontalAdvance(txt) <= allowed_w:
                                    return txt
                                words = txt.split()
                                for i in range(1, len(words)):
                                    l1 = ' '.join(words[:i])
                                    l2 = ' '.join(words[i:])
                                    if fm.horizontalAdvance(l1) <= allowed_w and fm.horizontalAdvance(l2) <= allowed_w:
                                        return l1 + '\n' + l2
                                # fallback: try to break near midpoint
                                mid = len(txt) // 2
                                left = txt.rfind(' ', 0, mid)
                                right = txt.find(' ', mid)
                                idx = left if left != -1 else right
                                if idx != -1:
                                    return txt[:idx] + '\n' + txt[idx+1:]
                                return fm.elidedText(txt, Qt.ElideRight, allowed_w)

                            # prefer forced newline for specific menu labels regardless of width
                            try:
                                o = orig.lower()
                                forced = None
                                if 'ingresar' in o and 'producto' in o:
                                    forced = 'Ingresar\nProducto'
                                elif 'registro' in o and 'entrada' in o:
                                    forced = 'Registro de\nEntradas'
                                elif 'sistema' in o and 'venta' in o:
                                    forced = 'Sistema de\nVentas'
                                elif 'registro' in o and 'general' in o:
                                    forced = 'Registro\nGeneral'

                                if forced:
                                    if btn.text() != forced:
                                        btn.setText(forced)
                                else:
                                    # fallback to dynamic split/elide behavior
                                    new_text = _split_text(orig)
                                    if fm.horizontalAdvance(orig) > allowed_w:
                                        if new_text != btn.text():
                                            btn.setText(new_text)
                                    else:
                                        if btn.text() != orig:
                                            btn.setText(orig)
                            except Exception:
                                new_text = _split_text(orig)
                                if new_text != btn.text():
                                    btn.setText(new_text)

                            btn.setStyleSheet(f"QPushButton {{ background:#D9CBFF; border-radius:{border_rad}px; font-weight:700; font-size:{font_px}px; color:#4A3BA5; padding:{padding_v}px {lr_pad}px; text-align:left;}} QPushButton:hover {{ background:#C8B5FF; }}")
                        except Exception:
                            pass
                    self._reflow_grid(self.menu_grid, self.menu_buttons, menu_num_cols, cs)
                    try:
                        self.menu_title.setFixedHeight(int(42 * cs))
                    except Exception:
                        pass
            except Exception:
                pass
            # Dept buttons
            try:
                if hasattr(self, 'dept_buttons') and hasattr(self, 'dep_grid'):
                    try:
                        sidebar_w = sidebar.width() if sidebar is not None else int(220 * cs)
                        center_w = max(400, self.width() - sidebar_w - int(40 * cs))
                        gm = self.dep_grid
                        gm_m = gm.contentsMargins()
                        spacing_h = gm.horizontalSpacing()
                        left_right = gm_m.left() + gm_m.right()
                        dep_col_w = max(140, int((center_w - left_right - (dept_num_cols - 1) * spacing_h) / dept_num_cols))
                    except Exception:
                        dep_col_w = max(140, int((self.width() - int(220*cs)) / dept_num_cols))

                    for btn in self.dept_buttons:
                        try:
                            h = int(90 * cs)
                            btn.setFixedHeight(h)
                            padding_v = max(4, int(8 * cs))
                            content_h = max(18, h - 2 * padding_v)
                            icon_px = max(18, min(int(40 * cs), int(content_h * 0.5), int(dep_col_w * 0.16)))
                            font_px = max(10, min(int(18 * cs), int(content_h * 0.28), int(dep_col_w * 0.11)))
                            lr_pad = max(8, int(12 * cs))
                            border_rad = max(8, int(12 * cs))

                            btn.setIconSize(QSize(icon_px, icon_px))

                            # original text
                            orig = getattr(btn, '_orig_text', btn.text()).replace('\n', ' ')
                            # if an explicit display override exists use it and skip dynamic splitting
                            display_override = getattr(btn, '_display_override', None)

                            qf = QFont()
                            qf.setPixelSize(font_px)
                            fm = QFontMetrics(qf)
                            allowed_w = dep_col_w - icon_px - lr_pad - 12
                            if allowed_w < 48:
                                allowed_w = max(48, int(dep_col_w * 0.6))

                            # prefer split into two lines if possible
                            def _split_dept(txt):
                                if fm.horizontalAdvance(txt) <= allowed_w:
                                    return txt
                                words = txt.split()
                                for i in range(1, len(words)):
                                    l1 = ' '.join(words[:i])
                                    l2 = ' '.join(words[i:])
                                    if fm.horizontalAdvance(l1) <= allowed_w and fm.horizontalAdvance(l2) <= allowed_w:
                                        return l1 + '\n' + l2
                                # fallback elide
                                return fm.elidedText(txt, Qt.ElideRight, allowed_w)

                            if display_override:
                                # use the explicit display text (it may contain a newline) and do not override it
                                if btn.text() != display_override:
                                    btn.setText(display_override)
                            else:
                                try:
                                    o = orig.lower()
                                    forced = None
                                    if (('repuesto' in o or 'repuestos' in o) and ('moto' in o or 'motos' in o)):
                                        forced = 'Repuestos\nde moto'
                                    elif (('repuesto' in o or 'repuestos' in o) and ('auto' in o or 'autos' in o)):
                                        forced = 'Repuestos\nde Autos'

                                    if forced:
                                        if btn.text() != forced:
                                            btn.setText(forced)
                                    else:
                                        new_text = _split_dept(orig)
                                        if new_text != btn.text():
                                            btn.setText(new_text)
                                except Exception:
                                    new_text = _split_dept(orig)
                                    if new_text != btn.text():
                                        btn.setText(new_text)

                            btn.setStyleSheet(f"QPushButton {{ background:#D9CBFF; border-radius:{border_rad}px; font-weight:700; font-size:{font_px}px; color:#4A3BA5; padding:{padding_v}px {lr_pad}px; text-align:left;}} QPushButton:hover {{ background:#C8B5FF; }}")
                        except Exception:
                            pass
                    self._reflow_grid(self.dep_grid, self.dept_buttons, dept_num_cols, cs)
                    try:
                        self.dept_title.setFixedHeight(int(42 * cs))
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _reflow_grid(self, grid, buttons, num_cols, cs=1.0):
        try:
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget()
                if widget:
                    try:
                        grid.removeWidget(widget)
                    except Exception:
                        pass
        except Exception:
            pass
        for i, btn in enumerate(buttons):
            row = i // num_cols
            col = i % num_cols
            try:
                grid.addWidget(btn, row, col)
            except Exception:
                pass
        if len(buttons) % num_cols != 0:
            try:
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                grid.addWidget(spacer, len(buttons)//num_cols, len(buttons)%num_cols)
            except Exception:
                pass
        try:
            grid.setHorizontalSpacing(int(28*cs))
            grid.setVerticalSpacing(int(18*cs))
            grid.setContentsMargins(int(12*cs), int(12*cs), int(12*cs), int(12*cs))
        except Exception:
            pass

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        try:
            self.apply_layout_scale()
        except Exception:
            pass

    # ---------------- BCV helpers ----------------
    def _refresh_bcv_display(self):
        try:
            rate, ts = get_current_bcv_rate_safe()
            if rate:
                self.bcv_value.setText(f"{float(rate):,.6f} Bs/USD")
                if ts:
                    try:
                        self.bcv_time.setText("Actualizada: " + str(ts)[:19].replace("T", " "))
                    except Exception:
                        self.bcv_time.setText(str(ts))
            else:
                self.bcv_value.setText("--")
                self.bcv_time.setText("Sin datos")
        except Exception:
            self.bcv_value.setText("--")
            self.bcv_time.setText("Error")

    def update_bcv_from_web(self):
        try:
            from main import fetch_bcv_rate
            rate, ts = fetch_bcv_rate()
            if rate:
                QMessageBox.information(self, "BCV", f"Tasa actualizada: {rate} Bs/USD")
            else:
                QMessageBox.warning(self, "BCV", "No se pudo obtener la tasa BCV.")
        except Exception as e:
            QMessageBox.warning(self, "BCV", f"Error al obtener tasa: {e}")
        self._refresh_bcv_display()

    def set_bcv_manual(self):
        val, ok = QInputDialog.getText(self, "Ingresar tasa BCV", "Ingrese tasa (Bs/USD):")
        if ok and val:
            try:
                from main import set_current_bcv_rate
                v = float(str(val).replace(",", "."))
                if set_current_bcv_rate(v):
                    QMessageBox.information(self, "BCV", f"Tasa establecida: {v} Bs/USD")
            except Exception as e:
                QMessageBox.warning(self, "BCV", f"Error: {e}")
        self._refresh_bcv_display()

    # ======= Open panels (unchanged) =======
    def open_productos(self):
        try:
            from modules.productos import ProductosWindow
            dlg = ProductosWindow(self)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
            self.refresh_totals()
            if self.notification_mgr:
                QTimer.singleShot(0, lambda: self.notification_mgr.evaluate_and_show(self.db))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Ingresar Producto: {e}")

    def open_entradas(self):
        try:
            # Abrir el Carrito de Entradas como pantalla completa (igual que Ventas)
            from modules.compras_carrito import ComprasCarritoWidget
            self.compras_widget = ComprasCarritoWidget(db=self.db, parent=self)
            try:
                self.compras_widget.venta_completada.connect(self._on_venta_completada)
            except Exception:
                pass
            try:
                self.compras_widget.volver_solicitado.connect(self.restore_dashboard_view)
            except Exception:
                pass
            self._mostrar_pantalla_completa(self.compras_widget)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Carrito de Entradas: {e}")

    # ======= NUEVO: Sistema de Ventas Profesional Integrado =======
    def open_ventas(self):
        """Abre el sistema de ventas ocupando TODA la pantalla (sin sidebar)"""
        try:
            from modules.ventas_integrado import VentasIntegradoWidget
            
            self.ventas_widget = VentasIntegradoWidget(db=self.db, parent=self)
            self.ventas_widget.venta_completada.connect(self._on_venta_completada)
            self.ventas_widget.volver_solicitado.connect(self.restore_dashboard_view)
            
            # Ocultar sidebar y mostrar ventas en pantalla completa
            self._mostrar_pantalla_completa(self.ventas_widget)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Sistema de Ventas: {e}")

    def _mostrar_pantalla_completa(self, widget):
        """Muestra un widget ocupando toda la ventana (oculta sidebar y dashboard)"""
        try:
            # Ocultar todos los widgets actuales
            for i in range(self.central_layout.count()):
                item = self.central_layout.itemAt(i)
                if item and item.widget():
                    item.widget().hide()
            
            # Agregar el nuevo widget si no está ya
            if widget not in [self.central_layout.itemAt(i).widget() 
                             for i in range(self.central_layout.count()) 
                             if self.central_layout.itemAt(i).widget()]:
                self.central_layout.addWidget(widget, 1)
            
            widget.show()
            self._current_content_widget = widget
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo mostrar pantalla completa: {e}")

    def restore_dashboard_view(self):
        """Restaura la vista normal del dashboard con sidebar"""
        try:
            # Ocultar widget actual si existe
            if self._current_content_widget is not None:
                self._current_content_widget.hide()
            
            # Mostrar sidebar (primer widget) y dashboard container
            for i in range(self.central_layout.count()):
                item = self.central_layout.itemAt(i)
                widget = item.widget() if item else None
                if widget and widget != self._current_content_widget:
                    widget.show()
            
            # Asegurar que el dashboard container sea el visible
            if self.dashboard_container not in [self.central_layout.itemAt(i).widget() 
                                               for i in range(self.central_layout.count())]:
                self.central_layout.addWidget(self.dashboard_container, 1)
            
            self.dashboard_container.show()
            self._current_content_widget = self.dashboard_container
            
            # Refrescar datos
            self.refresh_totals()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo restaurar vista: {e}")

    def _on_venta_completada(self, venta_data):
        """Callback cuando se completa una venta en el sistema de ventas"""
        # Actualizar totales del dashboard
        self.refresh_totals()
        
        # Actualizar notificaciones (stock bajo, caducidad)
        if self.notification_mgr:
            QTimer.singleShot(0, lambda: self.notification_mgr.evaluate_and_show(self.db))
        
        # Mostrar resumen en status bar
        total = venta_data['totales']['total_bs']
        num_productos = len(venta_data['productos'])
        cliente = venta_data.get('cliente', {}).get('nombre', 'General')
        self.statusBar().showMessage(
            f"✅ Venta {venta_data['numero_factura']}: {num_productos} productos a {cliente} - Total: {total:,.2f} Bs", 
            5000
        )

    def _on_venta_completada(self, venta_data):
        """Callback cuando se completa una venta en el sistema de ventas"""
        # Actualizar totales del dashboard
        self.refresh_totals()
        
        # Actualizar notificaciones (stock bajo, caducidad)
        if self.notification_mgr:
            QTimer.singleShot(0, lambda: self.notification_mgr.evaluate_and_show(self.db))
        
        # Mostrar resumen en status bar
        total = venta_data['totales']['total_bs']
        num_productos = len(venta_data['productos'])
        self.statusBar().showMessage(
            f"✅ Venta {venta_data['numero_factura']}: {num_productos} productos - Total: {total:,.2f} Bs", 
            5000
        )

    # ======= Mantener compatibilidad con salidas antiguo =======
    def open_salidas_legacy(self):
        """Mantiene el acceso al sistema de salidas antiguo por compatibilidad"""
        try:
            from modules.salidas import SalidasWindow
            self.ventana_salidas = SalidasWindow(self)
            self.ventana_salidas.venta_finalizada.connect(self._on_venta_completada)
            self.ventana_salidas.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Registro de Salidas: {e}")

    def open_registro_general(self):
        try:
            from modules.registro_general import RegistroGeneralWindow
            dlg = RegistroGeneralWindow(self)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Registro General: {e}")

    def open_reportes(self):
        try:
            from modules.reportes import ReportesWindow
            dlg = ReportesWindow(self)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Reportes: {e}")

    def open_caducidad(self):
        try:
            from modules.caducidad import CaducidadWindow
            dlg = CaducidadWindow(self)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
            self.refresh_totals()
            if self.notification_mgr:
                QTimer.singleShot(0, lambda: self.notification_mgr.evaluate_and_show(self.db))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Caducidad: {e}")

    def open_reporte_filtrado(self, departamento):
        try:
            from modules.registro_general import RegistroGeneralWindow
            dlg = RegistroGeneralWindow(self, departamento=departamento)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir reporte filtrado: {e}")

    def open_graficos(self):
        try:
            from modules.graficos import GraficosWindow
            dlg = GraficosWindow(self)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec_()
        except Exception:
            QMessageBox.information(self, "Gráficos", "Gráficos por mes - función en desarrollo.")

    def open_acerca(self):
        QMessageBox.information(self, "Acerca", "Minimarket ChiChi N-K, C.A\nRIF: J-5099900-7\nVersión: 2.0\nSistema de Inventario")

    def open_theme_editor(self):
        try:
            from modules.theme_editor import ThemeEditor
            dlg = ThemeEditor(self)
            # show modeless so the dialog is visible before any subdialogs
            try:
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                # fallback to modal exec if show fails
                dlg.setWindowModality(Qt.ApplicationModal)
                dlg.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Temas", f"No se pudo abrir editor de temas: {e}")

    def open_cierre_diario(self):
        try:
            from modules.cierre_diario import DialogoCierreDiario
            dlg = DialogoCierreDiario(self.db, self)
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Cierre Diario: {e}")

    def cerrar_sesion(self):
        self.close()

    # ------------------------------------------------------------------
    # Methods to swap main content with a full-screen widget (Libros / Inventario)
    # ------------------------------------------------------------------
    def show_only_widget(self, widget):
        try:
            if self._current_content_widget is not None:
                try:
                    self.central_layout.removeWidget(self._current_content_widget)
                    self._current_content_widget.setParent(None)
                except Exception:
                    pass
            self.central_layout.addWidget(widget, 1)
            self._current_content_widget = widget
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo mostrar la vista: {e}")

    def restore_dashboard_view(self):
        try:
            # Remove current content widget if it's not the dashboard container
            if self._current_content_widget is not None and self._current_content_widget is not self.dashboard_container:
                try:
                    self.central_layout.removeWidget(self._current_content_widget)
                    self._current_content_widget.setParent(None)
                except Exception:
                    pass
            # Ensure sidebar and any other widgets are visible again
            for i in range(self.central_layout.count()):
                item = self.central_layout.itemAt(i)
                widget = item.widget() if item else None
                if widget:
                    widget.show()
            # Ensure the dashboard container is present and visible
            if self.dashboard_container not in [self.central_layout.itemAt(i).widget()
                                               for i in range(self.central_layout.count())]:
                self.central_layout.addWidget(self.dashboard_container, 1)
            self.dashboard_container.show()
            self._current_content_widget = self.dashboard_container
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo restaurar vista: {e}")

    def open_libro(self, tipo):
        try:
            from modules.libros import LibrosWidget
            w = LibrosWidget(parent=self, default_book=tipo)
            self.show_only_widget(w)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir libro: {e}")

    # ======= Totales (backend) =======
    def refresh_totals(self):
        """
        Recalcula los totales en backend.
        """
        try:
            # Total físico
            total_fisico = 0
            try:
                if hasattr(self.db, 'get_total_inventario_fisico'):
                    total_fisico = int(self.db.get_total_inventario_fisico())
                else:
                    r = self.db.fetchone("SELECT SUM(COALESCE(stock,0.0)) AS total_stock FROM productos")
                    total_fisico = int(float(r.get('total_stock') or 0.0))
            except Exception:
                total_fisico = 0

            # Total valorizado USD
            total_val_usd = D('0')
            try:
                row = self.db.fetchone("SELECT SUM( COALESCE(stock,0.0) * COALESCE(precio_final,0.0) ) AS total_usd FROM productos")
                if row and row.get('total_usd') is not None:
                    total_val_usd = D(row.get('total_usd') or 0)
            except Exception:
                try:
                    rows = self.db.fetchall("SELECT COALESCE(stock,0.0) AS stock, COALESCE(precio_final,0.0) AS precio_final FROM productos") or []
                    s = D('0')
                    for r in rows:
                        s += (D(r.get('stock') or 0) * D(r.get('precio_final') or 0))
                    total_val_usd = s
                except Exception:
                    total_val_usd = D('0')

            # Convert to BS using system BCV rate for display (rate from main)
            rate, ts = get_current_bcv_rate_safe()
            total_val_bs = None
            if rate and rate != D('0'):
                try:
                    total_val_bs = (total_val_usd * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                except Exception:
                    total_val_bs = None

            try:
                if hasattr(self, "tf_value"):
                    self.tf_value.setText(str(total_fisico))
                if hasattr(self, "tv_value"):
                    if self._total_currency == 'Bs':
                        if total_val_bs is not None:
                            self.tv_value.setText(format_bs_decimal(total_val_bs))
                        else:
                            if total_val_usd is not None:
                                self.tv_value.setText(format_usd_decimal(total_val_usd) + "  (sin tasa)")
                            else:
                                self.tv_value.setText("0.00 Bs")
                    else:
                        self.tv_value.setText(format_usd_decimal(total_val_usd))
            except Exception:
                pass

        except Exception as e:
            print("Error refreshing totals:", e)

    # ---------------- Inventory view (delegated to modules/inventario.InventoryViewWidget) ----------------
    def open_inventory(self):
        """
        Crea y muestra InventoryViewWidget en la zona principal (sin popup).
        """
        try:
            from modules.inventario import InventoryViewWidget
            w = InventoryViewWidget(db=self.db, parent=self)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameStyle(QFrame.NoFrame)
            scroll.setWidget(w)
            self.show_only_widget(scroll)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir Inventario: {e}")

    # ---------------- Cleanup ----------------
    def closeEvent(self, ev):
        try:
            if self._expiry_timer:
                self._expiry_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)
