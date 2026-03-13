from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

import typer
from rich.console import Console

stderr = Console(stderr=True)


def should_output_json(json_flag: bool = False) -> bool:
    """True when output should be machine-readable JSON."""
    if json_flag:
        return True
    if not sys.stdout.isatty():
        return True
    return False


def output_result(data: Any, *, json_flag: bool = False) -> None:
    """Print *data* as indented JSON to stdout."""
    typer.echo(json.dumps(data, indent=2, default=str))


def output_error(message: str, *, code: str = "unknown", json_flag: bool = False) -> NoReturn:
    """Print an error and exit 1.

    JSON mode: ``{"error": {"message": "...", "code": "..."}}`` to stderr.
    Interactive: ``Error: ...`` with red styling to stderr.
    """
    if should_output_json(json_flag):
        sys.stderr.write(
            json.dumps({"error": {"message": message, "code": code}}, indent=2) + "\n"
        )
    else:
        stderr.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=1)
