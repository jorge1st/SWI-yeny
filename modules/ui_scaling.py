"""
modules/ui_scaling.py

Central helper for UI scaling. Exposes:
- get_ui_scale(): returns float scale factor (>=1.0)
- scale_px(n): returns int pixels scaled according to scale factor (only scales up when factor>1)
- scale_qss(qss_text): scales px values inside QSS text (preserves 0px)

This module uses lazy imports to avoid circular import problems and provides safe fallbacks.
"""
from typing import Union
import re


def _get_main_ui_scale() -> float:
    """Internal: try to call main.get_ui_scale() lazily, fallback to 1.0 on error."""
    try:
        # import lazily to avoid circular imports during module import time
        import importlib
        main = importlib.import_module('main')
        if hasattr(main, 'get_ui_scale'):
            s = main.get_ui_scale()
            if s is None:
                return 1.0
            s = float(s)
            if s <= 0:
                return 1.0
            return s
        return 1.0
    except Exception:
        return 1.0


def get_ui_scale() -> float:
    """Public API: return current UI scale factor (>=1.0)."""
    return _get_main_ui_scale()


def scale_px(n: Union[int, float]) -> int:
    """Scale a pixel value `n` according to global UI scale.

    Policy: only scale when scale factor > 1.0 (we don't shrink UI for smaller screens).
    Preserves 0 exactly (0px -> 0px). Guarantees at least 1px for non-zero values.
    """
    try:
        s = _get_main_ui_scale()
        n_f = float(n)
        if n_f == 0:
            return 0
        if s <= 1.0:
            return max(1, int(round(n_f)))
        return max(1, int(round(n_f * s)))
    except Exception:
        return max(1, int(round(float(n))))


def scale_qss(qss_text: str) -> str:
    """Scale px values inside a QSS stylesheet text. Preserves 0px.

    Example: 'font-size: 12px;' -> 'font-size: 18px;' when scale is 1.5
    """
    def _repl(m):
        val_str = m.group(1)
        try:
            val = float(val_str)
            if val == 0:
                return '0px'
            return f"{scale_px(val)}px"
        except Exception:
            return m.group(0)

    return re.sub(r'(\d+(?:\.\d+)?)px', _repl, qss_text)
