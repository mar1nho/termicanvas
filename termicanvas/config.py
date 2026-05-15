"""Constantes globais + paths e estado compartilhado."""

from pathlib import Path

DEFAULT_CWD = str(Path.cwd())

# Pastas em ~/.termicanvas (criadas em ensure_dirs())
TERMICANVAS_HOME = Path.home() / ".termicanvas"
ROLES_DIR        = TERMICANVAS_HOME / "roles"
SNAPSHOTS_DIR    = TERMICANVAS_HOME / "snapshots"
BUS_PORT_FILE    = TERMICANVAS_HOME / "bus.port"

# Sessao continua na raiz do projeto (compat com session.json existente)
SESSION_FILE = Path(__file__).resolve().parent.parent / "session.json"

_default_cwd = DEFAULT_CWD
_last_custom_cwd = None


def get_default_cwd():
    return _default_cwd


def set_default_cwd(path):
    global _default_cwd
    if path:
        _default_cwd = str(path)


def get_last_custom_cwd():
    return _last_custom_cwd


def set_last_custom_cwd(path):
    global _last_custom_cwd
    _last_custom_cwd = path


def ensure_dirs():
    """Cria estrutura ~/.termicanvas/ na primeira execucao. Idempotente."""
    TERMICANVAS_HOME.mkdir(parents=True, exist_ok=True)
    ROLES_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
