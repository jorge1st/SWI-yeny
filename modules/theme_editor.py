from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QColorDialog, QWidget, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from modules import theme_manager

class ThemeEditor(QDialog):
    """Editor simple de temas: seleccionar paleta, ajustar colores y aplicar.
    Muestra una vista previa con algunos widgets representativos.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Editor de Temas')
        # default editor size (restore smaller default so preview box isn't huge)
        self.resize(760, 480)
        # allow maximize/minimize and normal window decorations so user can resize freely
        try:
            self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        except Exception:
            pass
        self.palettes = theme_manager.load_palettes()
        self.current_name = None
        self.current_palette = None
        self._build_ui()
        # cleanup any leftover preview styles that might have leaked into the real app
        try:
            self._cleanup_existing_preview_styles()
        except Exception:
            pass
        # ensure window is raised after creation to avoid hidden prompt issues
        try:
            from PyQt5.QtCore import QTimer
            # Safe helper to call show/raise/activateWindow inside try/except
            def _safe_show_raise():
                try:
                    self.show()
                    try:
                        self.raise_()
                    except Exception:
                        pass
                    try:
                        self.activateWindow()
                    except Exception:
                        pass
                except Exception:
                    # swallow any exception to avoid crashing the host app
                    pass
            QTimer.singleShot(60, _safe_show_raise)
        except Exception:
            pass

    def _build_ui(self):
        layout = QHBoxLayout(self)
        left = QVBoxLayout()
        self.list = QListWidget()
        for k in self.palettes.keys():
            self.list.addItem(k)
        self.list.currentTextChanged.connect(self._on_select)
        left.addWidget(QLabel('Paletas'))
        left.addWidget(self.list)
        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton('Aplicar')
        self.apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self.apply_btn)
        self.save_btn = QPushButton('Guardar como activa')
        self.save_btn.clicked.connect(self._save_active)
        btn_row.addWidget(self.save_btn)
        self.save_new_btn = QPushButton('Guardar como nueva...')
        self.save_new_btn.clicked.connect(self._save_as_new)
        # Avoid being triggered as default when dialog opens
        try:
            self.save_new_btn.setAutoDefault(False)
            self.save_new_btn.setDefault(False)
        except Exception:
            pass
        btn_row.addWidget(self.save_new_btn)
        left.addLayout(btn_row)
        layout.addLayout(left, 1)
        # ensure list gets initial focus (prevents Enter activating a button)
        try:
            self.list.setFocus()
        except Exception:
            pass

        right = QVBoxLayout()
        right.addWidget(QLabel('Vista previa'))
        # preview selector: allow choosing module previews
        from PyQt5.QtWidgets import QComboBox
        self.preview_selector = QComboBox()
        modules_list = ['login','splash','dashboard','agregar_productos','registro_general','utilidad','entrada','salidas','graficos','caducidad']
        for m in modules_list:
            self.preview_selector.addItem(m)
        self.preview_selector.currentTextChanged.connect(self._on_preview_change)
        right.addWidget(self.preview_selector)

        # preview area uses QGraphicsView so the entire module can be embedded and scaled to fit
        from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QFrame
        self.preview_widget = QFrame()
        self.preview_widget.setObjectName('preview_frame')
        # create graphics view
        self.preview_view = QGraphicsView()
        self.preview_view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # improve update mode for smoother redraws
        try:
            self.preview_view.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
            self.preview_view.setInteractive(False)
        except Exception:
            pass
        self.preview_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preview_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # improve scaling behavior and centering
        try:
            self.preview_view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
            self.preview_view.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
            self.preview_view.setAlignment(Qt.AlignCenter)
        except Exception:
            pass
        # give the view a neutral background so embedded widgets are visible
        try:
            self.preview_view.setStyleSheet('background: #f7f7f7; border: 1px solid #d0d0d0;')
        except Exception:
            pass
        self.preview_scene = QGraphicsScene(self)
        try:
            self.preview_scene.setBackgroundBrush(Qt.white)
        except Exception:
            pass
        self.preview_view.setScene(self.preview_scene)
        try:
            # default minimum preview size (kept modest so editor remains compact)
            self.preview_view.setMinimumSize(540, 420)
        except Exception:
            pass
        right.addWidget(self.preview_view, 1)
        # mapping of widget -> token used for interactive color picking
        self._click_token_map = {}
        # store original styles for preview-only outlines so they can be restored
        self._preview_original_styles = {}
        # mark preview widgets with this dynamic property so we never modify real app widgets
        self._preview_marker = '_is_preview'
        # keep track of preview root widget ids to limit scope
        self._preview_root_ids = set()
        # pending overrides collected when user applies 'Solo este' to widgets; these will be merged into palette on Apply/Save
        self._pending_overrides = []
        # install eventFilter will be done after rendering previews
        try:
            # install filter on the preview viewport so clicks on background map to BG token
            self.preview_view.viewport().installEventFilter(self)
        except Exception:
            pass

        # Customization controls
        ctrl_box = QGridLayout()
        ctrl_box.addWidget(QLabel('Color Tarjeta'), 0, 0)
        self.card_color_btn = QPushButton('Elegir')
        self.card_color_btn.clicked.connect(lambda: self._pick_color('CARD_BG'))
        ctrl_box.addWidget(self.card_color_btn, 0, 1)

        ctrl_box.addWidget(QLabel('Color Botón'), 1, 0)
        self.btn_color_btn = QPushButton('Elegir')
        self.btn_color_btn.clicked.connect(lambda: self._pick_color('BTN_BG'))
        ctrl_box.addWidget(self.btn_color_btn, 1, 1)

        ctrl_box.addWidget(QLabel('Hover Botón'), 2, 0)
        self.btn_hover_color_btn = QPushButton('Elegir')
        self.btn_hover_color_btn.clicked.connect(lambda: self._pick_color('BTN_HOVER'))
        ctrl_box.addWidget(self.btn_hover_color_btn, 2, 1)

        ctrl_box.addWidget(QLabel('Color Texto'), 3, 0)
        self.text_color_btn = QPushButton('Elegir')
        self.text_color_btn.clicked.connect(lambda: self._pick_color('TEXT'))
        ctrl_box.addWidget(self.text_color_btn, 3, 1)

        # Additional tokens for more control
        ctrl_box.addWidget(QLabel('Color Primario'), 4, 0)
        self.primary_color_btn = QPushButton('Elegir')
        self.primary_color_btn.clicked.connect(lambda: self._pick_color('PRIMARY'))
        ctrl_box.addWidget(self.primary_color_btn, 4, 1)

        ctrl_box.addWidget(QLabel('Color Acento'), 5, 0)
        self.accent_color_btn = QPushButton('Elegir')
        self.accent_color_btn.clicked.connect(lambda: self._pick_color('ACCENT'))
        ctrl_box.addWidget(self.accent_color_btn, 5, 1)

        ctrl_box.addWidget(QLabel('Borde (border)'), 6, 0)
        self.border_color_btn = QPushButton('Elegir')
        self.border_color_btn.clicked.connect(lambda: self._pick_color('BORDER'))
        ctrl_box.addWidget(self.border_color_btn, 6, 1)

        ctrl_box.addWidget(QLabel('Fondo (BG)'), 7, 0)
        self.bg_color_btn = QPushButton('Elegir')
        self.bg_color_btn.clicked.connect(lambda: self._pick_color('BG'))
        ctrl_box.addWidget(self.bg_color_btn, 7, 1)

        ctrl_box.addWidget(QLabel('Iconos'), 8, 0)
        self.icon_color_btn = QPushButton('Elegir')
        self.icon_color_btn.clicked.connect(lambda: self._pick_color('ICON_COLOR'))
        ctrl_box.addWidget(self.icon_color_btn, 8, 1)

        from PyQt5.QtWidgets import QFontComboBox, QSpinBox, QComboBox
        ctrl_box.addWidget(QLabel('Fuente'), 9, 0)
        self.font_combo = QFontComboBox()
        ctrl_box.addWidget(self.font_combo, 9, 1)

        ctrl_box.addWidget(QLabel('Tamaño (px)'), 10, 0)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 36)
        self.font_size_spin.setValue(13)
        ctrl_box.addWidget(self.font_size_spin, 10, 1)

        # Default scope for color operations (affects what "Elegir" will apply to)
        ctrl_box.addWidget(QLabel('Alcance cambios'), 11, 0)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(['Solo este','Todos los fondos','Todas las tarjetas','Todos los botones','Todos los textos'])
        ctrl_box.addWidget(self.scope_combo, 11, 1)

        apply_ctrls = QHBoxLayout()
        self.apply_custom_btn = QPushButton('Aplicar cambios')
        self.apply_custom_btn.clicked.connect(self._apply_custom)
        apply_ctrls.addWidget(self.apply_custom_btn)
        clear_btn = QPushButton('Restaurar paleta')
        clear_btn.clicked.connect(self._on_select_current)
        apply_ctrls.addWidget(clear_btn)

        left.addLayout(ctrl_box)
        left.addLayout(apply_ctrls)

        layout.addLayout(right, 2)

        # select first after the window is shown to avoid modal dialogs stealing focus
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(200, lambda: self.list.setCurrentRow(0) if self.list.count() > 0 else None)
        except Exception:
            if self.list.count() > 0:
                self.list.setCurrentRow(0)

    def _make_preview_widget(self):
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(8,8,8,8)
        g.addWidget(QLabel('Título de ejemplo'), 0, 0)
        g.addWidget(QPushButton('Botón primario'), 1, 0)
        g.addWidget(QPushButton('Botón secundario'), 1, 1)
        # small table sample
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
        t = QTableWidget(3, 3)
        t.setItem(0,0, QTableWidgetItem('A'))
        t.setItem(1,1, QTableWidgetItem('B'))
        t.setItem(2,2, QTableWidgetItem('C'))
        g.addWidget(t, 2, 0, 1, 2)
        return w

    def _on_select(self, name):
        self.current_name = name
        if not name:
            return
        self.current_palette = dict(self.palettes.get(name) or {})
        # sync UI controls with palette
        self._on_select_current()
        # _on_select will sync controls and render preview via _render_preview
        # (rendering applies QSS to embedded widget)

    def _on_select_current(self):
        # helper to set controls to current_palette values
        if not self.current_palette:
            return
        try:
            self.font_combo.setCurrentFont(self.font_combo.font())
        except Exception:
            pass
        f = self.current_palette.get('FONT_FAMILY') or self.current_palette.get('font_family')
        if f:
            try:
                from PyQt5.QtGui import QFont
                self.font_combo.setCurrentFont(QFont(f))
            except Exception:
                pass
        fs = self.current_palette.get('FONT_SIZE') or self.current_palette.get('font_size')
        if fs:
            try:
                if isinstance(fs, str) and fs.endswith('px'):
                    fsn = int(''.join(c for c in fs if c.isdigit()))
                else:
                    fsn = int(fs)
                self.font_size_spin.setValue(fsn)
            except Exception:
                pass
        # update preview variant if present
        try:
            if hasattr(self, 'preview_selector'):
                self._render_preview(self.preview_selector.currentText())
        except Exception:
            pass

    def _pick_color(self, token, prompt_scope=False, target_widget=None):
        # If prompt_scope is True, ask the user immediately whether to apply
        # the chosen color only to this module/widget or globally to that token type.
        try:
            scope = None
            if prompt_scope:
                try:
                    from PyQt5.QtWidgets import QInputDialog
                    choices = ['Solo este módulo/elemento', 'Todos los fondos del sistema', 'Todas las tarjetas', 'Todos los botones', 'Todos los textos']
                    # prefer a focused default based on token
                    default_idx = 0
                    choice, ok = QInputDialog.getItem(self, 'Alcance de color', f'Aplicar color para {token}:', choices, default_idx, False)
                    if not ok:
                        return
                    mapping = {
                        'Solo este módulo/elemento': 'solo',
                        'Todos los fondos del sistema': 'todos_fondos',
                        'Todas las tarjetas': 'todas_tarjetas',
                        'Todos los botones': 'todos_botones',
                        'Todos los textos': 'todos_textos'
                    }
                    scope = mapping.get(choice, 'solo')
                except Exception:
                    scope = None
            if scope is None:
                # fall back to global UI selection
                scope_map = {
                    'Solo este': 'solo',
                    'Todos los fondos': 'todos_fondos',
                    'Todas las tarjetas': 'todas_tarjetas',
                    'Todos los botones': 'todos_botones',
                    'Todos los textos': 'todos_textos'
                }
                scope_text = self.scope_combo.currentText() if hasattr(self, 'scope_combo') else 'Solo este'
                scope = scope_map.get(scope_text, 'solo')
            self._open_color_dialog(token, scope=scope, target_widget=target_widget)
        except Exception:
            try:
                self._open_color_dialog(token, scope='solo', target_widget=target_widget)
            except Exception:
                pass

    def _open_color_dialog(self, token, initial=None, scope=None, target_widget=None):
        """Open a color picker dialog that includes scope selection and updates preview live.
        token: palette key to update (e.g., 'BG','BTN_BG','CARD_BG','TEXT')
        initial: optional initial QColor or hex string
        scope: optional initial scope value
        """
        try:
            from PyQt5.QtGui import QColor
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QColorDialog, QPushButton
            from PyQt5.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle('Selector de color')
            dlg.setWindowModality(Qt.NonModal)
            v = QVBoxLayout(dlg)

            # Use non-native QColorDialog so we can embed controls
            color_widget = QColorDialog(dlg)
            color_widget.setOption(QColorDialog.ShowAlphaChannel, False)
            try:
                color_widget.setOption(QColorDialog.DontUseNativeDialog, True)
            except Exception:
                pass

            # set initial color
            try:
                if initial is None and self.current_palette and token in self.current_palette:
                    initial = self.current_palette.get(token)
                if isinstance(initial, str):
                    color_widget.setCurrentColor(QColor(initial))
                elif isinstance(initial, QColor):
                    color_widget.setCurrentColor(initial)
            except Exception:
                pass

            v.addWidget(color_widget)

            # scope selector row
            row = QHBoxLayout()
            row.addWidget(QLabel('Aplicar a:'))
            scope_combo = QComboBox()
            opts = ['Solo este', 'Todos los fondos', 'Todas las tarjetas', 'Todos los botones', 'Todos los textos']
            scope_combo.addItems(opts)
            scope_map_rev = {'solo': 'Solo este', 'todos_fondos': 'Todos los fondos', 'todas_tarjetas':'Todas las tarjetas', 'todos_botones':'Todos los botones', 'todos_textos':'Todos los textos'}
            if scope and scope in scope_map_rev:
                try:
                    idx = opts.index(scope_map_rev[scope])
                    scope_combo.setCurrentIndex(idx)
                except Exception:
                    pass
            row.addWidget(scope_combo)

            # ok / cancel
            btns = QHBoxLayout()
            ok_btn = QPushButton('OK')
            cancel_btn = QPushButton('Cancelar')
            btns.addStretch(); btns.addWidget(ok_btn); btns.addWidget(cancel_btn)

            v.addLayout(row)
            v.addLayout(btns)

            current_scope = scope or 'solo'
            def _scope_text_to_key(txt):
                m = {'Solo este':'solo','Todos los fondos':'todos_fondos','Todas las tarjetas':'todas_tarjetas','Todos los botones':'todos_botones','Todos los textos':'todos_textos'}
                return m.get(txt, 'solo')

            def apply_color_to_palette(token_key, hexc, scope_key, target_widget=None):
                """Aplica color a la paleta o, si target_widget y scope_key == 'solo', aplica inline style
                solamente a ese widget en la preview."""
                if scope_key in (None, 'solo') and target_widget is not None:
                    # Only allow inline preview styles on widgets that belong to the preview
                    try:
                        is_preview = False
                        try:
                            is_preview = bool(target_widget.property(self._preview_marker))
                        except Exception:
                            is_preview = False
                        if not is_preview:
                            # don't mutate real app widgets — persist into current_palette instead
                            if not self.current_palette:
                                self.current_palette = {}
                            self.current_palette[token_key] = hexc
                            return
                    except Exception:
                        # if any error, fallback to not editing real widgets
                        if not self.current_palette:
                            self.current_palette = {}
                        self.current_palette[token_key] = hexc
                        return

                    # apply inline style to the widget instead of updating palette
                    try:
                        prev = target_widget.styleSheet() or ''
                        # map token to css
                        css = ''
                        if token_key in ('BTN_BG','CARD_BG','BG','SURFACE'):
                            css = f'background: {hexc};'
                        elif token_key in ('BTN_TEXT','TEXT','TEXT_COLOR'):
                            css = f'color: {hexc};'
                        elif token_key == 'BORDER':
                            css = f'border: 1px solid {hexc};'
                        elif token_key == 'ICON_COLOR':
                            css = f'color: {hexc};'
                        else:
                            css = f'background: {hexc};'
                        # append preview marker
                        try:
                            marker = '\n/* inline-preview-style */\n'
                            target_widget.setStyleSheet(prev + marker + css)
                        except Exception:
                            try:
                                target_widget.setStyleSheet(css)
                            except Exception:
                                pass
                        # store original if not saved
                        try:
                            wid_id = id(target_widget)
                            if wid_id not in self._preview_original_styles:
                                self._preview_original_styles[wid_id] = prev
                        except Exception:
                            pass
                        # record a pending override so Apply/Save will persist it into the palette
                        try:
                            if not hasattr(self, '_pending_overrides'):
                                self._pending_overrides = []
                            self._pending_overrides.append((token_key, hexc))
                        except Exception:
                            pass
                        return
                    except Exception:
                        pass
                # fallback: apply to palette
                if not self.current_palette:
                    self.current_palette = {}
                if scope_key in (None, 'solo'):
                    self.current_palette[token_key] = hexc
                elif scope_key == 'todos_fondos':
                    for t in ('BG','BACKGROUND','SURFACE','SIDEBAR','CARD_BG'):
                        self.current_palette[t] = hexc
                elif scope_key == 'todas_tarjetas' or scope_key == 'todas_tarjetas':
                    for t in ('CARD_BG', 'SURFACE'):
                        self.current_palette[t] = hexc
                elif scope_key == 'todos_botones':
                    for t in ('BTN_BG','BTN_HOVER','BTN_TEXT'):
                        self.current_palette[t] = hexc
                elif scope_key == 'todos_textos':
                    for t in ('TEXT','TEXT_COLOR','TEXT_PRIMARY','TEXT_SECONDARY'):
                        self.current_palette[t] = hexc
                else:
                    self.current_palette[token_key] = hexc

            def on_change(col):
                try:
                    if not col or not col.isValid():
                        return
                    hexc = col.name()
                    sk = current_scope
                    # if scope is solo and dialog was opened from a widget, prefer inline
                    apply_color_to_palette(token, hexc, sk, target_widget=locals().get('target_widget', None) or target_widget if 'target_widget' in locals() else target_widget)
                    base = theme_manager.get_palette(self.current_name) or {}
                    merged = dict(base)
                    merged.update(self.current_palette or {})
                    try:
                        qss = theme_manager.build_qss(merged)
                    except Exception:
                        try:
                            qss = theme_manager.build_qss(self.current_name)
                        except Exception:
                            qss = ''
                    try:
                        # apply to embedded previews (preview-only; do NOT save/apply globally here)
                        self._apply_qss_to_scene(qss)
                        bg = merged.get('BG') or merged.get('BACKGROUND') or merged.get('SURFACE')
                        if bg:
                            try:
                                self.preview_view.setStyleSheet(f'background: {bg}; border: 1px solid {merged.get("BORDER", "#d0d0d0")};')
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

            # connect signals
            try:
                color_widget.currentColorChanged.connect(on_change)
            except Exception:
                try:
                    color_widget.currentColorChanged.connect(on_change)
                except Exception:
                    pass

            def _on_scope_changed(txt):
                nonlocal current_scope
                current_scope = _scope_text_to_key(txt)
            scope_combo.currentTextChanged.connect(_on_scope_changed)

            ok_btn.clicked.connect(lambda: (on_change(color_widget.currentColor()), dlg.accept()))
            cancel_btn.clicked.connect(lambda: dlg.reject())

            def _on_done(res):
                try:
                    try:
                        c = color_widget.currentColor()
                        if c and c.isValid():
                            on_change(c)
                    except Exception:
                        pass
                    try:
                        self._reinstall_handlers_for_scene()
                        self._on_select_current()
                    except Exception:
                        pass
                    try:
                        self._clear_highlight()
                    except Exception:
                        pass
                finally:
                    try:
                        dlg.deleteLater()
                    except Exception:
                        pass

            dlg.finished.connect(_on_done)

            try:
                dlg.show()
                try:
                    dlg.raise_(); dlg.activateWindow()
                except Exception:
                    pass
            except Exception:
                try:
                    dlg.exec_()
                except Exception:
                    pass
        except Exception:
            pass

    def _highlight_widget(self, w):
        """Visually highlight a widget in the preview to indicate selection for color editing."""
        try:
            # clear previous highlight
            try:
                if hasattr(self, '_highlighted') and self._highlighted:
                    self._clear_highlight()
            except Exception:
                pass
            prev = ''
            try:
                prev = w.styleSheet() or ''
            except Exception:
                prev = ''
            try:
                # store and apply a temporary outline
                self._highlighted = (w, prev)
                w.setStyleSheet(prev + "\n/* preview highlight */\noutline: 3px solid #FFA500; outline-offset: -3px;")
            except Exception:
                pass
        except Exception:
            pass

    def _clear_highlight(self):
        """Remove any preview highlight applied earlier."""
        try:
            if hasattr(self, '_highlighted') and self._highlighted:
                try:
                    w, prev = self._highlighted
                    w.setStyleSheet(prev)
                except Exception:
                    pass
                self._highlighted = None
        except Exception:
            pass

    # ---------------- Interactive preview click handling ----------------
    def _install_click_handlers(self, root_widget):
        """Recorre hijos y instala eventFilter para widgets mapeables a tokens.
        También ajusta el cursor y aplica un delineado sutil para que el usuario vea
        claramente los elementos seleccionables en la vista previa. Se guardan los
        estilos originales para restaurarlos cuando la preview cambie.
        """
        try:
            self._click_token_map = {}
            def walk(w):
                try:
                    tokens = self._tokens_for_widget(w)
                    if tokens:
                        try:
                            w.installEventFilter(self)
                        except Exception:
                            pass
                        try:
                            from PyQt5.QtCore import Qt as _Qt
                            w.setCursor(_Qt.PointingHandCursor)
                        except Exception:
                            pass
                        # apply subtle preview delineation and save original style
                        try:
                            wid_id = id(w)
                            prev = w.styleSheet() or ''
                            if wid_id not in self._preview_original_styles:
                                self._preview_original_styles[wid_id] = prev
                            # mark widget as preview-only so we don't touch app widgets
                            try:
                                w.setProperty(self._preview_marker, True)
                            except Exception:
                                pass
                            # Only append preview outline if not already present
                            if '/* preview-delineation */' not in prev:
                                added = prev + "\n/* preview-delineation */\noutline: 1px dashed rgba(0,0,0,0.12); outline-offset: -1px;"
                                try:
                                    w.setStyleSheet(added)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        self._click_token_map[wid_id] = (w, tokens)
                except Exception:
                    pass
                try:
                    for c in w.findChildren(QWidget):
                        walk(c)
                except Exception:
                    pass
            walk(root_widget)
        except Exception:
            pass

    def _remove_preview_outlines(self):
        """Restaura los estilos originales de los widgets a los que se les aplicó
        el delineado de preview. Se limpia el almacen.
        """
        try:
            for wid_id, prev in list(self._preview_original_styles.items()):
                try:
                    # buscar widget por id no es trivial; iterar click_token_map para encontrar referencia
                    ent = self._click_token_map.get(wid_id)
                    if ent:
                        w, _ = ent
                        try:
                            # only restore if this widget was marked as preview to avoid touching app widgets
                            is_preview = False
                            try:
                                is_preview = bool(w.property(self._preview_marker))
                            except Exception:
                                is_preview = False
                            if is_preview:
                                try:
                                    w.setStyleSheet(prev or "")
                                except Exception:
                                    pass
                                try:
                                    w.setProperty(self._preview_marker, False)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
            self._preview_original_styles.clear()
            # also clear click token map for preview widgets
            try:
                for k in list(self._click_token_map.keys()):
                    ent = self._click_token_map.get(k)
                    if ent:
                        w, _ = ent
                        try:
                            if not bool(w.property(self._preview_marker)):
                                # if not preview, keep mapping; otherwise remove
                                continue
                        except Exception:
                            pass
                        try:
                            del self._click_token_map[k]
                        except Exception:
                            pass
            except Exception:
                pass
            # reset preview root tracking
            try:
                self._preview_root_ids.clear()
            except Exception:
                pass
        except Exception:
            pass

    def _token_for_widget(self, w):
        """Backward-compatible single-token helper (keeps existing behavior).
        Prefer using _tokens_for_widget for better granularity.
        """
        tokens = self._tokens_for_widget(w)
        return tokens[0] if tokens else None

    def _tokens_for_widget(self, w):
        """Devuelve una lista de tokens aplicables al widget para edición granular.
        Ej: ['BTN_BG','BTN_TEXT','BORDER']
        """
        try:
            res = []
            on = ''
            try:
                on = w.objectName()
            except Exception:
                try:
                    on = getattr(w, 'objectName', '')
                except Exception:
                    on = ''
            on_l = on.lower() if isinstance(on, str) else ''
            # objectName hints
            if on_l and 'sidebar' in on_l:
                return ['SIDEBAR']
            # property-based roles
            try:
                role = w.property('role')
                if role:
                    r = str(role).lower()
                    if r == 'sidebar':
                        return ['SIDEBAR']
                    if r == 'menu_button':
                        return ['BTN_BG','BTN_TEXT']
                    if r == 'dept_button':
                        return ['CARD_BG']
            except Exception:
                pass
            # class-name heuristics
            try:
                cls_name = w.__class__.__name__.lower()
                if 'card' in cls_name or 'tarjeta' in cls_name:
                    return ['CARD_BG','BORDER','TEXT']
                if 'icon' in cls_name or 'icono' in cls_name:
                    return ['ICON_COLOR']
                if 'cart' in cls_name or 'carrito' in cls_name:
                    return ['CARD_BG','TEXT']
            except Exception:
                pass
            # fallback by class type
            from PyQt5.QtWidgets import QPushButton, QFrame, QLabel, QToolButton, QLineEdit, QTableWidget, QAbstractButton
            try:
                if isinstance(w, (QPushButton, QToolButton, QAbstractButton)):
                    # allow editing background, text, border, icon
                    return ['BTN_BG','BTN_TEXT','BORDER','ICON_COLOR']
                if isinstance(w, QFrame) or isinstance(w, QTableWidget):
                    return ['CARD_BG','BORDER','TEXT']
                if isinstance(w, QLineEdit):
                    return ['SURFACE','TEXT','BORDER']
                if isinstance(w, QLabel):
                    return ['TEXT','BORDER']
            except Exception:
                pass
            # default: no tokens
            return res
        except Exception:
            return []

    def eventFilter(self, obj, event):
        # intercept clicks on preview-mapped widgets and the preview viewport background
        try:
            from PyQt5.QtCore import QEvent
            if event.type() == QEvent.MouseButtonPress:
                # special-case: clicking on preview background should allow editing BG token
                try:
                    if hasattr(self, 'preview_view') and hasattr(self.preview_view, 'viewport') and obj is self.preview_view.viewport():
                        # Ask whether change applies to this module only or to all module backgrounds
                        try:
                            from PyQt5.QtWidgets import QInputDialog
                            choices = ['Solo este módulo', 'Todos los fondos del sistema']
                            choice, ok = QInputDialog.getItem(self, 'Alcance color fondo', 'Aplicar cambio a:', choices, 1, False)
                            if not ok:
                                return True
                            if choice == 'Todos los fondos del sistema':
                                self._open_color_dialog('BG', scope='todos_fondos')
                            else:
                                # apply only to this preview (module)
                                self._open_color_dialog('BG', scope='solo')
                        except Exception:
                            # fallback: use current scope UI
                            scope_map = {
                                'Solo este': 'solo',
                                'Todos los fondos': 'todos_fondos',
                                'Todas las tarjetas': 'todas_tarjetas',
                                'Todos los botones': 'todos_botones',
                                'Todos los textos': 'todos_textos'
                            }
                            scope_text = self.scope_combo.currentText() if hasattr(self, 'scope_combo') else 'Solo este'
                            scope = scope_map.get(scope_text, 'solo')
                            self._open_color_dialog('BG', scope=scope)
                        return True
                except Exception:
                    pass

                ent = self._click_token_map.get(id(obj))
                if ent:
                    w, tokens = ent
                    try:
                        # highlight selected widget so user sees what will be edited
                        try:
                            self._highlight_widget(w)
                        except Exception:
                            pass
                        # determine token: show menu when multiple choices available
                        try:
                            token = None
                            if tokens and len(tokens) > 1:
                                from PyQt5.QtWidgets import QMenu
                                menu = QMenu(self)
                                mapping = {
                                    'BTN_BG': 'Fondo', 'BTN_TEXT': 'Texto', 'BORDER': 'Borde', 'ICON_COLOR': 'Icono',
                                    'CARD_BG': 'Fondo tarjeta', 'TEXT': 'Texto', 'SURFACE': 'Fondo', 'SIDEBAR': 'Sidebar'
                                }
                                for t in tokens:
                                    label = mapping.get(t, t)
                                    act = menu.addAction(label)
                                    act.setData(t)
                                try:
                                    pos = obj.mapToGlobal(event.pos())
                                except Exception:
                                    pos = None
                                chosen = menu.exec_(pos) if pos is not None else menu.exec_()
                                if chosen:
                                    token = chosen.data()
                            else:
                                token = tokens[0] if tokens else None

                            if token:
                                self._pick_color(token, prompt_scope=True, target_widget=w)
                        except Exception:
                            # fallback: pick first token
                            try:
                                token = tokens[0] if tokens else None
                                if token:
                                    self._pick_color(token, prompt_scope=True, target_widget=w)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _apply_qss_to_scene(self, qss):
        """Apply qss string to all QWidget instances embedded in the preview scene."""
        try:
            for item in self.preview_scene.items():
                try:
                    # QGraphicsProxyWidget provides widget()
                    w = None
                    if hasattr(item, 'widget'):
                        try:
                            w = item.widget()
                        except Exception:
                            w = None
                    if w:
                        try:
                            w.setStyleSheet(qss)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def _reinstall_handlers_for_scene(self):
        """Re-run installation of click handlers on all embedded widgets in the scene."""
        try:
            for item in self.preview_scene.items():
                try:
                    if hasattr(item, 'widget'):
                        try:
                            w = item.widget()
                            if w:
                                self._install_click_handlers(w)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_custom(self):
        # apply current selection/palette (same as Apply but keeps temp preview name)
        if not self.current_name:
            return
        try:
            base = theme_manager.get_palette(self.current_name) or {}
            merged = dict(base)
            merged.update(self.current_palette or {})
            theme_manager.save_palette('__temp_preview__', merged)
            theme_manager.apply_theme(__import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance(), '__temp_preview__')
        except Exception:
            try:
                qss = theme_manager.build_qss(merged)
                __import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance().setStyleSheet(qss)
            except Exception:
                pass

        # collect font and size
        if not self.current_palette:
            self.current_palette = {}
        try:
            fam = self.font_combo.currentFont().family()
            self.current_palette['FONT_FAMILY'] = fam
        except Exception:
            pass
        try:
            fs = self.font_size_spin.value()
            self.current_palette['FONT_SIZE'] = f"{fs}px"
        except Exception:
            pass
        # ensure TEXT key present
        if 'TEXT' not in self.current_palette and 'TEXT_COLOR' in self.current_palette:
            self.current_palette['TEXT'] = self.current_palette['TEXT_COLOR']
        # merge with base palette
        base = theme_manager.get_palette(self.current_name) or {}
        merged = dict(base)
        merged.update(self.current_palette)
        # incorporate any pending inline overrides into merged palette so they persist
        try:
            if hasattr(self, '_pending_overrides') and self._pending_overrides:
                for tk, val in self._pending_overrides:
                    try:
                        merged[tk] = val
                    except Exception:
                        pass
                # clear pending overrides after merging
                try:
                    self._pending_overrides.clear()
                except Exception:
                    pass
        except Exception:
            pass
        # Apply to whole app
        try:
            theme_manager.save_palette('__temp_preview__', merged)
            theme_manager.apply_theme(__import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance(), '__temp_preview__')
        except Exception:
            # fallback: apply via building qss and setting it
            try:
                qss = theme_manager.build_qss(merged)
                __import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance().setStyleSheet(qss)
            except Exception:
                pass

    def _save_as_new(self):
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, 'Nombre de paleta', 'Nombre para la nueva paleta:')
        if not ok or not name:
            return
        base = theme_manager.get_palette(self.current_name) or {}
        merged = dict(base)
        merged.update(self.current_palette or {})
        ok2 = theme_manager.save_palette(name, merged)
        if ok2:
            # refresh list
            self.list.clear()
            self.palettes = theme_manager.load_palettes()
            for k in self.palettes.keys():
                self.list.addItem(k)
            # select new
            items = self.list.findItems(name, Qt.MatchExactly)
            if items:
                self.list.setCurrentItem(items[0])

    def _on_preview_change(self, name):
        # render preview variant
        try:
            self._render_preview(name)
        except Exception:
            pass

    def _clear_layout(self, layout):
        try:
            while layout.count():
                item = layout.takeAt(0)
                if item is None:
                    continue
                w = item.widget()
                if w:
                    try:
                        w.setParent(None)
                    except Exception:
                        pass
                else:
                    sub = item.layout()
                    if sub:
                        self._clear_layout(sub)
        except Exception:
            pass

    def _cleanup_existing_preview_styles(self):
        """Remove any lingering preview markers/styles from real application widgets.
        Defensive: strip preview comments, inline-preview blocks and outline rules
        that may have been injected into widgets by older editor runs. Also
        remove event filters installed by the editor and clear preview properties.
        """
        try:
            import re
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import Qt
            app = QApplication.instance()
            if not app:
                return
            for w in app.allWidgets():
                try:
                    # remove any preview comment markers and content after them (safe split)
                    s = w.styleSheet() or ''
                    orig = s
                    try:
                        if '/* preview-delineation */' in s:
                            s = s.split('/* preview-delineation */')[0]
                        if '/* preview highlight */' in s:
                            s = s.split('/* preview highlight */')[0]
                        if '/* inline-preview-style */' in s:
                            s = s.split('/* inline-preview-style */')[0]
                    except Exception:
                        pass
                    # remove any outline rules left anywhere (outline, outline-offset)
                    try:
                        s = re.sub(r'outline\s*:[^;]+;?', '', s, flags=re.IGNORECASE)
                        s = re.sub(r'outline-offset\s*:[^;]+;?', '', s, flags=re.IGNORECASE)
                    except Exception:
                        pass

                    # trim trailing whitespace
                    s = s.strip()
                    if s != orig:
                        try:
                            w.setStyleSheet(s)
                        except Exception:
                            pass

                    # remove event filter added by previous editor runs
                    try:
                        w.removeEventFilter(self)
                    except Exception:
                        pass

                    # clear preview marker property if present
                    try:
                        if w.property(getattr(self, '_preview_marker', '_is_preview')):
                            try:
                                w.setProperty(getattr(self, '_preview_marker', '_is_preview'), False)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # reset cursor if it was set to pointing hand by the editor
                    try:
                        from PyQt5.QtGui import QCursor
                        if w.cursor().shape() != Qt.ArrowCursor:
                            try:
                                w.setCursor(QCursor(Qt.ArrowCursor))
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def _render_preview(self, name):
        # Render the selected module INTO the QGraphicsScene and scale it to fit the preview view.
        from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QWidget

        # clear previous scene
        try:
            # restore any preview-only outlines/styles before clearing
            try:
                self._remove_preview_outlines()
            except Exception:
                pass
            self.preview_scene.clear()
        except Exception:
            pass

        # Try to instantiate the real module widget for a faithful visual preview. If that fails, fall back to lightweight mock.
        def try_real(module_name, class_name):
            try:
                import importlib
                mod = importlib.import_module(f"modules.{module_name}")
                cls = getattr(mod, class_name, None)
                if cls is None:
                    return None
                # sandbox: monkeypatch risky GUI calls to avoid side-effects in preview (dialogs, exec_(), timers, quit/exit)
                try:
                    from PyQt5 import QtWidgets, QtCore
                    import sys as _sys
                    _orig_QMessageBox_exec = getattr(QtWidgets.QMessageBox, 'exec_', None)
                    _orig_QDialog_exec = getattr(QtWidgets.QDialog, 'exec_', None)
                    _orig_QDialog_show = getattr(QtWidgets.QDialog, 'show', None)
                    _orig_QTimer_single = getattr(QtCore.QTimer, 'singleShot', None)
                    _orig_QApp_quit = getattr(QtWidgets.QApplication, 'quit', None) if hasattr(QtWidgets, 'QApplication') else None
                    _orig_QCore_quit = getattr(QtCore.QCoreApplication, 'quit', None) if hasattr(QtCore, 'QCoreApplication') else None
                    _orig_sys_exit = getattr(_sys, 'exit', None)

                    def _noop_exec(self=None):
                        return 0
                    def _noop_show(self=None):
                        return None
                    def _safe_singleShot(msec, func):
                        # no-op during preview instantiation to avoid running animations/dialogs
                        return None
                    def _noop_quit(*a, **k):
                        return None

                    try:
                        if _orig_QMessageBox_exec:
                            QtWidgets.QMessageBox.exec_ = _noop_exec
                        if _orig_QDialog_exec:
                            QtWidgets.QDialog.exec_ = _noop_exec
                        if _orig_QDialog_show:
                            QtWidgets.QDialog.show = _noop_show
                        if _orig_QTimer_single:
                            QtCore.QTimer.singleShot = staticmethod(_safe_singleShot)
                        if _orig_QApp_quit:
                            QtWidgets.QApplication.quit = staticmethod(_noop_quit)
                        if _orig_QCore_quit:
                            QtCore.QCoreApplication.quit = staticmethod(_noop_quit)
                        if _orig_sys_exit:
                            _sys.exit = lambda *a, **k: None
                    except Exception:
                        pass
                except Exception:
                    _orig_QMessageBox_exec = _orig_QDialog_exec = _orig_QDialog_show = _orig_QTimer_single = None
                    _orig_QApp_quit = _orig_QCore_quit = _orig_sys_exit = None

                # construct without parent to avoid side-effects (done while monkeypatched)
                try:
                    try:
                        inst = cls()
                    except TypeError:
                        try:
                            inst = cls(parent=None)
                        except Exception:
                            try:
                                inst = cls(None)
                            except Exception:
                                inst = None
                except Exception:
                    inst = None

                if inst is None:
                    # restore immediately if nothing created
                    try:
                        from PyQt5 import QtWidgets, QtCore
                        def _restore_immediate():
                            try:
                                if _orig_QMessageBox_exec:
                                    QtWidgets.QMessageBox.exec_ = _orig_QMessageBox_exec
                            except Exception:
                                pass
                            try:
                                if _orig_QDialog_exec:
                                    QtWidgets.QDialog.exec_ = _orig_QDialog_exec
                            except Exception:
                                pass
                            try:
                                if _orig_QDialog_show:
                                    QtWidgets.QDialog.show = _orig_QDialog_show
                            except Exception:
                                pass
                            try:
                                if _orig_QTimer_single:
                                    QtCore.QTimer.singleShot = _orig_QTimer_single
                            except Exception:
                                pass
                            try:
                                if _orig_QApp_quit:
                                    QtWidgets.QApplication.quit = _orig_QApp_quit
                            except Exception:
                                pass
                            try:
                                if _orig_QCore_quit:
                                    QtCore.QCoreApplication.quit = _orig_QCore_quit
                            except Exception:
                                pass
                            try:
                                if _orig_sys_exit:
                                    _sys.exit = _orig_sys_exit
                            except Exception:
                                pass
                        try:
                            QtCore.QTimer.singleShot(10, _restore_immediate)
                        except Exception:
                            _restore_immediate()
                    except Exception:
                        pass
                    return None

                # convert to embedded widget
                try:
                    # Force the instance to behave as a child widget (not a top-level fullscreen/modal window)
                    inst.setWindowFlags(Qt.Widget)
                except Exception:
                    pass
                try:
                    # Clear any fullscreen/window state that some modules (splash) set during init
                    inst.setWindowState(Qt.WindowNoState)
                except Exception:
                    pass
                try:
                    # Ensure dialogs are non-modal for embedding
                    if hasattr(inst, 'setModal'):
                        try:
                            inst.setModal(False)
                        except Exception:
                            pass
                    try:
                        from PyQt5.QtCore import Qt as _Qt
                        if hasattr(inst, 'setWindowModality'):
                            try:
                                inst.setWindowModality(_Qt.NonModal)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

                # clear inline styles recursively for preview, but preserve inline styles for
                # modules that build styling programmatically (carritos, producto-cards, etc.)
                def clear_styles(w):
                    try:
                        skip_modules = ('ventas_carrito', 'ventas_carrito_cards', 'compras_carrito', 'productos', 'inventario', 'caducidad', 'registro_general', 'entradas', 'salidas')
                        if module_name and str(module_name).lower() in skip_modules:
                            # preserve inline styles for these modules so their programmatic appearance
                            # remains intact in the preview
                            return
                        w.setStyleSheet("")
                    except Exception:
                        pass
                    try:
                        for c in w.findChildren(QWidget):
                            clear_styles(c)
                    except Exception:
                        pass
                try:
                    clear_styles(inst)
                except Exception:
                    pass

                # restore monkeypatches after a short idle via QTimer.singleShot
                try:
                    from PyQt5 import QtWidgets, QtCore
                    def _restore():
                        try:
                            if _orig_QMessageBox_exec:
                                QtWidgets.QMessageBox.exec_ = _orig_QMessageBox_exec
                        except Exception:
                            pass
                        try:
                            if _orig_QDialog_exec:
                                QtWidgets.QDialog.exec_ = _orig_QDialog_exec
                        except Exception:
                            pass
                        try:
                            if _orig_QDialog_show:
                                QtWidgets.QDialog.show = _orig_QDialog_show
                        except Exception:
                            pass
                        try:
                            if _orig_QTimer_single:
                                QtCore.QTimer.singleShot = _orig_QTimer_single
                        except Exception:
                            pass
                        try:
                            if _orig_QApp_quit:
                                QtWidgets.QApplication.quit = _orig_QApp_quit
                        except Exception:
                            pass
                        try:
                            if _orig_QCore_quit:
                                QtCore.QCoreApplication.quit = _orig_QCore_quit
                        except Exception:
                            pass
                        try:
                            if _orig_sys_exit:
                                _sys.exit = _orig_sys_exit
                        except Exception:
                            pass
                    try:
                        QtCore.QTimer.singleShot(100, _restore)
                    except Exception:
                        _restore()
                except Exception:
                    pass
                return inst
            except Exception:
                return None

        widget = None
        # For safety: never instantiate real application modules in the preview to avoid
        # modifying or interacting with live app widgets. Use mocks only.
        allow_real_modules = False
        if allow_real_modules:
            if name == 'login':
                widget = try_real('login', 'LoginWindow')
            elif name == 'splash':
                widget = try_real('splash', 'SplashWindow')
            elif name == 'dashboard':
                widget = try_real('dashboard', 'DashboardWindow')
            elif name == 'agregar_productos':
                widget = try_real('productos', 'ProductosWindow')
            elif name == 'registro_general':
                widget = try_real('registro_general', 'RegistroGeneralWindow')
            elif name == 'utilidad':
                widget = try_real('inventario', 'InventoryViewWidget')
            elif name == 'entrada':
                widget = try_real('entradas', 'EntradasWindow')
            elif name == 'salidas':
                # try SalidasWindow then VentasIntegradoWidget
                widget = try_real('salidas', 'SalidasWindow') or try_real('salidas', 'VentasIntegradoWidget')
            elif name == 'graficos':
                widget = try_real('graficos', 'GraficosWindow')
            elif name == 'caducidad':
                widget = try_real('caducidad', 'CaducidadWindow')

        if widget is not None:
            try:
                # ensure the widget has a reasonable size
                try:
                    widget.adjustSize()
                except Exception:
                    pass

                # ensure widget is treated as a child widget (not a standalone window)
                try:
                    widget.setWindowFlags(Qt.Widget)
                except Exception:
                    pass

                # For entrada/salidas, attempt to compose the module with a cart widget side-by-side
                composite_widget = None
                try:
                    if name in ('entrada', 'salidas'):
                        from PyQt5.QtWidgets import QWidget as _QWidget, QHBoxLayout as _QHBoxLayout
                        container = _QWidget()
                        hl = _QHBoxLayout(container)
                        hl.setContentsMargins(0,0,0,0)
                        hl.setSpacing(8)
                        hl.addWidget(widget)
                        try:
                            # Build a lightweight mock cart instead of instantiating full cart widgets
                            from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QLabel, QFrame
                            try:
                                # try to use ProductoCard for a realistic appearance
                                from modules.ventas_carrito_cards import ProductoCard
                            except Exception:
                                ProductoCard = None

                            cart_frame = QFrame()
                            cart_layout = QVBoxLayout(cart_frame)
                            cart_layout.setContentsMargins(8,8,8,8)
                            cart_layout.setSpacing(8)
                            # create a few sample product cards
                            sample_items = [
                                {'nombre':'Producto A','codigo':'A001','precio_unitario_bs':120.0,'stock_original':10,'cantidad':1,'unidad':'und'},
                                {'nombre':'Producto B','codigo':'B002','precio_unitario_bs':45.5,'stock_original':5,'cantidad':2,'unidad':'und'},
                                {'nombre':'Producto C','codigo':'C003','precio_unitario_bs':9.75,'stock_original':100,'cantidad':1,'unidad':'und'}
                            ]
                            for idx,it in enumerate(sample_items):
                                try:
                                    if ProductoCard:
                                        pc = ProductoCard(idx, it)
                                        cart_layout.addWidget(pc)
                                    else:
                                        lbl = QLabel(f"{it['nombre']} • {it['codigo']} — {it['precio_unitario_bs']:.2f} Bs")
                                        cart_layout.addWidget(lbl)
                                except Exception:
                                    pass
                            cart_layout.addStretch()
                            scroll = QScrollArea()
                            scroll.setWidgetResizable(True)
                            scroll.setWidget(cart_frame)
                            scroll.setFixedWidth(300)
                            hl.addWidget(scroll)
                        except Exception:
                            # fallback: ignore cart composition
                            pass
                        composite_widget = container
                except Exception:
                    composite_widget = None

                target = composite_widget if composite_widget is not None else widget

                # add widget (or composite) to graphics scene
                proxy = self.preview_scene.addWidget(target)
                try:
                    # mark the preview root so we can avoid touching the real app widgets
                    try:
                        self._preview_root_ids.add(id(target))
                    except Exception:
                        pass
                    # mark this widget and its children as preview-only
                    def _mark_preview(w):
                        try:
                            w.setProperty(self._preview_marker, True)
                        except Exception:
                            pass
                        try:
                            for c in w.findChildren(QWidget):
                                _mark_preview(c)
                        except Exception:
                            pass
                    try:
                        _mark_preview(target)
                    except Exception:
                        pass
                    # ensure widget paints a background so it isn't invisible under the view's background
                    target.setAttribute(Qt.WA_StyledBackground, True)
                    try:
                        target.setAutoFillBackground(True)
                    except Exception:
                        pass
                except Exception:
                    pass

                # For some modules that create very large layouts (registro_general, caducidad),
                # clamp their initial widget size to viewport to avoid oversized previews.
                try:
                    if name in ('registro_general', 'caducidad'):
                        try:
                            cap_w = int(self.preview_view.viewport().width() * 0.95)
                            cap_h = int(self.preview_view.viewport().height() * 0.95)
                            cur_w = target.width() or target.sizeHint().width() or 800
                            cur_h = target.height() or target.sizeHint().height() or 600
                            if cur_w > cap_w or cur_h > cap_h:
                                try:
                                    target.resize(min(cur_w, cap_w), min(cur_h, cap_h))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
 
                # compute scaling to fit view
                try:
                    vw = max(1, self.preview_view.viewport().width())
                    vh = max(1, self.preview_view.viewport().height())
                except Exception:
                    vw, vh = 1000, 600
                w = target.width() or target.sizeHint().width() or 800
                h = target.height() or target.sizeHint().height() or 600

                # Use fitInView to scale the embedded widget to the preview area, with fallback.
                try:
                    try:
                        proxy.setTransformOriginPoint(proxy.boundingRect().center())
                    except Exception:
                        try:
                            proxy.setTransformOriginPoint(0, 0)
                        except Exception:
                            pass
                    br = proxy.boundingRect()
                    self.preview_scene.setSceneRect(br)
                    try:
                        # prefer our fit helper which recenters and handles resizeEvent
                        self._fit_preview()
                    except Exception:
                        try:
                            self.preview_view.resetTransform()
                        except Exception:
                            pass
                        try:
                            self.preview_view.fitInView(br, Qt.KeepAspectRatio)
                        except Exception:
                            pass

                    # Compute scale to fit into viewport. Allow upscaling so small modules can fill the preview.
                    # Limit extreme upscales to a reasonable maximum (2.0) to avoid huge blurring.
                    try:
                        try:
                            bw = max(1.0, float(br.width()))
                            bh = max(1.0, float(br.height()))
                            vw = max(1.0, float(self.preview_view.viewport().width()))
                            vh = max(1.0, float(self.preview_view.viewport().height()))
                            scale_w = (vw * 0.95) / bw
                            scale_h = (vh * 0.95) / bh
                            # Previously allowed upscaling; to avoid preview distortion in fullscreen
                            # clamp scale to at most 1.0 (no upscaling) so embedded modules never become oversized.
                            scale = min(scale_w, scale_h)
                            scale = max(0.1, min(scale, 1.0))
                        except Exception:
                            scale = 1.0
                        try:
                            proxy.setTransformOriginPoint(br.center())
                        except Exception:
                            try:
                                proxy.setTransformOriginPoint(0,0)
                            except Exception:
                                pass
                        from PyQt5.QtGui import QTransform
                        try:
                            proxy.setTransform(QTransform().scale(scale, scale))
                        except Exception:
                            try:
                                proxy.setScale(scale)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

                # apply qss to embedded widget(s) so preview reflects palette changes
                try:
                    base = theme_manager.get_palette(self.current_name) or {}
                    merged = dict(base)
                    merged.update(self.current_palette or {})
                    qss = theme_manager.build_qss(merged)
                    # Inject light preview-only overrides to improve spacing for cramped modules (only downscaling/visual tweaks)
                    try:
                        preview_overrides = ''
                        if name in ('dashboard', 'registro_general', 'caducidad', 'inventario'):
                            preview_overrides = '''
/* Preview-only overrides: increase container padding, slightly reduce font size for spacing */
* { padding: 6px; margin: 4px; }
QLabel, QToolButton, QPushButton { font-size: 13px; }
QPushButton { padding: 6px 8px; }
QTableWidget::item { padding: 6px; }
QHeaderView::section { padding: 4px; }
'''
                        try:
                            target.setStyleSheet(qss + "\n" + preview_overrides)
                        except Exception:
                            target.setStyleSheet(qss)
                    except Exception:
                        try:
                            target.setStyleSheet(qss)
                        except Exception:
                            pass
                except Exception:
                    pass

                # install handlers for interactive clicking
                try:
                    self._install_click_handlers(target)
                except Exception:
                    pass

                # Preview-only adjustments: improve table column sizing (caducidad, registros) so content isn't cramped
                try:
                    from PyQt5.QtWidgets import QTableWidget, QHeaderView
                    tw = target.findChild(QTableWidget)
                    if tw is not None:
                        try:
                            tw.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
        else:
            # fallback lightweight mock (placed into scene)
            try:
                mock = QWidget()
                from PyQt5.QtWidgets import QVBoxLayout
                ml = QVBoxLayout(mock)
                if name == 'login':
                    l = QLabel('Iniciar sesión')
                    user = QLineEdit(); user.setPlaceholderText('Usuario')
                    pw = QLineEdit(); pw.setPlaceholderText('Contraseña')
                    pw.setEchoMode(QLineEdit.Password)
                    btn = QPushButton('Ingresar')
                    ml.addWidget(l); ml.addWidget(user); ml.addWidget(pw); ml.addWidget(btn)
                elif name == 'splash':
                    l = QLabel('Bienvenido al Sistema')
                    l.setStyleSheet('font-size:24px; font-weight:800;')
                    ml.addStretch(); ml.addWidget(l, alignment=Qt.AlignCenter); ml.addStretch()
                elif name == 'dashboard':
                    sidebar = QWidget(); sb_l = QVBoxLayout(sidebar); sb_l.addWidget(QLabel('MENÚ')); sb_l.addWidget(QPushButton('Entradas'))
                    content = QWidget(); c_l = QVBoxLayout(content); c_l.addWidget(QLabel('Panel Principal')); c_l.addWidget(QPushButton('Actualizar'))
                    from PyQt5.QtWidgets import QHBoxLayout
                    main_h = QWidget(); mh_l = QHBoxLayout(main_h); mh_l.addWidget(sidebar); mh_l.addWidget(content)
                    ml.addWidget(main_h)
                elif name == 'agregar_productos':
                    ml.addWidget(QLabel('Ingresar Producto'))
                    ml.addWidget(QLineEdit()); ml.addWidget(QLineEdit()); ml.addWidget(QPushButton('Guardar'))
                elif name == 'registro_general':
                    t = QTableWidget(4,4)
                    for i in range(4):
                        for j in range(4):
                            t.setItem(i,j,QTableWidgetItem(f'{i},{j}'))
                    ml.addWidget(QLabel('Registro General'))
                    ml.addWidget(t)
                elif name == 'utilidad':
                    ml.addWidget(QLabel('Utilidad'))
                    ml.addWidget(QLineEdit()); ml.addWidget(QPushButton('Calcular'))
                elif name in ('entrada','salidas'):
                    # Compose a left-side movements table and a right-side lightweight cart preview
                    from PyQt5.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QFrame
                    container = QWidget()
                    hl = QHBoxLayout(container)
                    hl.setContentsMargins(0,0,0,0)
                    hl.setSpacing(8)
                    # left: table of movements
                    t = QTableWidget(3,3)
                    t.setHorizontalHeaderLabels(['ID','Producto','Cantidad'])
                    t.setItem(0,0,QTableWidgetItem('1'))
                    t.setItem(0,1,QTableWidgetItem('Coca'))
                    t.setItem(0,2,QTableWidgetItem('10'))
                    left_col = QWidget(); left_l = QVBoxLayout(left_col); left_l.addWidget(QLabel('Movimientos')); left_l.addWidget(t)
                    hl.addWidget(left_col, 2)
                    # right: mock cart
                    try:
                        from modules.ventas_carrito_cards import ProductoCard
                    except Exception:
                        ProductoCard = None
                    cart_frame = QFrame()
                    cart_layout = QVBoxLayout(cart_frame)
                    cart_layout.setContentsMargins(8,8,8,8)
                    cart_layout.setSpacing(8)
                    sample_items = [
                        {'nombre':'Producto A','codigo':'A001','precio_unitario_bs':120.0,'stock_original':10,'cantidad':1,'unidad':'und'},
                        {'nombre':'Producto B','codigo':'B002','precio_unitario_bs':45.5,'stock_original':5,'cantidad':2,'unidad':'und'},
                        {'nombre':'Producto C','codigo':'C003','precio_unitario_bs':9.75,'stock_original':100,'cantidad':1,'unidad':'und'}
                    ]
                    for idx,it in enumerate(sample_items):
                        try:
                            if ProductoCard:
                                pc = ProductoCard(idx, it)
                                cart_layout.addWidget(pc)
                            else:
                                lbl = QLabel(f"{it['nombre']} • {it['codigo']} — {it['precio_unitario_bs']:.2f} Bs")
                                cart_layout.addWidget(lbl)
                        except Exception:
                            pass
                    cart_layout.addStretch()
                    scroll = QScrollArea()
                    scroll.setWidgetResizable(True)
                    scroll.setWidget(cart_frame)
                    scroll.setFixedWidth(300)
                    hl.addWidget(scroll, 1)
                    ml.addWidget(container)
                elif name == 'graficos':
                    ml.addWidget(QLabel('Gráfico por mes (vista previa)'))
                    ml.addWidget(QLabel('▂▅▇▆▂▁▇▅'))
                elif name == 'caducidad':
                    t = QTableWidget(3,3); t.setHorizontalHeaderLabels(['ID','Nombre','Días']); t.setItem(0,0,QTableWidgetItem('1')); t.setItem(0,1,QTableWidgetItem('Leche')); t.setItem(0,2,QTableWidgetItem('5'))
                    ml.addWidget(QLabel('Caducidad'))
                    ml.addWidget(t)
                proxy = self.preview_scene.addWidget(mock)
                try:
                    br = proxy.boundingRect()
                    self.preview_scene.setSceneRect(br)
                    try:
                        self._fit_preview()
                    except Exception:
                        try:
                            self.preview_view.resetTransform()
                        except Exception:
                            pass
                        try:
                            self.preview_view.fitInView(br, Qt.KeepAspectRatio)
                        except Exception:
                            pass
                except Exception:
                    pass
                # apply merged qss to mock
                try:
                    base = theme_manager.get_palette(self.current_name) or {}
                    merged = dict(base)
                    merged.update(self.current_palette or {})
                    qss = theme_manager.build_qss(merged)
                    mock.setStyleSheet(qss)
                except Exception:
                    pass
                # install interactive handlers on mock
                try:
                    self._install_click_handlers(mock)
                except Exception:
                    pass
            except Exception:
                pass

    def _fit_preview(self):
        try:
            if not hasattr(self, 'preview_scene') or not hasattr(self, 'preview_view'):
                return
            br = self.preview_scene.itemsBoundingRect()
            if br.isNull() or br.width() == 0 or br.height() == 0:
                br = self.preview_scene.sceneRect()
                if br.isNull():
                    return
            try:
                self.preview_scene.setSceneRect(br)
            except Exception:
                pass
            try:
                self.preview_view.resetTransform()
            except Exception:
                pass
            try:
                self.preview_view.fitInView(br, Qt.KeepAspectRatio)
            except Exception:
                pass
            try:
                self.preview_view.centerOn(br.center())
            except Exception:
                pass
        except Exception:
            pass

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        try:
            self._fit_preview()
        except Exception:
            pass

    def _save_active(self):
        # write active theme and additionally build styles.qss
        # if user made custom changes, merge them into palette to persist
        base = theme_manager.get_palette(self.current_name) or {}
        merged = dict(base)
        merged.update(self.current_palette or {})
        # if current_name exists, save over it, else create
        target_name = self.current_name or 'Custom'
        theme_manager.save_palette(target_name, merged)
        theme_manager.build_and_write_styles(target_name)
        theme_manager.apply_theme(__import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance(), target_name)
        self.accept()

    def _apply(self):
        # apply selected palette by name (no custom edits)
        if not self.current_name:
            return
        try:
            theme_manager.apply_theme(__import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance(), self.current_name)
        except Exception:
            try:
                qss = theme_manager.build_qss(self.current_name)
                __import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance().setStyleSheet(qss)
            except Exception:
                pass

        # write active theme and additionally build styles.qss
        # if user made custom changes, merge them into palette to persist
        base = theme_manager.get_palette(self.current_name) or {}
        merged = dict(base)
        merged.update(self.current_palette or {})
        # if current_name exists, save over it, else create
        target_name = self.current_name or 'Custom'
        theme_manager.save_palette(target_name, merged)
        theme_manager.build_and_write_styles(target_name)
        theme_manager.apply_theme(__import__('sys').modules['PyQt5.QtWidgets'].QApplication.instance(), target_name)
        self.accept()


if __name__ == '__main__':
    # quick manual test (not executed by main app)
    pass
