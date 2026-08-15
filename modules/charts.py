# modules/charts.py
"""
Funciones utilitarias para obtener y visualizar stock de productos
de forma segura (evitando duplicados y errores de agregación).
- get_stock_by_product(db): devuelve [(label, stock), ...] agrupado por código o nombre.
- get_total_stock(db): suma COALESCE(stock,0) desde productos.
- get_stock_from_movements(db): calcula stock acumulado a partir de movimientos (Entradas/Salidas).
- compare_stock_sources(db): compara stock en productos vs. stock calculado desde movimientos.
- plot_stock_bar(labels, values): ejemplo simple con matplotlib.
"""
from typing import List, Tuple, Dict, Optional
from decimal import Decimal
import logging

# opcional: matplotlib para graficar
try:
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False

def _to_float_safe(v) -> float:
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace(',', ''))
        except Exception:
            return 0.0

def get_stock_by_product(db, key='codigo') -> List[Tuple[str, float]]:
    """
    Recupera products desde la tabla productos y devuelve una lista
    (label, stock) agrupada por codigo si existe, o por nombre en su defecto.
    key: 'codigo' o 'nombre' (clave para agrupar).
    """
    rows = db.fetchall("SELECT id, codigo, nombre, COALESCE(stock,0.0) AS stock FROM productos")
    grouped: Dict[str, float] = {}
    for r in rows:
        code = (r.get('codigo') or '').strip()
        name = (r.get('nombre') or '').strip()
        stock = _to_float_safe(r.get('stock', 0.0))
        # elegir clave robusta: codigo si existe, sino nombre
        if key == 'codigo':
            k = code if code else name
        else:
            k = name if name else code
        if not k:
            # fallback a id
            k = f"id:{r.get('id')}"
        # evitar nil/empty keys
        grouped.setdefault(k, 0.0)
        # si se desea ignorar duplicados, comentar la siguiente línea y usar 'set' de ids en su lugar.
        grouped[k] += stock
    # convertir a lista ordenada por stock descendente
    items = sorted(grouped.items(), key=lambda x: x[1], reverse=True)
    return items

def get_total_stock(db) -> float:
    """
    Suma simple del stock en la tabla productos: SELECT SUM(COALESCE(stock,0))
    """
    row = db.fetchone("SELECT SUM(COALESCE(stock,0.0)) AS total_stock FROM productos")
    if not row:
        return 0.0
    return _to_float_safe(row.get('total_stock', 0.0))

def get_stock_from_movements(db) -> Dict[int, float]:
    """
    Calcula stock por producto_id a partir de la tabla movimientos:
      stock_calc = SUM(CASE WHEN tipo='Entrada' THEN cantidad ELSE -cantidad END)
    Devuelve dict {producto_id: stock_calc}
    """
    # esta consulta asume que la columna 'tipo' contiene 'Entrada' o 'Salida'
    rows = db.fetchall("""
        SELECT producto_id, 
               SUM(CASE WHEN LOWER(COALESCE(tipo,'')) = 'entrada' THEN cantidad 
                        WHEN LOWER(COALESCE(tipo,'')) = 'salida' THEN -cantidad 
                        ELSE 0 END) AS stock_calc
        FROM movimientos
        GROUP BY producto_id
    """)
    res: Dict[int, float] = {}
    for r in rows:
        pid = r.get('producto_id')
        if pid is None:
            continue
        res[int(pid)] = _to_float_safe(r.get('stock_calc', 0.0))
    return res

def compare_stock_sources(db) -> Dict[str, object]:
    """
    Compara stock en productos.stock vs stock calculado desde movimientos.
    Devuelve dict con listas de discrepancias para análisis.
    """
    # cargar productos
    products = db.fetchall("SELECT id, codigo, nombre, COALESCE(stock,0.0) AS stock FROM productos")
    prod_map = {}
    for p in products:
        pid = p.get('id')
        prod_map[int(pid)] = {
            'id': int(pid),
            'codigo': p.get('codigo'),
            'nombre': p.get('nombre'),
            'stock_product': _to_float_safe(p.get('stock', 0.0))
        }

    mov_map = get_stock_from_movements(db)

    discrepancies = []
    for pid, info in prod_map.items():
        stock_prod = info['stock_product']
        stock_mov = mov_map.get(pid, 0.0)
        if abs(stock_prod - stock_mov) >= 0.0001 and (stock_prod != 0.0 or stock_mov != 0.0):
            discrepancies.append({
                'producto_id': pid,
                'codigo': info.get('codigo'),
                'nombre': info.get('nombre'),
                'stock_product': stock_prod,
                'stock_from_movements': stock_mov,
                'difference': stock_prod - stock_mov
            })

    total_product_stock = get_total_stock(db)
    total_mov_stock = sum(mov_map.values()) if mov_map else 0.0

    return {
        'total_product_stock': total_product_stock,
        'total_mov_stock': total_mov_stock,
        'discrepancies': discrepancies
    }

def plot_stock_bar(labels: List[str], values: List[float], title: str = "Stock por producto", horizontal: bool = True):
    """
    Plot simple using matplotlib. If matplotlib no está instalado, lanza excepción.
    """
    if not _HAS_MPL:
        raise RuntimeError("matplotlib no está disponible en este entorno.")
    plt.figure(figsize=(10, max(3, len(labels) * 0.4)))
    if horizontal:
        plt.barh(labels, values, color='tab:purple')
        plt.xlabel('Unidades en stock')
    else:
        plt.bar(labels, values, color='tab:purple')
        plt.ylabel('Unidades en stock')
        plt.xticks(rotation=45, ha='right')
    plt.title(title)
    plt.tight_layout()
    plt.show()

# Helper rápido usado en UI:
def get_chart_data_for_ui(db) -> Tuple[List[str], List[float]]:
    """
    Retorna (labels, values) listo para pasar al gráfico de la UI.
    Filtra productos con stock 0 opcionalmente (aquí incluimos todos).
    """
    items = get_stock_by_product(db, key='codigo')
    labels = [k for k, v in items]
    values = [v for k, v in items]
    return labels, values

