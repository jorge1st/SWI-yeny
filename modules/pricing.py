# modules/pricing.py
"""
Cálculos de precio alineados a la convención:
- TODOS los productos se almacenan en USD como moneda base (precio_final).
- El precio en Bs (precio_final_bs) es SIEMPRE una referencia calculada al momento.
- Esto protege el valor del producto ante la devaluación del Bs.

Flujo:
1. Si registro en USD: calculo normal, guardo USD, calculo referencia Bs si hay tasa
2. Si registro en Bs: calculo precio final en Bs (costo + iva + ganancia), 
   CONVIERTO a USD usando tasa actual, guardo USD como precio base permanente
3. Para ventas/mostrado: siempre tomo USD guardado y convierto a Bs con tasa actual

La ganancia se interpreta como MARKUP sobre el costo:
    precio_sin_iva = costo * (1 + gan_pct/100)
  y luego se aplica IVA encima: precio_with_iva = precio_sin_iva * (1 + iva_pct/100)
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, getcontext
from typing import Optional, Dict

getcontext().prec = 28

# precisiones
DEC_2 = Decimal("0.01")
DEC_USD = Decimal("0.0001")

def D(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')

def calcular_desde_usd(costo_usd, iva_pct, gan_pct, tasa_bcv: Optional[float]) -> Dict[str, Optional[Decimal]]:
    """
    Registro en USD: calculo directo, USD es la moneda base.
    """
    costo = D(costo_usd)
    iva = D(iva_pct) if iva_pct is not None else D('0')
    gan = D(gan_pct) if gan_pct is not None else D('0')

    # 1) precio sin IVA (markup sobre costo)
    precio_sin_iva_usd = (costo * (Decimal('1') + (gan / Decimal('100')))).quantize(DEC_USD, rounding=ROUND_HALF_UP)

    # 2) aplicar IVA encima -> ESTE es el precio de venta en USD (PERMANENTE)
    precio_with_iva_usd = (precio_sin_iva_usd * (Decimal('1') + (iva / Decimal('100')))).quantize(DEC_USD, rounding=ROUND_HALF_UP)

    iva_unit_usd = (precio_with_iva_usd - precio_sin_iva_usd).quantize(DEC_USD, rounding=ROUND_HALF_UP)
    ganancia_unit_usd = (precio_sin_iva_usd - costo).quantize(DEC_USD, rounding=ROUND_HALF_UP)

    # 3) Referencia en Bs (SOLO para mostrar, no se guarda como base)
    bcv = D(tasa_bcv) if tasa_bcv is not None else None
    precio_sin_iva_bs = precio_with_iva_bs = iva_unit_bs = ganancia_unit_bs = None
    if bcv and bcv != Decimal('0'):
        precio_sin_iva_bs = (precio_sin_iva_usd * bcv).quantize(DEC_2, rounding=ROUND_HALF_UP)
        precio_with_iva_bs = (precio_with_iva_usd * bcv).quantize(DEC_2, rounding=ROUND_HALF_UP)
        iva_unit_bs = (iva_unit_usd * bcv).quantize(DEC_2, rounding=ROUND_HALF_UP)
        ganancia_unit_bs = (ganancia_unit_usd * bcv).quantize(DEC_2, rounding=ROUND_HALF_UP)

    return {
        "precio_sin_iva_usd": precio_sin_iva_usd,
        "precio_with_iva_usd": precio_with_iva_usd,      # ← PRECIO BASE PERMANENTE (USD)
        "precio_sin_iva_bs": precio_sin_iva_bs,          # ← Referencia temporal
        "precio_with_iva_bs": precio_with_iva_bs,        # ← Referencia temporal
        "iva_unit_usd": iva_unit_usd,
        "iva_unit_bs": iva_unit_bs,
        "ganancia_unit_usd": ganancia_unit_usd,
        "ganancia_unit_bs": ganancia_unit_bs,
        "bcv_tasa": bcv
    }

def calcular_desde_bs(costo_bs, iva_pct, gan_pct, tasa_bcv: Optional[float]) -> Dict[str, Optional[Decimal]]:
    """
    Registro en Bs: calculo el precio final en Bs, pero INMEDIATAMENTE convierto a USD
    usando la tasa actual para guardar el precio base PERMANENTE en USD.
    
    REQUIERE tasa_bcv obligatoriamente para poder hacer la conversión.
    """
    costo = D(costo_bs)
    iva = D(iva_pct) if iva_pct is not None else D('0')
    gan = D(gan_pct) if gan_pct is not None else D('0')
    bcv = D(tasa_bcv) if tasa_bcv is not None else None

    if not bcv or bcv == Decimal('0'):
        raise ValueError("Se requiere la tasa BCV para registrar productos en Bs. "
                        "El sistema convierte a USD para proteger el valor ante devaluación.")

    # 1) Calcular precio en Bs (para referencia/visualización)
    precio_sin_iva_bs = (costo * (Decimal('1') + (gan / Decimal('100')))).quantize(DEC_2, rounding=ROUND_HALF_UP)
    precio_with_iva_bs = (precio_sin_iva_bs * (Decimal('1') + (iva / Decimal('100')))).quantize(DEC_2, rounding=ROUND_HALF_UP)

    iva_unit_bs = (precio_with_iva_bs - precio_sin_iva_bs).quantize(DEC_2, rounding=ROUND_HALF_UP)
    ganancia_unit_bs = (precio_sin_iva_bs - costo).quantize(DEC_2, rounding=ROUND_HALF_UP)

    # 2) CONVERTIR A USD para guardar como precio base PERMANENTE
    # El precio en USD no cambiará nunca, independientemente de futuras tasas
    precio_sin_iva_usd = (precio_sin_iva_bs / bcv).quantize(DEC_USD, rounding=ROUND_HALF_UP)
    precio_with_iva_usd = (precio_with_iva_bs / bcv).quantize(DEC_USD, rounding=ROUND_HALF_UP)
    iva_unit_usd = (iva_unit_bs / bcv).quantize(DEC_USD, rounding=ROUND_HALF_UP)
    ganancia_unit_usd = (ganancia_unit_bs / bcv).quantize(DEC_USD, rounding=ROUND_HALF_UP)

    return {
        "precio_sin_iva_bs": precio_sin_iva_bs,          # ← Referencia al momento del registro
        "precio_with_iva_bs": precio_with_iva_bs,        # ← Referencia al momento del registro
        "precio_sin_iva_usd": precio_sin_iva_usd,
        "precio_with_iva_usd": precio_with_iva_usd,      # ← PRECIO BASE PERMANENTE (USD)
        "iva_unit_bs": iva_unit_bs,
        "iva_unit_usd": iva_unit_usd,
        "ganancia_unit_bs": ganancia_unit_bs,
        "ganancia_unit_usd": ganancia_unit_usd,
        "bcv_tasa": bcv  # Tasa usada para la conversión (referencia histórica)
    }

def calcular_precio_venta_actual(precio_usd_almacenado: float, tasa_bcv_actual: Optional[float]) -> Dict[str, Optional[Decimal]]:
    """
    Calcula el precio de venta actual en Bs a partir del USD almacenado.
    Usar esta función SIEMPRE para mostrar precios en Bs o registrar ventas.
    
    El precio en USD nunca cambia, el precio en Bs fluctúa con la tasa.
    """
    precio_usd = D(precio_usd_almacenado)
    tasa = D(tasa_bcv_actual) if tasa_bcv_actual is not None else None
    
    precio_bs_actual = None
    if tasa and tasa != Decimal('0'):
        precio_bs_actual = (precio_usd * tasa).quantize(DEC_2, rounding=ROUND_HALF_UP)
    
    return {
        "precio_usd": precio_usd,           # Precio base permanente
        "precio_bs_actual": precio_bs_actual,  # Precio en Bs al momento (para venta)
        "tasa_usada": tasa
    }

def format_usd_minimal(value: Optional[Decimal]) -> str:
    if value is None:
        return "-- $"
    try:
        q = value.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        s = f"{q:,.2f}"; s = s.rstrip('0').rstrip('.')
        return f"{s} $"
    except Exception:
        try:
            return f"{float(value):.2f} $"
        except Exception:
            return "-- $"

def format_bs_minimal(value: Optional[Decimal]) -> str:
    if value is None:
        return "-- Bs"
    try:
        q = value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return f"{q:,.2f} Bs"
    except Exception:
        try:
            return f"{float(value):.2f} Bs"
        except Exception:
            return "-- Bs"

