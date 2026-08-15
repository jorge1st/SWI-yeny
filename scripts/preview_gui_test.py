import sys, time, traceback, os, faulthandler
faulthandler.enable()
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "\\..")
sys.path.insert(0, os.getcwd())
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from modules.theme_editor import ThemeEditor

try:
    app = QApplication([])
    te = ThemeEditor()
    te.show()
    print('Shown: isVisible=', te.isVisible())
    # select dashboard then agregar_productos
    def do_test():
        try:
            print('Selecting dashboard...')
            te.preview_selector.setCurrentText('dashboard')
            app.processEvents()
            time.sleep(0.3)
            print('After dashboard select: visible=', te.isVisible())
            print('Selecting agregar_productos...')
            te.preview_selector.setCurrentText('agregar_productos')
            app.processEvents()
            time.sleep(0.3)
            print('After agregar select: visible=', te.isVisible())
        except Exception:
            traceback.print_exc()
        finally:
            print('Ending test, quitting app')
            try:
                app.quit()
            except Exception:
                pass

    QTimer.singleShot(200, do_test)
    app.exec_()
    print('app.exec_ ended')
except Exception:
    traceback.print_exc()
    raise
