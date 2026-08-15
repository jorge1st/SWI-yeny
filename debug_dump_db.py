#!/usr/bin/env python3
# Ejecutar: python debug_dump_db.py
import sqlite3
import sys
from pprint import pprint

DB = "inventory.db"  # ajusta si tu DB se llama distinto o está en otra ruta

def dump():
    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(productos)")
        cols = cur.fetchall()
        print("PRAGMA table_info(productos):")
        for c in cols:
            print(tuple(c))
        print("\n---- Contenido productos (orden descendente por id) ----")
        cur.execute("SELECT id, codigo, nombre, descripcion, departamento, stock, unidad, costo_compra, precio_final, moneda, fecha_registro, fecha_caducidad FROM productos ORDER BY id DESC")
        rows = cur.fetchall()
        if not rows:
            print("No hay filas en la tabla productos.")
            return
        for r in rows:
            # imprimir repr de cada campo para ver espacios invisibles / None
            print("-" * 60)
            for k in r.keys():
                v = r[k]
                print(f"{k}: {repr(v)}")
    except Exception as e:
        print("ERROR al abrir DB:", e)
        sys.exit(1)

if __name__ == "__main__":
    dump()
