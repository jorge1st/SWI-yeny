# modules/splash.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget,
    QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QEvent, QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup, QEasingCurve, QTimer
from PyQt5.QtGui import QPixmap, QFont
import os

class SplashWindow(QDialog):
    """
    Fullscreen splash shown AFTER login.
    - Starts in fullscreen.
    - Closes only when the user clicks anywhere (including any child widget) or presses the "Continuar" button.
    - Added smooth fade-in and fade-out animations for the whole window and for individual elements
      (logo, system name, company, rif, continue button) to provide a pleasant transition.
    """
    def __init__(self, parent=None):
        # Use Window flag (not just Dialog) so fullscreen works reliably, keep frameless.
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setModal(True)

        # animation state flags
        self._closing = False
        self._showing = False
        self._anim_group_show = None
        self._anim_group_close = None

        self._build_ui()

        # Request fullscreen state
        try:
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)
        except Exception:
            pass

        # Install event filters on all children so any mouse press anywhere closes the splash
        self._install_global_click_filter()

        # Start the show animation slightly after construction so the window is visible and ready.
        QTimer.singleShot(10, self.start_show_animation)

    def _build_ui(self):
        self.setObjectName("splash")
        # Styling moved to styles/modules/splash.qss

        # Use a centered container so content looks good on any screen size
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(80, 60, 80, 60)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignCenter)

        # Larger logo placeholder
        self.logo_lbl = QLabel()
        # size will be scaled relative to screen: we'll compute target from available geometry
        screen = self.screen().availableGeometry() if hasattr(self, "screen") else None
        target_size = 360
        if screen:
            # pick a larger size so the logo is more visible, but cap to reasonable fraction
            w = min(int(screen.width() * 0.28), 640)
            h = min(int(screen.height() * 0.28), 640)
            target_size = max(240, min(w, h))
        self.logo_lbl.setFixedSize(target_size, target_size)
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        self.logo_lbl.setObjectName("logo_lbl")
        self._load_logo()
        layout.addWidget(self.logo_lbl, alignment=Qt.AlignCenter)

        # System name (very large)
        self.sys_lbl = QLabel("Sistema para el control de registro de inventario")
        self.sys_lbl.setObjectName("system_name")
        self.sys_lbl.setWordWrap(True)
        f_sys = QFont()
        f_sys.setPointSize(72 if target_size >= 400 else 56)
        f_sys.setBold(True)
        self.sys_lbl.setFont(f_sys)
        self.sys_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sys_lbl)

        # Company name (large)
        self.comp_lbl = QLabel("Minimarket ChiChi N-K, C.A")
        self.comp_lbl.setObjectName("company")
        f_comp = QFont()
        f_comp.setPointSize(44 if target_size >= 400 else 36)
        f_comp.setBold(True)
        self.comp_lbl.setFont(f_comp)
        self.comp_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.comp_lbl)

        # RIF (medium)
        self.rif_lbl = QLabel("RIF: J-5099900-7")
        self.rif_lbl.setObjectName("rif")
        f_rif = QFont()
        f_rif.setPointSize(32 if target_size >= 400 else 28)
        self.rif_lbl.setFont(f_rif)
        self.rif_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rif_lbl)

        # Spacer and continue button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cont_btn = QPushButton("Continuar")
        self.cont_btn.setObjectName("cont_btn")
        self.cont_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cont_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Put container in the dialog layout so it scales with full screen
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container, alignment=Qt.AlignCenter)

        # Prepare opacity effects for animated widgets
        # We'll animate: logo_lbl, sys_lbl, comp_lbl, rif_lbl, cont_btn
        self._animated_widgets = [
            self.logo_lbl,
            self.sys_lbl,
            self.comp_lbl,
            self.rif_lbl,
            self.cont_btn
        ]
        for w in self._animated_widgets:
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)

        # Start window fully transparent (so window fade-in animates)
        try:
            self.setWindowOpacity(0.0)
        except Exception:
            pass

    def _load_logo(self):
        """
        Try to load a logo from common locations. If none found, show a large text placeholder.
        User can place 'logo.png' at project root or 'img/logo.png'.
        """
        possible = [
            os.path.join(os.getcwd(), "logo.jpeg"),
            os.path.join(os.getcwd(), "img", "logo.jpeg"),
            os.path.join(os.path.dirname(__file__), "..", "logo.png"),
            os.path.join(os.path.dirname(__file__), "..", "img", "logo.png"),
            os.path.join(r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules", "Logo.png"),
            os.path.join(r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules", "Logo.jpg"),
            os.path.join(r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules", "Logo.jpeg"),
            os.path.join(r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules", "Logo.bmp"),
            os.path.join(r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules", "Logo.svg"),
        ]
        pix = None
        for p in possible:
            try:
                p_abs = os.path.abspath(p)
                if os.path.exists(p_abs):
                    pix = QPixmap(p_abs)
                    if not pix.isNull():
                        break
            except Exception:
                continue

        if pix and not pix.isNull():
            scaled = pix.scaled(self.logo_lbl.width(), self.logo_lbl.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_lbl.setPixmap(scaled)
        else:
            # large text placeholder
            self.logo_lbl.setText("LOGO\n(logo.png)")
            # ensure color/style includes the gradient background case
            # Color and weight moved to QSS for #logo_lbl
            f = QFont()
            f.setPointSize(max(12, int(self.logo_lbl.height() / 8)))
            f.setBold(True)
            self.logo_lbl.setFont(f)
            self.logo_lbl.setAlignment(Qt.AlignCenter)

    def _install_global_click_filter(self):
        """
        Install an event filter on all child widgets (including the dialog itself)
        so that any mouse press anywhere will start the close animation.
        """
        # Install on self
        self.installEventFilter(self)
        # Also install on existing children
        for w in self.findChildren(QWidget):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        # If any widget receives a mouse press, start the close animation (instead of immediate close)
        try:
            if event.type() == QEvent.MouseButtonPress:
                # ensure the click triggers a graceful close animation
                self.start_close_animation()
                # consume the event
                return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def accept(self):
        """
        Override accept so that clicking the 'Continuar' button triggers the close animation
        and only after the animation finishes the dialog is accepted.
        """
        # If already closing, do nothing (the close animation will call the base accept).
        if self._closing:
            return
        self.start_close_animation()

    # -------------------- Animations --------------------
    def start_show_animation(self):
        """
        Play a short sequence:
         - Fade window from 0 -> 1
         - Fade child elements in (logo then texts + button) with a pleasant easing
        """
        if self._showing:
            return
        self._showing = True

        # Window fade-in
        win_anim = QPropertyAnimation(self, b"windowOpacity")
        win_anim.setDuration(350)
        win_anim.setStartValue(0.0)
        win_anim.setEndValue(1.0)
        win_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Child fades: we'll fade logo slightly earlier than texts
        anims = []

        # logo fade
        logo_eff = self.logo_lbl.graphicsEffect()
        if logo_eff:
            a = QPropertyAnimation(logo_eff, b"opacity")
            a.setDuration(450)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            anims.append(a)

        # group for texts and button
        parallel = QParallelAnimationGroup()
        for w in (self.sys_lbl, self.comp_lbl, self.rif_lbl, self.cont_btn):
            eff = w.graphicsEffect()
            if eff:
                a = QPropertyAnimation(eff, b"opacity")
                a.setDuration(420)
                a.setStartValue(0.0)
                a.setEndValue(1.0)
                a.setEasingCurve(QEasingCurve.OutCubic)
                parallel.addAnimation(a)

        # sequence: window fade -> logo fade (overlapping) -> parallel texts fade
        seq = QSequentialAnimationGroup()
        seq.addAnimation(win_anim)

        # overlapping: run logo + slightly delayed texts; to overlap, we put a parallel group containing logo and texts but with logo having a longer duration
        overlap_group = QParallelAnimationGroup()
        for a in anims:
            overlap_group.addAnimation(a)
        overlap_group.addAnimation(parallel)
        seq.addAnimation(overlap_group)

        # keep reference so GC doesn't delete animations
        self._anim_group_show = seq

        # when finished, clear showing flag
        def on_show_finished():
            self._showing = False
            self._anim_group_show = None
        seq.finished.connect(on_show_finished)

        seq.start()

    def start_close_animation(self):
        """
        Play fade-out animation for child elements and window, then accept the dialog.
        Prevents re-entry if already closing.
        """
        if self._closing:
            return
        self._closing = True

        # Stop any show animation if running
        try:
            if self._anim_group_show and self._anim_group_show.state() == self._anim_group_show.Running:
                self._anim_group_show.stop()
        except Exception:
            pass

        # Child fade-outs (texts + button + logo)
        parallel_out = QParallelAnimationGroup()
        for w in (self.cont_btn, self.rif_lbl, self.comp_lbl, self.sys_lbl, self.logo_lbl):
            eff = w.graphicsEffect()
            if eff:
                a = QPropertyAnimation(eff, b"opacity")
                a.setDuration(280)
                a.setStartValue(1.0)
                a.setEndValue(0.0)
                a.setEasingCurve(QEasingCurve.InCubic)
                parallel_out.addAnimation(a)

        # Window fade-out
        win_anim = QPropertyAnimation(self, b"windowOpacity")
        win_anim.setDuration(300)
        win_anim.setStartValue(1.0)
        win_anim.setEndValue(0.0)
        win_anim.setEasingCurve(QEasingCurve.InCubic)

        seq = QSequentialAnimationGroup()
        seq.addAnimation(parallel_out)
        seq.addAnimation(win_anim)

        # keep reference alive
        self._anim_group_close = seq

        # on finished, call the base class accept to actually close the dialog
        def on_close_finished():
            try:
                # ensure the window is fully transparent when finishing
                try:
                    self.setWindowOpacity(0.0)
                except Exception:
                    pass
                super(SplashWindow, self).accept()
            finally:
                self._anim_group_close = None
                self._closing = False

        seq.finished.connect(on_close_finished)
        seq.start()

    # Ensure that if the dialog is closed by other means we attempt to stop animations cleanly
    def closeEvent(self, ev):
        try:
            if self._anim_group_show and self._anim_group_show.state() == self._anim_group_show.Running:
                self._anim_group_show.stop()
            if self._anim_group_close and self._anim_group_close.state() == self._anim_group_close.Running:
                # let it finish
                pass
        except Exception:
            pass
        super().closeEvent(ev)

