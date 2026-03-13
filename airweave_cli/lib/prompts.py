from __future__ import annotations

from typing import Callable, Optional, Sequence, Tuple

import typer

from airweave_cli.lib.output import output_error
from airweave_cli.lib.tty import is_interactive


def require_text(
    value: Optional[str],
    *,
    prompt_msg: str,
    flag: str,
    json_flag: bool = False,
    hide_input: bool = False,
    validate: Optional[Callable[[str], Optional[str]]] = None,
) -> str:
    """Return *value* if provided, else prompt interactively, else error."""
    if value:
        return value

    if not is_interactive():
        output_error(f"Missing required flag --{flag}", code="missing_flag", json_flag=json_flag)

    import questionary

    result = questionary.text(
        prompt_msg,
        validate=validate or (lambda v: True if v.strip() else "This field is required"),
    ).ask()

    if result is None:
        raise typer.Exit(code=0)
    return result


def require_password(
    value: Optional[str],
    *,
    prompt_msg: str,
    flag: str,
    json_flag: bool = False,
) -> str:
    """Like require_text but masks input."""
    if value:
        return value

    if not is_interactive():
        output_error(f"Missing required flag --{flag}", code="missing_flag", json_flag=json_flag)

    import questionary

    result = questionary.password(prompt_msg).ask()
    if result is None:
        raise typer.Exit(code=0)
    return result


def require_select(
    value: Optional[str],
    *,
    options: Sequence[Tuple[str, str]],
    prompt_msg: str,
    flag: str,
    json_flag: bool = False,
) -> str:
    """Return *value* if provided, else show a select list, else error.

    *options* is a sequence of ``(value, label)`` tuples.
    """
    if value:
        return value

    if not is_interactive():
        output_error(f"Missing required flag --{flag}", code="missing_flag", json_flag=json_flag)

    import questionary

    choices = [questionary.Choice(title=label, value=val) for val, label in options]
    result = questionary.select(prompt_msg, choices=choices).ask()
    if result is None:
        raise typer.Exit(code=0)
    return result


def confirm_action(
    message: str,
    *,
    yes_flag: bool = False,
    json_flag: bool = False,
) -> None:
    """Ask for confirmation. Skips if *yes_flag* is True.

    In non-interactive mode without --yes, exits with an error.
    """
    if yes_flag:
        return

    if not is_interactive():
        output_error(
            "Use --yes to confirm in non-interactive mode.",
            code="confirmation_required",
            json_flag=json_flag,
        )

    import questionary

    confirmed = questionary.confirm(message, default=False).ask()
    if confirmed is None or not confirmed:
        raise typer.Exit(code=0)
