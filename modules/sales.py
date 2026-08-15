# modules/sales.py
"""
Funciones para calcular al momento de venta partiendo de precio_final registrado
(ahora: precio en USD incluyendo IVA).
Provee el desglose de precio sin IVA, IVA, totales y utilidad (excluyendo IVA).
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, Any, Optional

getcontext().prec = 28
DEC_2 = Decimal("0.01")
DEC_USD = Decimal("0.0001")

def D(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')

def compute_sale_from_saved_price(precio_final_usd_con_iva: float, iva_pct: float, costo_orig: float, moneda_cost: str,
                                  tasa_bcv: Optional[float], qty: float = 1.0) -> Dict[str, Any]:
    """
    Parámetros:
      - precio_final_usd_con_iva: precio guardado en BD en USD (incluye IVA)
      - iva_pct: porcentaje IVA registrado en producto (ej. 16)
      - costo_orig: costo almacenado (en USD si moneda_cost == '$' o en Bs si 'Bs')
      - moneda_cost: '$' or 'Bs'
      - tasa_bcv: Bs por 1 USD o None
      - qty: cantidad vendida

    Retorna dict con montos en Bs (cuando posible) y utilidades excluyendo IVA.
    """
    notes = []
    precio_with_iva_usd = D(precio_final_usd_con_iva)
    iva_d = D(iva_pct)
    qty_d = D(qty)
    tasa = D(tasa_bcv) if tasa_bcv is not None else None

    # precio_sin_iva_usd = precio_with_iva_usd / (1 + iva_pct/100)
    denom = (Decimal('1') + (iva_d / Decimal('100')))
    precio_sin_iva_usd = (precio_with_iva_usd / denom).quantize(DEC_USD, rounding=ROUND_HALF_UP)

    # convertir a Bs si hay tasa
    precio_sin_iva_bs = precio_with_iva_bs = iva_unit_bs = None
    if tasa and tasa != Decimal('0'):
        precio_sin_iva_bs = (precio_sin_iva_usd * tasa).quantize(DEC_2, rounding=ROUND_HALF_UP)
        precio_with_iva_bs = (precio_with_iva_usd * tasa).quantize(DEC_2, rounding=ROUND_HALF_UP)
        iva_unit_bs = (precio_with_iva_bs - precio_sin_iva_bs).quantize(DEC_2, rounding=ROUND_HALF_UP)
    else:
        notes.append("Tasa BCV faltante; no se pueden calcular montos en Bs desde USD")

    # costo en Bs
    cost_unit_bs = None
    if moneda_cost in ('$', 'usd', 'USD'):
        if tasa and tasa != Decimal('0'):
            cost_unit_bs = (D(costo_orig) * tasa).quantize(DEC_2, rounding=ROUND_HALF_UP)
        else:
            cost_unit_bs = None
            notes.append("Tasa BCV faltante; costo en Bs no calculado")
    else:
        cost_unit_bs = D(costo_orig).quantize(DEC_2, rounding=ROUND_HALF_UP)

    # Totales y utilidades (si disponemos)
    revenue_total_bs = net_revenue_bs = iva_total_bs = None
    if precio_with_iva_bs is not None:
        revenue_total_bs = (precio_with_iva_bs * qty_d).quantize(DEC_2, rounding=ROUND_HALF_UP)
    if precio_sin_iva_bs is not None:
        net_revenue_bs = (precio_sin_iva_bs * qty_d).quantize(DEC_2, rounding=ROUND_HALF_UP)
    if iva_unit_bs is not None:
        iva_total_bs = (iva_unit_bs * qty_d).quantize(DEC_2, rounding=ROUND_HALF_UP)

    profit_unit_bs = profit_total_bs = None
    if precio_sin_iva_bs is not None and cost_unit_bs is not None:
        profit_unit_bs = (precio_sin_iva_bs - cost_unit_bs).quantize(DEC_2, rounding=ROUND_HALF_UP)
        profit_total_bs = (profit_unit_bs * qty_d).quantize(DEC_2, rounding=ROUND_HALF_UP)
    else:
        notes.append("No se pudo calcular utilidad (faltan precio o costo en Bs)")

    return {
        "precio_sin_iva_usd": precio_sin_iva_usd,
        "precio_with_iva_usd": precio_with_iva_usd,
        "precio_sin_iva_bs": precio_sin_iva_bs,
        "precio_with_iva_bs": precio_with_iva_bs,
        "iva_unit_bs": iva_unit_bs,
        "revenue_total_bs": revenue_total_bs,
        "iva_total_bs": iva_total_bs,
        "net_revenue_bs": net_revenue_bs,
        "cost_unit_bs": cost_unit_bs,
        "profit_unit_bs": profit_unit_bs,
        "profit_total_bs": profit_total_bs,
        "notes": notes
    }

