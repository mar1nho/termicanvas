"""Always-on diagnostics: error capture and render time samples.

Passive module — no QTimer, no signal. Other code calls record_error() and
record_render_time() directly. Buffers are bounded deques; install_excepthooks
chains with any previously-installed hook.
"""

import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorRecord:
    timestamp: float
    source: str
    exc_type: str
    message: str
    stack: str


_errors: deque = deque(maxlen=200)
_render_times: deque = deque(maxlen=600)


def record_error(source: str, exc: BaseException, message: str = "") -> None:
    """Push an ErrorRecord into the global buffer.

    Called from `except Exception as e:` blocks throughout the app. Captures
    the current traceback via traceback.format_exc() (only valid inside an
    except handler — outside, falls back to a synthesized stack).
    """
    stack = traceback.format_exc()
    if stack.strip() == "NoneType: None":
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    rec = ErrorRecord(
        timestamp=time.time(),
        source=source,
        exc_type=type(exc).__name__,
        message=message or str(exc),
        stack=stack,
    )
    _errors.append(rec)


def record_render_time(ms: float) -> None:
    """Push a render time sample (in milliseconds) into the buffer."""
    _render_times.append(ms)


def iter_errors() -> list:
    """Snapshot list of current errors, oldest first."""
    return list(_errors)


def iter_render_times() -> list:
    """Snapshot list of current render times."""
    return list(_render_times)


def install_excepthooks() -> None:
    """Install global excepthook + threading.excepthook that record errors.

    Preserves any previously-installed hook by chaining (calls it after we
    record). Idempotent via attribute marker on the installed hook.
    """
    if getattr(sys.excepthook, "_termicanvas_installed", False):
        return

    previous_sys_hook = sys.excepthook

    def _our_excepthook(exc_type, exc_value, exc_tb):
        rec = ErrorRecord(
            timestamp=time.time(),
            source="excepthook",
            exc_type=exc_type.__name__ if exc_type else "Unknown",
            message=str(exc_value),
            stack="".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        _errors.append(rec)
        try:
            previous_sys_hook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    _our_excepthook._termicanvas_installed = True
    sys.excepthook = _our_excepthook

    previous_threading_hook = threading.excepthook

    def _our_threading_hook(args):
        rec = ErrorRecord(
            timestamp=time.time(),
            source=f"thread:{args.thread.name if args.thread else 'unknown'}",
            exc_type=args.exc_type.__name__,
            message=str(args.exc_value),
            stack="".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback
            )),
        )
        _errors.append(rec)
        try:
            previous_threading_hook(args)
        except Exception:
            pass

    _our_threading_hook._termicanvas_installed = True
    threading.excepthook = _our_threading_hook
