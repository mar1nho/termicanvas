"""Constantes globais + paths e estado compartilhado."""

from pathlib import Path

DEFAULT_CWD  = r"C:\Users\usuario\Documents\Vault\dattos-ia"

# Pastas em ~/.termicanvas (criadas em ensure_dirs())
TERMICANVAS_HOME = Path.home() / ".termicanvas"
ROLES_DIR        = TERMICANVAS_HOME / "roles"
BUS_PORT_FILE    = TERMICANVAS_HOME / "bus.port"

# Sessao continua na raiz do projeto (compat com session.json existente)
SESSION_FILE = Path(__file__).resolve().parent.parent / "session.json"

_last_custom_cwd = None


def get_last_custom_cwd():
    return _last_custom_cwd


def set_last_custom_cwd(path):
    global _last_custom_cwd
    _last_custom_cwd = path


def ensure_dirs():
    """Cria estrutura ~/.termicanvas/ na primeira execucao. Idempotente."""
    TERMICANVAS_HOME.mkdir(parents=True, exist_ok=True)
    ROLES_DIR.mkdir(parents=True, exist_ok=True)
