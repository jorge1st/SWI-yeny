import sys, os, traceback
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "\\..")
sys.path.insert(0, os.getcwd())
from PyQt5.QtWidgets import QApplication
from modules.theme_editor import ThemeEditor

def run_one(te, name):
    print('\n--- Preview:', name)
    try:
        te._render_preview(name)
        scene = te.preview_scene
        items = scene.items()
        print(' scene items count:', len(items))
        for i,it in enumerate(items):
            w = None
            try:
                if hasattr(it, 'widget'):
                    w = it.widget()
            except Exception:
                w = None
            print(f'  item {i}: widget={bool(w)}, type={type(w) if w else None}')
            if w:
                try:
                    print('   size:', w.size(), 'w,h', w.width(), w.height())
                except Exception as e:
                    print('   size error', e)
        try:
            print(' sceneRect:', scene.sceneRect())
        except Exception as e:
            print(' sceneRect error', e)
    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    app = QApplication([])
    te = ThemeEditor()
    print('ThemeEditor created; palettes:', list(te.palettes.keys()))
    for name in ['login','dashboard','agregar_productos','registro_general','splash']:
        run_one(te, name)
    print('\nSimulating selector change to agregar_productos via _on_preview_change()')
    try:
        te._on_preview_change('agregar_productos')
        print('After selector call: visible=', te.isVisible())
    except Exception:
        traceback.print_exc()
    print('\nDone')
