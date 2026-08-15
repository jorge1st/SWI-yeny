import os
import sys
import json

# Configuration loader for SWI application.
# Search order:
# 1) {commonappdata}\SWI\config.json (ProgramData)
# 2) <exe_dir>\config.json (portable install)
# 3) %APPDATA%\SWI\config.json
# 4) fallback defaults

def _config_paths():
    paths = []
    progdata = os.environ.get('PROGRAMDATA') or os.environ.get('ProgramData') or r'C:\ProgramData'
    paths.append(os.path.join(progdata, 'SWI', 'config.json'))
    try:
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'executable', None) else None
        if exe_dir:
            paths.append(os.path.join(exe_dir, 'config.json'))
    except Exception:
        pass
    paths.append(os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'SWI', 'config.json'))
    # user-level fallback
    paths.append(os.path.join(os.path.expanduser('~'), 'Documents', 'Registros', 'config.json'))
    return paths


def load_config():
    for p in _config_paths():
        if p and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                continue
    # defaults
    return {
        'pdf_base_dir': os.path.join(os.path.expanduser('~'), 'Documents', 'Registros'),
        'company_name': 'Minimarket ChiChi N-K, C.A',
        'company_rif': 'J-5099900-7'
    }

# singleton config loaded on import
_CONFIG = load_config()


def get(key, default=None):
    return _CONFIG.get(key, default)


def get_pdf_dir():
    return _CONFIG.get('pdf_base_dir', os.path.join(os.path.expanduser('~'), 'Documents', 'Registros'))


def get_company_name():
    return _CONFIG.get('company_name', 'Minimarket ChiChi N-K, C.A')


def get_company_rif():
    return _CONFIG.get('company_rif', 'J-5099900-7')


def reload_config():
    global _CONFIG
    _CONFIG = load_config()


