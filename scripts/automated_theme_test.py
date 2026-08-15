import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel
from modules import theme_manager
from modules.theme_editor import ThemeEditor

app = QApplication([])
editor = ThemeEditor()
# set palette
editor.current_name = 'Light' if 'Light' in theme_manager.load_palettes() else next(iter(theme_manager.load_palettes().keys()))
editor.current_palette = dict(theme_manager.get_palette(editor.current_name) or {})

results = {}

# Dashboard: render and color first button red
editor._render_preview('dashboard')
for item in editor.preview_scene.items():
    try:
        w = item.widget()
    except Exception:
        w = None
    if w:
        btns = w.findChildren(QPushButton)
        if btns:
            btn = btns[0]
            try:
                prev = btn.styleSheet() or ''
                btn.setStyleSheet(prev + "\nbackground: #ff0000; color: #ffffff;")
                results['dashboard_button'] = btn.styleSheet()
            except Exception as e:
                results['dashboard_button_error'] = str(e)
            break

# Login: render and color login button red
editor._render_preview('login')
for item in editor.preview_scene.items():
    try:
        w = item.widget()
    except Exception:
        w = None
    if w:
        btns = w.findChildren(QPushButton)
        if btns:
            # try to find by text 'Ingresar'
            found = None
            for b in btns:
                try:
                    if b.text().lower().strip() in ('ingresar','iniciar','ingresar producto','login','entrar'):
                        found = b
                        break
                except Exception:
                    pass
            if not found:
                found = btns[0]
            try:
                prev = found.styleSheet() or ''
                found.setStyleSheet(prev + "\nbackground: #ff0000; color: #ffffff;")
                results['login_button'] = found.styleSheet()
            except Exception as e:
                results['login_button_error'] = str(e)
            break

# Splash: render and enlarge first label
editor._render_preview('splash')
for item in editor.preview_scene.items():
    try:
        w = item.widget()
    except Exception:
        w = None
    if w:
        labs = w.findChildren(QLabel)
        if labs:
            lab = labs[0]
            try:
                prev = lab.styleSheet() or ''
                lab.setStyleSheet(prev + "\nfont-size: 48px; font-family: Arial; font-weight: 800;")
                results['splash_label'] = lab.styleSheet()
            except Exception as e:
                results['splash_label_error'] = str(e)
            break

# Print verification
for k, v in results.items():
    print(f"{k}: {v}")

# tidy
app.quit()
sys.exit(0)
