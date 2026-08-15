# modules/graficos.py
"""
Gráficos profesionales estilo dashboard moderno.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QComboBox, QMessageBox, QWidget, QFileDialog, QFrame,
    QCheckBox, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QDate, QTimer, QObject, pyqtSignal, QRunnable, QThreadPool, QPoint, QPointF
from PyQt5.QtGui import (
    QColor, QLinearGradient, QBrush, QPen, QFont, QPainterPath,
    QPolygonF, QPainter, QPixmap
)
from db_manager import DBManager
import datetime
import calendar
import numpy as np

# PyQtGraph
try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtGui, QtCore
    _HAVE_PG = True
except Exception:
    _HAVE_PG = False

DEBUG = True
_POLL_INTERVAL_MS = 5000


class WorkerSignals(QObject):
    finished = pyqtSignal(object)


class QueryWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(res)
        except Exception as e:
            if DEBUG:
                print(f"Worker error: {e}")
            self.signals.finished.emit(None)


def _get_bcv_rate():
    try:
        from main import get_current_bcv_rate
        r, _ = get_current_bcv_rate()
        return r
    except Exception:
        return None


class GraficosWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        if not _HAVE_PG:
            QMessageBox.warning(self, "Error", "pyqtgraph no está instalado.\nEjecuta: pip install pyqtgraph scipy")
            self.reject()
            return
            
        self.db = DBManager()
        self.setWindowTitle("Gráficos de Inventario")
        try:
            from modules.ui_scaling import scale_px

            self.resize(scale_px(1200), scale_px(750))
        except Exception:
            self.resize(1200, 750)
        # Styling moved to styles/modules/graficos.qss
        self.setObjectName("graficos")

        self._last_mov_id = self._get_last_mov_id()
        self._pool = QThreadPool.globalInstance()
        self._curve_data = None
        
        self._build_ui()
        
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._on_poll)
        self._poll_timer.start()
        
        QTimer.singleShot(200, self.generar_grafico)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header
        title = QLabel("Evolución de Stock")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #5E3DB3;")
        
        subtitle = QLabel("Análisis de movimientos de inventario")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #8B7AB8;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Controles
        ctrl_panel = QFrame()
        ctrl_panel.setObjectName("ctrl_panel")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(107, 78, 214, 25))
        shadow.setOffset(0, 4)
        ctrl_panel.setGraphicsEffect(shadow)
        
        ctrl_layout = QHBoxLayout(ctrl_panel)
        ctrl_layout.setContentsMargins(20, 16, 20, 16)

        current_year = QDate.currentDate().year()
        self.year_cb = QComboBox()
        for y in range(current_year - 5, current_year + 2):
            self.year_cb.addItem(str(y))
        self.year_cb.setCurrentText(str(current_year))

        months = [("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"), ("04", "Abril"),
                  ("05", "Mayo"), ("06", "Junio"), ("07", "Julio"), ("08", "Agosto"),
                  ("09", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre")]
        self.start_month_cb = QComboBox()
        self.end_month_cb = QComboBox()
        for code, name in months:
            self.start_month_cb.addItem(name, code)
            self.end_month_cb.addItem(name, code)
        self.end_month_cb.setCurrentIndex(QDate.currentDate().month() - 1)
        sm = max(0, QDate.currentDate().month() - 3)
        self.start_month_cb.setCurrentIndex(sm)

        self.product_cb = QComboBox()
        self._populate_product_list()

        self.smooth_chk = QCheckBox("Curva suave")
        self.smooth_chk.setChecked(False)

        self.btn_generar = QPushButton("📊 Actualizar")
        self.btn_generar.clicked.connect(self.generar_grafico)
        
        self.btn_export = QPushButton("💾 Exportar")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background: #E8E3F5;
                color: #5E3DB3;
            }
            QPushButton:hover {
                background: #D9CBFF;
            }
        """)
        self.btn_export.clicked.connect(self.export_png)

        ctrl_layout.addWidget(QLabel("<b>Año</b>"))
        ctrl_layout.addWidget(self.year_cb)
        ctrl_layout.addWidget(QLabel("<b>Desde</b>"))
        ctrl_layout.addWidget(self.start_month_cb)
        ctrl_layout.addWidget(QLabel("<b>Hasta</b>"))
        ctrl_layout.addWidget(self.end_month_cb)
        ctrl_layout.addWidget(QLabel("<b>Producto</b>"))
        ctrl_layout.addWidget(self.product_cb, 1)
        ctrl_layout.addWidget(self.smooth_chk)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_generar)
        ctrl_layout.addWidget(self.btn_export)
        
        layout.addWidget(ctrl_panel)

        # Gráfico
        graph_card = QFrame()
        graph_card.setObjectName("graph_card")
        
        graph_shadow = QGraphicsDropShadowEffect()
        graph_shadow.setBlurRadius(40)
        graph_shadow.setColor(QColor(107, 78, 214, 20))
        graph_shadow.setOffset(0, 8)
        graph_card.setGraphicsEffect(graph_shadow)
        
        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(24, 20, 24, 20)

        pg.setConfigOptions(antialias=True)
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.03)
        
        # Ejes estilizados
        self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color='#F0F0F0', width=1))
        self.plot_widget.getAxis('left').setPen(pg.mkPen(color='#F0F0F0', width=1))
        self.plot_widget.getAxis('bottom').setTextPen(pg.mkPen(color='#888888'))
        self.plot_widget.getAxis('left').setTextPen(pg.mkPen(color='#888888'))
        
        self.plot_widget.setLabel('left', 'Unidades', color='#666666')
        
        graph_layout.addWidget(self.plot_widget)
        layout.addWidget(graph_card, 1)

        # Label para tooltip
        self.tooltip_label = QLabel(self)
        self.tooltip_label.setObjectName("tooltip_label")
        self.tooltip_label.setVisible(False)

        # Eventos
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _populate_product_list(self):
        self.product_cb.clear()
        self.product_cb.addItem("📦 Todos los productos", "__ALL__")
        try:
            prods = self.db.listar_productos()
            prods = sorted(prods, key=lambda r: (r.get('nombre') or '').lower())
            for p in prods:
                label = f"{p.get('nombre') or 'Sin nombre'} ({p.get('codigo') or 'N/A'})"
                self.product_cb.addItem(label, p.get('id'))
        except Exception as e:
            if DEBUG:
                print(f"Error cargando productos: {e}")

    def _get_last_mov_id(self):
        try:
            row = self.db.fetchone("SELECT MAX(id) as mx FROM movimientos")
            if row and row.get('mx') is not None:
                return int(row.get('mx') or 0)
        except Exception:
            pass
        return 0

    def _range_dates(self):
        year = int(self.year_cb.currentText())
        start_m = self.start_month_cb.currentData()
        end_m = self.end_month_cb.currentData()
        if not start_m or not end_m:
            return f"{year}-01-01", f"{year}-12-31"
        start_date = f"{year}-{start_m}-01"
        end_month = int(end_m)
        last_day = calendar.monthrange(year, end_month)[1]
        end_date = f"{year}-{end_m}-{last_day}"
        return start_date, end_date

    def _on_poll(self):
        try:
            row = self.db.fetchone("SELECT MAX(id) as mx FROM movimientos")
            mx = int(row.get('mx') or 0) if row else 0
            if mx <= self._last_mov_id:
                return
            self._last_mov_id = mx
            self.generar_grafico()
        except Exception:
            pass

    def _build_plot_data(self):
        try:
            start_date, end_date = self._range_dates()
            pid = self.product_cb.currentData()
            
            if pid == "__ALL__" or pid is None:
                # Resumen mensual
                q = """
                    SELECT strftime('%Y-%m', fecha_registro) AS ym,
                           SUM(COALESCE(stock,0.0)) AS total_stock
                    FROM productos
                    WHERE date(fecha_registro) BETWEEN date(?) AND date(?)
                    GROUP BY ym
                    ORDER BY ym
                """
                rows = self.db.fetchall(q, (start_date, end_date)) or []
                months = self._month_list(start_date, end_date)
                stock_map = {r['ym']: float(r.get('total_stock') or 0.0) for r in rows}
                
                x_dates = [datetime.datetime.strptime(m + "-15", "%Y-%m-%d") for m in months]
                stocks = [stock_map.get(m, 0.0) for m in months]
                
                return {'x': x_dates, 'y': stocks, 'title': 'Stock Total por Mes'}
            else:
                # Producto específico
                prod = self.db.fetchone("SELECT * FROM productos WHERE id = ?", (pid,)) or {}
                current_stock = float(prod.get('stock') or 0.0)
                
                q_after = """
                    SELECT lower(tipo) as tipo, SUM(COALESCE(cantidad,0.0)) as ssum
                    FROM movimientos
                    WHERE producto_id = ? AND date(fecha) >= date(?)
                    GROUP BY lower(tipo)
                """
                rows_after = self.db.fetchall(q_after, (pid, start_date)) or []
                sum_after = 0.0
                for r in rows_after:
                    tipo = (r.get('tipo') or '').strip().lower()
                    s = float(r.get('ssum') or 0.0)
                    sum_after += s if tipo == 'entrada' else -s
                initial_stock = current_stock - sum_after
                
                q_mov = """
                    SELECT fecha, tipo, cantidad 
                    FROM movimientos 
                    WHERE producto_id = ? AND date(fecha) BETWEEN date(?) AND date(?) 
                    ORDER BY fecha ASC
                """
                movs = self.db.fetchall(q_mov, (pid, start_date, end_date)) or []
                
                times = []
                values = []
                
                start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                times.append(start_dt)
                values.append(initial_stock)
                cum = initial_stock
                
                for m in movs:
                    fecha = m.get('fecha') or ''
                    try:
                        dt = datetime.datetime.strptime(str(fecha)[:19], "%Y-%m-%dT%H:%M:%S")
                    except:
                        try:
                            dt = datetime.datetime.strptime(str(fecha)[:10], "%Y-%m-%d")
                        except:
                            dt = times[-1] + datetime.timedelta(days=1)
                    
                    tipo = (m.get('tipo') or '').strip().lower()
                    delta = float(m.get('cantidad') or 0.0)
                    cum += delta if tipo == 'entrada' else -delta
                    times.append(dt)
                    values.append(cum)
                
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                if times and end_dt > times[-1]:
                    times.append(end_dt)
                    values.append(values[-1])
                
                return {
                    'x': times, 
                    'y': values,
                    'title': f"{prod.get('nombre') or 'Producto'} - Evolución de Stock"
                }
        except Exception as e:
            if DEBUG:
                print(f"Error build data: {e}")
            return None

    def _smooth_curve(self, x, y):
        """Genera curva suave tipo spline"""
        x = np.array(x)
        y = np.array(y)
        
        if len(x) < 2:
            return x, y
        
        n_points = max(400, len(x) * 80)
        
        if len(x) == 2:
            x_new = np.linspace(x.min(), x.max(), n_points)
            y_new = np.interp(x_new, x, y)
            return x_new, y_new
        
        try:
            from scipy.interpolate import make_interp_spline, UnivariateSpline
            
            sort_idx = np.argsort(x)
            x_sorted = x[sort_idx]
            y_sorted = y[sort_idx]
            
            # Eliminar duplicados
            mask = np.concatenate(([True], np.diff(x_sorted) > 0))
            x_u = x_sorted[mask]
            y_u = y_sorted[mask]
            
            if len(x_u) < 2:
                raise ValueError("Pocos puntos")
            
            # Spline suavizado
            if len(x_u) >= 4:
                spl = UnivariateSpline(x_u, y_u, s=len(x_u))
                x_new = np.linspace(x_u.min(), x_u.max(), n_points)
                y_new = spl(x_new)
            else:
                cs = make_interp_spline(x_u, y_u, k=min(3, len(x_u)-1))
                x_new = np.linspace(x_u.min(), x_u.max(), n_points)
                y_new = cs(x_new)
            
            return x_new, y_new
            
        except ImportError:
            pass
        except Exception as e:
            if DEBUG:
                print(f"Spline error: {e}")
        
        # Fallback: Catmull-Rom
        return self._catmull_rom(x, y, n_points)

    def _catmull_rom(self, x, y, num_points):
        """Spline Catmull-Rom manual"""
        points = list(zip(x, y))
        result_x, result_y = [], []
        
        for i in range(len(points) - 1):
            p0 = points[max(0, i-1)]
            p1 = points[i]
            p2 = points[i+1]
            p3 = points[min(len(points)-1, i+2)]
            
            for t in np.linspace(0, 1, 40):
                t2 = t * t
                t3 = t2 * t
                
                x_val = 0.5 * (
                    (2 * p1[0]) +
                    (-p0[0] + p2[0]) * t +
                    (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +
                    (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3
                )
                y_val = 0.5 * (
                    (2 * p1[1]) +
                    (-p0[1] + p2[1]) * t +
                    (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +
                    (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3
                )
                result_x.append(x_val)
                result_y.append(y_val)
        
        return np.array(result_x), np.array(result_y)

    def _plot_data(self, data):
        self.plot_widget.clear()
        self._curve_data = data
        
        x_raw = data['x']
        y_raw = data['y']
        
        if not x_raw or not y_raw or len(x_raw) < 2:
            return
        
        # Convertir a timestamps
        x_ts = np.array([dt.timestamp() for dt in x_raw])
        y = np.array(y_raw)
        
        # Curva suave
        if self.smooth_chk.isChecked():
            x_plot, y_plot = self._smooth_curve(x_ts, y)
        else:
            x_plot, y_plot = x_ts, y
        
        # GRADIENTE PARA ÁREA
        gradient = QLinearGradient(0, 0, 0, 400)
        gradient.setColorAt(0, QColor(142, 115, 230, 180))
        gradient.setColorAt(0.5, QColor(107, 78, 214, 100))
        gradient.setColorAt(1, QColor(107, 78, 214, 20))
        
        # ÁREA BAJO LA CURVA
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(x_plot, y_plot),
            pg.PlotDataItem(x_plot, np.zeros_like(y_plot)),
            brush=QBrush(gradient)
        )
        self.plot_widget.addItem(fill)
        
        # LÍNEA PRINCIPAL
        pen = pg.mkPen(color=QColor(107, 78, 214), width=3)
        self.plot_widget.plot(x_plot, y_plot, pen=pen)
        
        # PUNTOS ORIGINALES CON SOMBRA
        for xi, yi in zip(x_ts, y):
            # Sombra
            shadow = pg.ScatterPlotItem(
                x=[xi], y=[yi-0.5],
                size=10,
                brush=pg.mkBrush(color=QColor(0, 0, 0, 40)),
                pen=pg.mkPen(color=QColor(0, 0, 0, 0))
            )
            self.plot_widget.addItem(shadow)
        
        # Puntos principales
        scatter = pg.ScatterPlotItem(
            x=x_ts, 
            y=y,
            size=11,
            pen=pg.mkPen(color='white', width=2),
            brush=pg.mkBrush(color=QColor(107, 78, 214)),
            hoverable=True,
            hoverPen=pg.mkPen(color=QColor(180, 160, 255), width=3),
            hoverBrush=pg.mkBrush(color=QColor(142, 115, 230)),
            hoverSize=13
        )
        self.plot_widget.addItem(scatter)
        
        # Guardar datos para tooltip
        self._hover_points = []
        for dt, val, ts in zip(x_raw, y_raw, x_ts):
            self._hover_points.append({
                'ts': ts,
                'date': dt,
                'value': val
            })
        
        # Rangos
        x_pad = (x_ts.max() - x_ts.min()) * 0.08
        self.plot_widget.setXRange(x_ts.min() - x_pad, x_ts.max() + x_pad)
        
        y_min, y_max = y.min(), y.max()
        y_pad = max((y_max - y_min) * 0.15, y_max * 0.05)
        self.plot_widget.setYRange(max(0, y_min - y_pad), y_max + y_pad)

    def _on_mouse_moved(self, pos):
        try:
            if not hasattr(self, '_hover_points') or not self._hover_points:
                self.tooltip_label.hide()
                return
            
            mouse_point = self.plot_widget.getViewBox().mapSceneToView(pos)
            mouse_x = mouse_point.x()
            
            # Punto más cercano
            closest = None
            min_dist = float('inf')
            
            for p in self._hover_points:
                dist = abs(p['ts'] - mouse_x)
                if dist < min_dist and dist < 86400 * 25:
                    min_dist = dist
                    closest = p
            
            if closest:
                date_str = closest['date'].strftime("%d %b %Y")
                value_str = f"Stock: {closest['value']:,.0f} unidades"
                
                self.tooltip_label.setText(f"  {date_str}\n  <b>{value_str}</b>  ")
                self.tooltip_label.adjustSize()
                
                # Posición
                view_pos = self.plot_widget.getViewBox().mapViewToScene(
                    QPointF(closest['ts'], closest['value'])
                )
                global_pos = self.plot_widget.mapToGlobal(view_pos.toPoint())
                local_pos = self.mapFromGlobal(global_pos)
                
                self.tooltip_label.move(
                    int(local_pos.x() - self.tooltip_label.width()/2),
                    int(local_pos.y() - self.tooltip_label.height() - 15)
                )
                self.tooltip_label.show()
                self.tooltip_label.raise_()
            else:
                self.tooltip_label.hide()
                
        except Exception as e:
            if DEBUG:
                print(f"Tooltip error: {e}")
            self.tooltip_label.hide()

    def generar_grafico(self):
        worker = QueryWorker(self._build_plot_data)
        worker.signals.finished.connect(self._on_data_ready)
        self._pool.start(worker)

    def _on_data_ready(self, data):
        if data:
            self._plot_data(data)

    def _month_list(self, start_date, end_date):
        s = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        e = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        months = []
        cur = datetime.date(s.year, s.month, 15)
        while cur <= e:
            months.append(cur.strftime("%Y-%m"))
            if cur.month == 12:
                cur = datetime.date(cur.year + 1, 1, 15)
            else:
                cur = datetime.date(cur.year, cur.month + 1, 15)
        return months

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar gráfico", "grafico.png", "PNG files (*.png)"
        )
        if not path:
            return
        try:
            pixmap = QPixmap(self.plot_widget.size())
            pixmap.fill(Qt.white)
            painter = QPainter(pixmap)
            self.plot_widget.render(painter)
            painter.end()
            pixmap.save(path)
            QMessageBox.information(self, "Éxito", f"Guardado en:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar: {e}")

    def closeEvent(self, ev):
        try:
            self._poll_timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)

