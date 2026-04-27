"""Snapshots — saves nomeados do canvas em ~/.termicanvas/snapshots/.

Cada snapshot e um JSON contendo a mesma serializacao que session.py produz
(nodes, connections, viewport, accent_color), mais metadados (nome de exibicao,
created_at, modified_at). NAO inclui bus_enabled — bus state e preferencia de
runtime, nao parte do layout.

API publica:
- list_snapshots() -> list[dict]: cada item tem name, file_name, node_count,
  modified_at; ordenado pelo mais recente.
- save_snapshot(display_name, canvas, accent_color): grava no disco.
- load_snapshot(file_name) -> dict | None: le do disco; retorna mesmo formato
  que load_session().
- delete_snapshot(file_name): apaga.
- rename_snapshot(old_file_name, new_display_name): regrava com novo nome.
- snapshot_exists(display_name) -> bool: chequeia colisao antes de salvar.

File names sao versoes sanitizadas do display_name (lowercase, sem espaco,
sem path traversal). O display_name "real" vive dentro do JSON.
"""

import json
import re
import time
from pathlib import Path

from .config import SNAPSHOTS_DIR, ensure_dirs
from .tokens import ACCENT


SCHEMA_VERSION = 1


def _sanitize_file_name(display_name: str) -> str:
    """Converte 'My Workflow #1' em 'my-workflow-1' para uso seguro como filename.

    Mantem so alfanumericos + hifen. Lowercase. Colapsa hifens duplicados.
    String vazia ou com so caractere invalido vira 'unnamed'.
    """
    s = (display_name or "").strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-_")
    return s or "unnamed"


def _path_for(file_name: str) -> Path:
    """Monta caminho seguro para um snapshot. file_name ja deve estar sanitizado."""
    safe = _sanitize_file_name(file_name)
    return SNAPSHOTS_DIR / f"{safe}.json"


def list_snapshots() -> list[dict]:
    """Lista snapshots ordenados do mais recente pro mais antigo.

    Cada entry: {"name", "file_name", "node_count", "modified_at"}.
    Snapshots corrompidos (JSON invalido) sao silenciosamente ignorados.
    """
    ensure_dirs()
    items = []
    for path in SNAPSHOTS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({
            "name":        data.get("name") or path.stem,
            "file_name":   path.stem,
            "node_count":  len(data.get("nodes", [])),
            "modified_at": data.get("modified_at") or path.stat().st_mtime,
        })
    items.sort(key=lambda d: d["modified_at"], reverse=True)
    return items


def snapshot_exists(display_name: str) -> bool:
    return _path_for(_sanitize_file_name(display_name)).exists()


def save_snapshot(display_name: str, canvas, accent_color: str = ACCENT) -> str:
    """Grava o estado atual do canvas como snapshot. Retorna o file_name usado.

    Sobrescreve se ja existir um snapshot com o mesmo nome sanitizado.
    """
    ensure_dirs()
    file_name = _sanitize_file_name(display_name)
    path = _path_for(file_name)
    now = time.time()

    # Importacao tardia evita ciclo entre snapshots <-> session.
    from .session import serialize_canvas
    nodes, connections = serialize_canvas(canvas)

    created_at = now
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            created_at = existing.get("created_at", now)
        except (OSError, json.JSONDecodeError):
            pass

    payload = {
        "version":      SCHEMA_VERSION,
        "name":         display_name,
        "file_name":    file_name,
        "created_at":   created_at,
        "modified_at":  now,
        "canvas": {
            "scale":        canvas.transform().m11(),
            "scroll_h":     canvas.horizontalScrollBar().value(),
            "scroll_v":     canvas.verticalScrollBar().value(),
            "accent_color": accent_color,
        },
        "nodes":       nodes,
        "connections": connections,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_name


def load_snapshot(file_name: str) -> dict | None:
    """Le um snapshot do disco. Retorna o dict completo ou None se nao existe/invalido."""
    path = _path_for(file_name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete_snapshot(file_name: str) -> bool:
    """Apaga um snapshot. Retorna True se removeu, False se nao existia."""
    path = _path_for(file_name)
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def rename_snapshot(old_file_name: str, new_display_name: str) -> str | None:
    """Renomeia um snapshot — regrava com novo display_name + filename sanitizado.

    Retorna o novo file_name, ou None se a operacao falhou.
    """
    data = load_snapshot(old_file_name)
    if data is None:
        return None
    new_file_name = _sanitize_file_name(new_display_name)
    if new_file_name == old_file_name:
        # Mesma chave fisica; so atualiza o display_name dentro do JSON.
        data["name"] = new_display_name
        data["modified_at"] = time.time()
        _path_for(new_file_name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        return new_file_name

    new_path = _path_for(new_file_name)
    if new_path.exists():
        # Colisao — chamador deve resolver antes (ex: pedir confirmacao).
        return None

    data["name"] = new_display_name
    data["file_name"] = new_file_name
    data["modified_at"] = time.time()
    new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    delete_snapshot(old_file_name)
    return new_file_name


