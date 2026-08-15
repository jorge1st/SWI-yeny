# modules/notification.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtSlot, QObject
from PyQt5.QtGui import QColor, QFont
import datetime
import math

# NotificationManager singleton that can be called from anywhere:
# from modules.notification import NotificationManager
# NotificationManager.instance().evaluate_and_show(db)  # db is DBManager instance
#
# AnimatedNotification created/managed internally by the manager.


class AnimatedNotification(QWidget):
    """Floating notification: expands, shows list, auto-collapses to persistent badge.
       - click badge to expand back
       - clicking list item opens ProductDetail if caller sets a callback
    """
    def __init__(self, parent=None, items=None, auto_collapse_ms=3000, open_item_cb=None, title="Productos por caducar / vencidos"):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, False)
        self.parent_win = parent
        self.items = items or []
        self.open_item_cb = open_item_cb  # callback(product_id)
        self.auto_collapse_ms = auto_collapse_ms
        self.title_text = title

        # appearance config
        self._expanded_w = 360
        self._expanded_h = 160
        self._badge_d = 48
        try:
            from modules.ui_scaling import scale_px

            if s and float(s) > 1.0:
                self._expanded_w = max(1, int(round(self._expanded_w * float(s))))
                self._expanded_h = max(1, int(round(self._expanded_h * float(s))))
                self._badge_d = max(1, int(round(self._badge_d * float(s))))
        except Exception:
            pass

        self._collapsed = False

        self._build_ui()
        self._setup_anims()

    def _build_ui(self):
        # card
        self.card = QWidget(self)
        self.card.setObjectName("card")
        # High-contrast styling: white card, lavanda accent, red badge
        self.card.setStyleSheet("""
            QWidget#card {
                background: #FFFFFF;
                border-radius: 12px;
                border: 1px solid rgba(94,61,179,0.12);
            }
            QLabel.title {
                color: #5E3DB3;
                font-weight: 800;
                font-size: 13px;
            }
            QListWidget { background: transparent; border: none; }
            QListWidget::item { padding: 6px 4px; color: #2E2E2E; }
            QPushButton.badge {
                background: #E74C3C;
                color: white;
                border-radius: 24px;
                font-weight:700;
            }
        """)
        v = QVBoxLayout(self.card)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        title = QLabel(self.title_text)
        title.setObjectName("title")
        title.setProperty("class", "title")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        v.addWidget(title)

        # compact list: name — días
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        v.addWidget(self.list_widget, 1)

        h = QHBoxLayout()
        h.addStretch()
        self.view_all_btn = QPushButton("Ver lista completa")
        self.view_all_btn.setCursor(Qt.PointingHandCursor)
        self.view_all_btn.setStyleSheet("background: transparent; color: #5E3DB3; border: none; font-weight:700;")
        h.addWidget(self.view_all_btn)
        self.close_btn = QPushButton("Cerrar")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("background: transparent; color: #666; border: none;")
        h.addWidget(self.close_btn)
        v.addLayout(h)

        # collapsed badge (initially hidden)
        self.badge = QPushButton("", self)
        self.badge.setObjectName("badge")
        self.badge.setVisible(False)
        self.badge.setCursor(Qt.PointingHandCursor)
        self.badge.setStyleSheet("""
            QPushButton#badge {
                background: #E74C3C;
                color: white;
                border-radius: 24px;
                font-weight:700;
                padding: 6px;
            }
            QPushButton#badge:hover { background: #ff6b6b; }
        """)

        # connections
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.view_all_btn.clicked.connect(self._on_view_all)
        self.close_btn.clicked.connect(self.dismiss)
        self.badge.clicked.connect(self.expand_from_badge)

        # timers
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.collapse_to_badge)

        # size
        self.resize(self._expanded_w, self._expanded_h)
        self.card.resize(self._expanded_w, self._expanded_h)

    def _setup_anims(self):
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(260)
        self.opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(360)
        self.geom_anim.setEasingCurve(QEasingCurve.OutCubic)

    def update_items(self, items):
        self.items = items or []
        self._refresh_list()
        # update badge text if collapsed
        if self._collapsed:
            self._update_badge_text()

    def _refresh_list(self):
        self.list_widget.clear()
        for it in self.items:
            name = it.get('nombre') or it.get('codigo') or '—'
            parts = []
            # caducidad part
            dias = it.get("dias")
            if dias is None and ('stock' not in it):
                dias_text = "Sin fecha"
            elif dias is not None:
                if dias < 0:
                    dias_text = f"Vencido ({abs(dias)}d)"
                elif dias == 0:
                    dias_text = "Hoy"
                elif dias == 1:
                    dias_text = "1 día"
                else:
                    dias_text = f"{dias} días"
                parts.append(dias_text)
            # stock part
            if 'stock' in it and it.get('stock') is not None:
                stock = it.get('stock')
                try:
                    stock_display = str(int(float(stock))) if float(stock).is_integer() else f"{float(stock):,.3f}"
                except Exception:
                    stock_display = str(stock)
                parts.append(f"{stock_display} und")
            label = f"{name} — " + " — ".join(parts) if parts else name
            li = QListWidgetItem(label)
            li.setData(Qt.UserRole, it)
            self.list_widget.addItem(li)
        self._update_badge_text()

    def _update_badge_text(self):
        c = len(self.items or [])
        if c <= 0:
            self.badge.setText("")
        else:
            self.badge.setText(str(c) if c < 100 else "99+")

    def show_with_animation(self):
        # schedule actual show a bit later so parent geometry exists
        QTimer.singleShot(10, self._do_show)

    def _do_show(self):
        try:
            self._refresh_list()
            geom = self._expanded_geometry()
            self.setGeometry(geom)
            self.setWindowOpacity(0.0)
            self.show()
            self.raise_()
            self.opacity_anim.stop()
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.opacity_anim.start()
            if self.auto_collapse_ms and self.auto_collapse_ms > 0:
                self._auto_timer.start(self.auto_collapse_ms)
        except Exception:
            try:
                self.show()
            except Exception:
                pass

    def _expanded_geometry(self):
        margin = 12
        w = self._expanded_w
        h = self._expanded_h
        try:
            if self.parent_win and self.parent_win.isVisible():
                pw = self.parent_win.frameGeometry()
                x = pw.x() + pw.width() - w - margin
                y = pw.y() + pw.height() - h - margin
            else:
                scr = QApplication.primaryScreen().availableGeometry()
                x = scr.x() + scr.width() - w - margin
                y = scr.y() + scr.height() - h - margin
        except Exception:
            scr = QApplication.primaryScreen().availableGeometry()
            x = scr.x() + scr.width() - w - margin
            y = scr.y() + scr.height() - h - margin
        return QRect(int(x), int(y), int(w), int(h))

    def _badge_geometry(self):
        d = self._badge_d
        try:
            if self.parent_win and self.parent_win.isVisible():
                pw = self.parent_win.frameGeometry()
                x = pw.x() + pw.width() - (d // 2)
                y = pw.y() + (pw.height() // 2) - (d // 2)
            else:
                scr = QApplication.primaryScreen().availableGeometry()
                x = scr.x() + scr.width() - (d // 2)
                y = scr.y() + (scr.height() // 2) - (d // 2)
        except Exception:
            scr = QApplication.primaryScreen().availableGeometry()
            x = scr.x() + scr.width() - (d // 2)
            y = scr.y() + (scr.height() // 2) - (d // 2)
        x = max(x - d, 8)
        return QRect(int(x), int(y), int(d), int(d))

    @pyqtSlot()
    def collapse_to_badge(self):
        if self._collapsed:
            return
        self._collapsed = True
        end_geom = self._badge_geometry()
        start_geom = self.geometry()
        self.geom_anim.stop()
        try:
            self.geom_anim.finished.disconnect()
        except Exception:
            pass
        self.geom_anim.setStartValue(start_geom)
        self.geom_anim.setEndValue(end_geom)

        def on_end():
            try:
                self.card.setVisible(False)
                self.badge.setVisible(True)
                self.badge.setGeometry(0, 0, end_geom.width(), end_geom.height())
                self.setWindowOpacity(1.0)
            except Exception:
                pass

        self.geom_anim.finished.connect(on_end)
        self.geom_anim.start()

    @pyqtSlot()
    def expand_from_badge(self):
        if not self._collapsed:
            return
        start = self.geometry()
        end = self._expanded_geometry()
        self.card.setVisible(True)
        self.badge.setVisible(False)
        try:
            self.geom_anim.finished.disconnect()
        except Exception:
            pass
        self.geom_anim.stop()
        self.geom_anim.setStartValue(start)
        self.geom_anim.setEndValue(end)

        def on_finished():
            try:
                self._collapsed = False
                self._refresh_list()
                if self.auto_collapse_ms and self.auto_collapse_ms > 0:
                    self._auto_timer.start(self.auto_collapse_ms)
            except Exception:
                pass

        self.geom_anim.finished.connect(on_finished)
        self.geom_anim.start()

    def dismiss(self):
        try:
            self.hide()
            self.deleteLater()
        except Exception:
            pass

    def _on_item_clicked(self, item):
        it = item.data(Qt.UserRole) or {}
        pid = it.get("id")
        if self.open_item_cb and pid:
            try:
                self.open_item_cb(pid)
            except Exception:
                pass
        # collapse after opening
        if not self._collapsed:
            self.collapse_to_badge()

    def _on_view_all(self):
        # caller should bind to this button if desired (manager will)
        # by default, just collapse
        if not self._collapsed:
            self.collapse_to_badge()


class NotificationManager(QObject):
    """Singleton manager to evaluate DB and show AnimatedNotification accordingly."""
    _instance = None

    def __init__(self, parent=None, days=3, auto_collapse_ms=3000):
        super().__init__(parent)
        self.parent = parent  # usually dashboard window
        self.days = days
        self.auto_collapse_ms = auto_collapse_ms
        self.widget = None
        self._last_ids = set()

    @classmethod
    def instance(cls, parent=None, days=3, auto_collapse_ms=3000):
        if cls._instance is None:
            cls._instance = NotificationManager(parent=parent, days=days, auto_collapse_ms=auto_collapse_ms)
        return cls._instance

    def evaluate_and_show(self, db):
        """Query DBManager (db) for low-stock products and products near/over expiry and show/update notification."""
        try:
            if db is None:
                return
            LOW_STOCK_THRESHOLD = 10
            NOTIFY_MIN_COUNT = 1

            items_map = {}
            # low stock rows
            try:
                if hasattr(db, "listar_stock_bajo"):
                    stock_rows = db.listar_stock_bajo(LOW_STOCK_THRESHOLD) or []
                else:
                    stock_rows = db.fetchall(
                        "SELECT id,codigo,nombre,COALESCE(stock,0) as stock FROM productos WHERE COALESCE(stock,0) <= ? ORDER BY stock ASC",
                        (LOW_STOCK_THRESHOLD,))
            except Exception:
                stock_rows = []

            for r in stock_rows:
                pid = r.get("id")
                key = str(pid)
                it = items_map.get(key, {"id": pid, "codigo": r.get("codigo"), "nombre": r.get("nombre")})
                it["stock"] = r.get("stock")
                items_map[key] = it

            # expiry rows
            try:
                cad_rows = db.fetchall("SELECT id,codigo,nombre,fecha_caducidad FROM productos WHERE fecha_caducidad IS NOT NULL AND fecha_caducidad != ''")
            except Exception:
                cad_rows = []
            today = datetime.date.today()
            for r in cad_rows:
                pid = r.get("id")
                fecha_raw = r.get("fecha_caducidad") or ""
                try:
                    fecha_dt = datetime.datetime.strptime(str(fecha_raw)[:10], "%Y-%m-%d").date()
                except Exception:
                    continue
                dias = (fecha_dt - today).days
                # include expired or near expiry
                if dias <= self.days:
                    key = str(pid)
                    it = items_map.get(key, {"id": pid, "codigo": r.get("codigo"), "nombre": r.get("nombre")})
                    it["dias"] = dias
                    items_map[key] = it

            items = list(items_map.values())
            # sort: items with dias first (ascending), then stock ascending
            items_with_dias = sorted([it for it in items if it.get("dias") is not None], key=lambda x: int(x.get("dias")))
            items_with_stock_only = sorted([it for it in items if it.get("dias") is None and it.get("stock") is not None], key=lambda x: float(x.get("stock") or 0))
            items_sorted = items_with_dias + items_with_stock_only
            display_items = items_sorted[:8]
            ids = {str(it.get('id')) for it in items_sorted if it.get('id') is not None}

            if len(items_sorted) >= NOTIFY_MIN_COUNT:
                if ids and ids == self._last_ids and self.widget:
                    try:
                        self.widget.update_items(display_items)
                    except Exception:
                        pass
                    return
                self._last_ids = ids
                if self.widget:
                    try:
                        self.widget.update_items(display_items)
                    except Exception:
                        pass
                else:
                    try:
                        title = "Stock bajo / Caducidad"
                        self.widget = AnimatedNotification(parent=self.parent, items=display_items, auto_collapse_ms=self.auto_collapse_ms, open_item_cb=self._open_product_detail, title=title)
                        try:
                            self.widget.view_all_btn.clicked.connect(self._open_caducidad_window)
                        except Exception:
                            pass
                        self.widget.show_with_animation()
                    except Exception:
                        pass
            else:
                # nothing to show: dismiss if exists
                self._last_ids = set()
                if self.widget:
                    try:
                        self.widget.dismiss()
                    except Exception:
                        pass
                    self.widget = None
        except Exception:
            pass

    def _open_product_detail(self, product_id):
        # helper to open ProductDetailDialog if available
        try:
            from modules.product_detail import ProductDetailDialog
            # find parent to use as dialog parent
            parent = self.parent if self.parent is not None else None
            dlg = ProductDetailDialog(parent, db=self.parent.db if hasattr(self.parent, "db") else None, product_id=product_id, product_dict=None)
            dlg.exec_()
            # after possible edit, re-evaluate
            try:
                # small delay to allow commit to finish
                QTimer.singleShot(0, lambda: self.evaluate_and_show(self.parent.db if hasattr(self.parent, "db") else None))
            except Exception:
                pass
        except Exception:
            pass

    def _open_caducidad_window(self):
        try:
            from modules.caducidad import CaducidadWindow
            parent = self.parent if self.parent is not None else None
            dlg = CaducidadWindow(parent)
            dlg.exec_()
            # after possible edits, re-evaluate
            QTimer.singleShot(0, lambda: self.evaluate_and_show(self.parent.db if hasattr(self.parent, "db") else None))
        except Exception:
            pass

