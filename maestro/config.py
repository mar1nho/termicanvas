"""Constantes globais + estado compartilhado (cwd padrao, arquivo de sessao)."""

from pathlib import Path

DEFAULT_CWD  = r"C:\Users\usuario\Documents\Vault\dattos-ia"
SESSION_FILE = Path(__file__).resolve().parent.parent / "session.json"

_last_custom_cwd = None


def get_last_custom_cwd():
    return _last_custom_cwd


def set_last_custom_cwd(path):
    global _last_custom_cwd
    _last_custom_cwd = path
