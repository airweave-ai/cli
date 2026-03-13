from __future__ import annotations

from typing import Any, Callable, Dict

import typer
from rich.console import Console

from airweave_cli.config import get_http_client
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.spinner import with_spinner

stderr = Console(stderr=True)


def _get_global_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


def run_get(
    ctx: typer.Context,
    *,
    endpoint: str,
    spinner_loading: str,
    spinner_success: str,
    spinner_fail: str,
    render: Callable[[Any], None],
) -> None:
    """GET *endpoint*, show a spinner, then render or output JSON."""
    opts = _get_global_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    client = get_http_client()
    try:
        with with_spinner(spinner_loading, spinner_success, spinner_fail, quiet=quiet):
            resp = client.get(endpoint)
            resp.raise_for_status()
            data = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="fetch_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(data, json_flag=json_flag)
    else:
        render(data)


def run_list(
    ctx: typer.Context,
    *,
    endpoint: str,
    spinner_loading: str,
    spinner_success: str,
    spinner_fail: str,
    render: Callable[[Any], None],
    empty_message: str = "No results found.",
) -> None:
    """GET *endpoint*, show a spinner, then render a table or output JSON."""
    opts = _get_global_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    client = get_http_client()
    try:
        with with_spinner(spinner_loading, spinner_success, spinner_fail, quiet=quiet):
            resp = client.get(endpoint)
            resp.raise_for_status()
            data = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="list_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(data, json_flag=json_flag)
        return

    if not data:
        stderr.print(f"[yellow]{empty_message}[/yellow]")
        return

    render(data)


def run_create(
    ctx: typer.Context,
    *,
    endpoint: str,
    body: Dict[str, Any],
    spinner_loading: str,
    spinner_success: str,
    spinner_fail: str,
    render: Callable[[Any], None],
) -> None:
    """POST *endpoint* with *body*, show a spinner, then render or output JSON."""
    opts = _get_global_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    client = get_http_client()
    try:
        with with_spinner(spinner_loading, spinner_success, spinner_fail, quiet=quiet):
            resp = client.post(endpoint, json=body)
            if resp.status_code >= 400:
                output_error(
                    f"({resp.status_code}) {resp.text}",
                    code="create_error",
                    json_flag=json_flag,
                )
            data = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="create_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(data, json_flag=json_flag)
    else:
        render(data)
