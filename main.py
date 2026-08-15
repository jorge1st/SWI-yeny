# main.py
"""
Punto de entrada + utilidades BCV en memoria.
La tasa BCV vive solo en memoria (no se guarda en BD ni archivo).
Contiene:
- fetch_bcv_rate(): busca la tasa en https://www.bcv.org.ve/ (fallback SSL)
- get_current_bcv_rate(), set_current_bcv_rate()
- ensure_db_migrations(): agrega columnas mínimas a productos si faltan (no borra)
- Inicio de la app (login -> splash -> dashboard)
"""

import sys
import datetime
from pathlib import Path
import sqlite3
import os

# requests y bs4 se usan para fetch web
try:
    import requests
    from requests.exceptions import SSLError, RequestException
    from bs4 import BeautifulSoup
except Exception:
    # Si no están instaladas, la app seguirá funcionando, solo que no podrá obtener la tasa automáticamente.
    requests = None
    SSLError = RequestException = Exception
    BeautifulSoup = None

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication

# RUTA BD (ajusta si tu DB tiene otro nombre)
DB_PATH = Path("inventory.db")

# Tasa BCV en memoria (no persistente)
GLOBAL_BCV_RATE = None
GLOBAL_BCV_TIMESTAMP = None

# Factor de escala UI (base 1.0). Se actualiza en tiempo de ejecución si main detecta pantalla mayor.
UI_SCALE = 1.0

def get_ui_scale():
    """Devuelve el factor de escala actualmente aplicado a la UI (float)."""
    return UI_SCALE



def ensure_db_migrations():
    """
    Asegura columnas mínimas en la tabla productos para compatibilidad con los nuevos campos.
    No elimina ni modifica datos existentes, solo intenta agregar columnas si faltan.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
        if cur.fetchone():
            cur.execute("PRAGMA table_info('productos')")
            cols = [r[1] for r in cur.fetchall()]
            required = {
                "costo_compra": "REAL DEFAULT 0.0",
                "iva": "REAL DEFAULT 0.0",
                "ganancia": "REAL DEFAULT 0.0",
                "moneda": "TEXT DEFAULT '$'",
                "precio_final": "REAL DEFAULT 0.0"
            }
            for col, spec in required.items():
                if col not in cols:
                    try:
                        cur.execute(f"ALTER TABLE productos ADD COLUMN {col} {spec}")
                    except Exception:
                        # no interrumpir si falla (es posible que el esquema sea complejo)
                        pass
        conn.commit()
        conn.close()
    except Exception as e:
        print("ensure_db_migrations warning:", e)


def fetch_bcv_rate():
    """
    Intenta obtener la tasa BCV del sitio oficial. Retorna (rate: float | None, timestamp_iso: str | None).
    - Si requests/bs4 no están instalados, retorna (None, None).
    - Si hay problemas de verificación de certificados, reintenta con verify=False.
    Actualiza variables GLOBAL_BCV_RATE / GLOBAL_BCV_TIMESTAMP en memoria.
    """
    global GLOBAL_BCV_RATE, GLOBAL_BCV_TIMESTAMP

    if requests is None or BeautifulSoup is None:
        print("fetch_bcv_rate: requests/bs4 no disponibles.")
        return None, None

    url = "https://www.bcv.org.ve/"
    try:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except SSLError:
            # Fallback si hay problema con certificados locales
            resp = requests.get(url, timeout=10, verify=False)
            resp.raise_for_status()
        except RequestException as e:
            print("fetch_bcv_rate request error:", e)
            return None, None

        soup = BeautifulSoup(resp.text, "html.parser")
        dolar_div = soup.find("div", {"id": "dolar"}) or soup.find(id="dolar")
        raw = None
        if dolar_div:
            strong = dolar_div.find("strong")
            raw = strong.get_text(strip=True) if strong else dolar_div.get_text(" ", strip=True)
        else:
            # fallback: buscar patrón USD y número cercano
            text = soup.get_text(" ", strip=True)
            import re
            m = re.search(r"USD[^0-9\d]{0,8}(\d+[.,]\d+)", text)
            if m:
                raw = m.group(1)

        if not raw:
            return None, None

        # Normalizar número
        raw = raw.strip().replace(" ", "")
        raw = raw.replace(".", "") if raw.count(".") > 1 and "," in raw else raw
        raw = raw.replace(",", ".")
        import re
        m2 = re.search(r"(\d+\.\d+|\d+)", raw)
        if not m2:
            return None, None
        val = float(m2.group(1))
        ts = datetime.datetime.now().isoformat()
        GLOBAL_BCV_RATE = val
        GLOBAL_BCV_TIMESTAMP = ts
        print(f"[fetch_bcv_rate] tasa obtenida: {val} Bs/USD")
        return val, ts
    except Exception as e:
        print("fetch_bcv_rate error:", e)
        return None, None


def get_current_bcv_rate():
    """Devuelve (rate, timestamp) actuales desde memoria."""
    global GLOBAL_BCV_RATE, GLOBAL_BCV_TIMESTAMP
    return GLOBAL_BCV_RATE, GLOBAL_BCV_TIMESTAMP


def set_current_bcv_rate(rate):
    """Establece la tasa BCV en memoria (no persistente). Devuelve True/False."""
    global GLOBAL_BCV_RATE, GLOBAL_BCV_TIMESTAMP
    try:
        r = float(str(rate).replace(",", "."))
        GLOBAL_BCV_RATE = r
        GLOBAL_BCV_TIMESTAMP = datetime.datetime.now().isoformat()
        print(f"[set_current_bcv_rate] tasa establecida: {r}")
        return True
    except Exception as e:
        print("set_current_bcv_rate error:", e)
        return False


if __name__ == "__main__":
    # Aplicar migraciones mínimas
    ensure_db_migrations()

    # Intentar obtener tasa al iniciar (no fatal)
    try:
        fetch_bcv_rate()
    except Exception:
        pass

    # Calcular factor de escala basado en resolución de pantalla (base 1366x768)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        base_w, base_h = 1366.0, 768.0
        scale_w = screen_w / base_w if base_w else 1.0
        scale_h = screen_h / base_h if base_h else 1.0
        scale = min(scale_w, scale_h)
        if scale <= 0:
            scale = 1.0
        # apply scaling only if larger than 1 (don't shrink for smaller screens)
        if scale > 1.0:
            os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
            os.environ['QT_SCALE_FACTOR'] = str(scale)
            # Ensure Qt high-DPI attributes are enabled
            try:
                QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
                QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            except Exception:
                pass
            # Actualizar factor global para módulos que lo consulten
            UI_SCALE = scale
    except Exception:
        pass

    app = QApplication(sys.argv)

    # Adjust global font size based on UI scale so widgets that use default fonts scale
    try:
        from modules.ui_scaling import get_ui_scale
        s = get_ui_scale()
        if s and s > 1.0:
            f = app.font()
            try:
                f.setPointSizeF(f.pointSizeF() * s)
            except Exception:
                f.setPointSize(max(1, int(f.pointSize() * s)))
            app.setFont(f)
    except Exception:
        pass

    # Import tardío para evitar circularidad
    try:
        from modules.login import LoginWindow
        from modules.dashboard import DashboardWindow
    except Exception as e:
        print("Error importando ventanas (revisa modules/login.py y modules/dashboard.py):", e)
        sys.exit(1)

    # Build and load theme-based styles (module-based QSS). Fall back to older lookup if necessary.
    try:
        try:
            from modules import theme_manager
            # build styles.qss from styles/modules and palettes (no-op if already up-to-date)
            try:
                theme_manager.build_and_write_styles()
            except Exception:
                pass
        except Exception:
            pass

        # Cargar estilo si existe (busca en rutas de bundle y cwd)
        base = getattr(sys, '_MEIPASS', None)
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'executable', None) else None
        candidates = []
        if base:
            candidates.append(os.path.join(base, 'styles.qss'))
        if exe_dir:
            candidates.append(os.path.join(exe_dir, 'styles.qss'))
            candidates.append(os.path.join(exe_dir, '_internal', 'styles.qss'))
        candidates.append(os.path.join(os.path.abspath(os.getcwd()), 'styles.qss'))
        candidates.append(os.path.join(os.path.abspath(os.getcwd()), '_internal', 'styles.qss'))
        for p in candidates:
            if p and os.path.isfile(p):
                with open(p, 'r', encoding='utf-8') as f:
                    qss_text = f.read()
                    try:
                        from modules.ui_scaling import scale_qss
                        qss_text = scale_qss(qss_text)
                    except Exception:
                        pass
                    app.setStyleSheet(qss_text)
                break
    except Exception:
        pass

    # 1) Show login first
    login = LoginWindow()
    if login.exec_() == LoginWindow.Accepted:
        # 2) After successful login, show the splash that must be closed by clicking
        try:
            from modules.splash import SplashWindow
            splash = SplashWindow()
            # This exec_() will block until the user clicks anywhere or presses "Continuar"
            splash.exec_()
        except Exception as e:
            # If splash fails for any reason, continue to dashboard
            print("Warning: splash failed to show:", e)

        # 3) Open dashboard
        dashboard = DashboardWindow()
        # Start dashboard maximized
        dashboard.showMaximized()
        sys.exit(app.exec_())
    else:
        # Login cancelled -> exit
        sys.exit(0)
