from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console

from airweave_cli.lib.tty import is_interactive

_stderr = Console(stderr=True)

TICK = "\u2714"  # ✔
CROSS = "\u2717"  # ✗


@contextmanager
def with_spinner(
    loading: str,
    success: str,
    fail: str,
    *,
    quiet: bool = False,
) -> Generator[None, None, None]:
    """Show a spinner while a block executes. No-op when non-interactive or quiet."""
    if quiet or not is_interactive():
        yield
        return

    with _stderr.status(f"  {loading}", spinner="dots"):
        try:
            yield
        except Exception:
            _stderr.print(f"  [red]{CROSS}[/red] {fail}")
            raise
    _stderr.print(f"  [green]{TICK}[/green] {success}")
