import os
import json

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
STYLES_DIR = os.path.join(ROOT_DIR, 'styles')
MODULES_QSS_DIR = os.path.join(STYLES_DIR, 'modules')
PALETTES_PATH = os.path.join(STYLES_DIR, 'palettes.json')
OUTPUT_QSS = os.path.join(ROOT_DIR, 'styles.qss')
ACTIVE_THEME_PATH = os.path.join(STYLES_DIR, 'active_theme.json')


DEFAULT_PALETTES = {
    "Light": {
        "PRIMARY": "#6B4ED6",
        "PRIMARY_DARK": "#5A3FC7",
        "PRIMARY_LIGHT": "#8E6BE6",
        "BG": "#F8F6FF",
        "SURFACE": "#FFFFFF",
        "TEXT": "#222222",
        "TEXT_COLOR": "#222222",
        "ACCENT": "#00C853",
        "BTN_BG": "#8E6BE6",
        "BTN_HOVER": "#6B4ED6",
        "CARD_BG": "#FFFFFF",
        "FONT_FAMILY": "Segoe UI",
        "FONT_SIZE": "13px",
        "BORDER": "#E8E3F5"
    },
    "Dark": {
        "PRIMARY": "#2E2E3A",
        "PRIMARY_DARK": "#1F1F28",
        "PRIMARY_LIGHT": "#484850",
        "BG": "#121217",
        "SURFACE": "#1B1B20",
        "TEXT": "#E6E6E6",
        "TEXT_COLOR": "#E6E6E6",
        "ACCENT": "#FFB86B",
        "BTN_BG": "#33323A",
        "BTN_HOVER": "#44444A",
        "CARD_BG": "#1B1B20",
        "FONT_FAMILY": "Segoe UI",
        "FONT_SIZE": "13px",
        "BORDER": "#2A2A31"
    },
    "PurpleAccent": {
        "PRIMARY": "#4A3BA5",
        "PRIMARY_DARK": "#3B2E8A",
        "PRIMARY_LIGHT": "#D9CBFF",
        "BG": "#FBF9FF",
        "SURFACE": "#FFFFFF",
        "TEXT": "#1E1B29",
        "TEXT_COLOR": "#1E1B29",
        "ACCENT": "#FF6B6B",
        "BTN_BG": "#D9CBFF",
        "BTN_HOVER": "#C8B5FF",
        "CARD_BG": "#FFFFFF",
        "FONT_FAMILY": "Segoe UI",
        "FONT_SIZE": "13px",
        "BORDER": "#EDE9FF"
    }
}

def load_palettes():
    """Load palettes.json, ensure default palettes exist and write file if missing keys."""
    try:
        pals = {}
        if os.path.isfile(PALETTES_PATH):
            with open(PALETTES_PATH, 'r', encoding='utf-8') as f:
                try:
                    pals = json.load(f) or {}
                except Exception:
                    pals = {}
        else:
            pals = {}
        # ensure defaults present
        changed = False
        for k, v in DEFAULT_PALETTES.items():
            if k not in pals:
                pals[k] = v
                changed = True
        if changed:
            try:
                with open(PALETTES_PATH, 'w', encoding='utf-8') as f:
                    json.dump(pals, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        return pals
    except Exception:
        return DEFAULT_PALETTES.copy()


def save_palette(name, palette_dict):
    """Guarda o actualiza una paleta en styles/palettes.json"""
    try:
        pals = load_palettes()
        if not isinstance(pals, dict):
            pals = {}
        pals[name] = palette_dict
        with open(PALETTES_PATH, 'w', encoding='utf-8') as f:
            json.dump(pals, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_palette(name):
    pals = load_palettes()
    return pals.get(name)


def _read_module_qss():
    parts = []
    if os.path.isdir(MODULES_QSS_DIR):
        for fn in sorted(os.listdir(MODULES_QSS_DIR)):
            if fn.lower().endswith('.qss'):
                path = os.path.join(MODULES_QSS_DIR, fn)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        parts.append(f.read())
                except Exception:
                    continue
    return '\n'.join(parts)


def build_qss(theme_name=None):
    """
    Backwards-compatible helper used by theme_editor when passing a merged palette dict:
    If theme_name is actually a dict (palette), use it directly.
    """
    # If caller passed a palette dict instead of name, delegate
    if isinstance(theme_name, dict):
        palette = theme_name
        # ensure defaults
        defaults = {'CARD_BG': '#FFFFFF', 'FONT_FAMILY': 'Segoe UI', 'FONT_SIZE': '13px', 'TEXT_COLOR': palette.get('TEXT', '#222222')}
        for dk, dv in defaults.items():
            if dk not in palette:
                palette[dk] = dv
        qss_template = _read_module_qss()
        for k, v in palette.items():
            qss_template = qss_template.replace('{' + k + '}', str(v))
        return qss_template

    """
    Construye el QSS final combinando todos los qss de styles/modules y reemplazando
    los placeholders {PRIMARY}, {BG}, etc. Si theme_name es None, intenta leer
    styles/active_theme.json y usar ese nombre.
    """
    if theme_name is None:
        try:
            with open(ACTIVE_THEME_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                theme_name = data.get('active')
        except Exception:
            theme_name = None

    palette = get_palette(theme_name) if theme_name else None
    if not palette:
        # pick first palette available as fallback
        pals = load_palettes()
        if isinstance(pals, dict) and pals:
            first = next(iter(pals.keys()))
            palette = pals.get(first)
        else:
            # default fallback
            palette = {
                'PRIMARY': '#6B4ED6', 'PRIMARY_DARK': '#5A3FC7', 'PRIMARY_LIGHT': '#8E6BE6',
                'BG': '#F8F6FF', 'SURFACE': '#FFFFFF', 'TEXT': '#222222', 'ACCENT': '#00C853',
                'BTN_BG': '#8E6BE6', 'BTN_HOVER': '#6B4ED6', 'BORDER': '#E8E3F5',
                'CARD_BG': '#FFFFFF', 'FONT_FAMILY': 'Segoe UI', 'FONT_SIZE': '13px', 'TEXT_COLOR': '#222222'
            }

    # ensure some default keys exist to avoid KeyError-like misses
    defaults = {
        'CARD_BG': '#FFFFFF',
        'FONT_FAMILY': 'Segoe UI',
        'FONT_SIZE': '13px',
        'TEXT_COLOR': palette.get('TEXT') if palette and palette.get('TEXT') else '#222222'
    }
    for dk, dv in defaults.items():
        if dk not in palette:
            palette[dk] = dv
    # sidebar token: allow independent sidebar color, fallback to PRIMARY
    if 'SIDEBAR' not in palette:
        palette['SIDEBAR'] = palette.get('PRIMARY', '#6B4ED6')

    qss_template = _read_module_qss()
    # global tokens mapping (allow missing keys)
    for k, v in palette.items():
        qss_template = qss_template.replace('{' + k + '}', str(v))
    return qss_template


def build_and_write_styles(theme_name=None):
    qss = build_qss(theme_name)
    # For application stylesheet, strip visual delineations (borders) so the running
    # app doesn't show boxed outlines used for preview or developer debugging.
    try:
        import re
        qss_app = re.sub(r'(?i)border-bottom\s*:[^;]+;', 'border-bottom: none;', qss)
        qss_app = re.sub(r'(?i)border\s*:[^;]+;', 'border: none;', qss_app)
    except Exception:
        qss_app = qss
    try:
        with open(OUTPUT_QSS, 'w', encoding='utf-8') as f:
            f.write(qss_app)
        return True
    except Exception:
        return False


def apply_theme(app, theme_name=None):
    qss = build_qss(theme_name)
    # When applying at runtime, ensure borders are removed to avoid showing
    # preview/delineation artifacts in the full app.
    try:
        import re
        qss_app = re.sub(r'(?i)border-bottom\s*:[^;]+;', 'border-bottom: none;', qss)
        qss_app = re.sub(r'(?i)border\s*:[^;]+;', 'border: none;', qss_app)
    except Exception:
        qss_app = qss
    try:
        app.setStyleSheet(qss_app)
        # persist active theme
        try:
            with open(ACTIVE_THEME_PATH, 'w', encoding='utf-8') as f:
                json.dump({'active': theme_name}, f)
        except Exception:
            pass
        return True
    except Exception:
        return False


def list_palettes():
    pals = load_palettes()
    return list(pals.keys())


if __name__ == '__main__':
    # simple test: build styles.qss
    build_and_write_styles()
