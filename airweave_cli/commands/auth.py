from __future__ import annotations

import os
from typing import Any, Dict

import typer
from rich.console import Console

from airweave_cli.config import clear_config, load_config, save_config
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.prompts import confirm_action, require_password, require_text
from airweave_cli.lib.spinner import with_spinner

app = typer.Typer(
    name="auth",
    help="Manage authentication.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

stderr = Console(stderr=True)
stdout = Console()


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


@app.command()
def login(ctx: typer.Context) -> None:
    """Interactive login: save your API key to ~/.airweave/config.json."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    api_key = require_password(
        None, prompt_msg="Enter your API key:", flag="api-key", json_flag=json_flag
    )
    base_url = require_text(
        None,
        prompt_msg="Base URL (leave empty for https://api.airweave.ai):",
        flag="base-url",
        json_flag=json_flag,
        validate=lambda v: True,
    )
    if not base_url.strip():
        base_url = "https://api.airweave.ai"

    collection = require_text(
        None,
        prompt_msg="Default collection readable_id (optional, press enter to skip):",
        flag="collection",
        json_flag=json_flag,
        validate=lambda v: True,
    )

    try:
        with with_spinner(
            "Validating credentials...",
            "Credentials valid",
            "Authentication failed",
            quiet=quiet,
        ):
            from airweave import AirweaveSDK

            client = AirweaveSDK(api_key=api_key, base_url=base_url)
            client.collections.list(limit=1)
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(f"Authentication failed: {exc}", code="auth_failed", json_flag=json_flag)

    cfg = load_config()
    cfg["api_key"] = api_key
    if base_url and base_url != "https://api.airweave.ai":
        cfg["base_url"] = base_url
    if collection and collection.strip():
        cfg["collection"] = collection.strip()
    save_config(cfg)

    stderr.print("  [green]\u2714[/green] Config saved to ~/.airweave/config.json")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show current authentication state."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)

    env_key = os.environ.get("AIRWEAVE_API_KEY")
    cfg = load_config()

    info = {
        "api_key_source": "env" if env_key else ("config" if cfg.get("api_key") else "none"),
        "api_key_set": bool(env_key or cfg.get("api_key")),
        "base_url": os.environ.get("AIRWEAVE_BASE_URL")
        or cfg.get("base_url", "https://api.airweave.ai"),
        "base_url_source": "env"
        if os.environ.get("AIRWEAVE_BASE_URL")
        else ("config" if cfg.get("base_url") else "default"),
        "collection": os.environ.get("AIRWEAVE_COLLECTION") or cfg.get("collection"),
        "collection_source": "env"
        if os.environ.get("AIRWEAVE_COLLECTION")
        else ("config" if cfg.get("collection") else "none"),
    }

    if should_output_json(json_flag):
        output_result(info, json_flag=json_flag)
        return

    stdout.print()
    key_display = "****" if info["api_key_set"] else "[red]not set[/red]"
    stdout.print(f"  API key:     {key_display}  [dim]({info['api_key_source']})[/dim]")
    stdout.print(f"  Base URL:    {info['base_url']}  [dim]({info['base_url_source']})[/dim]")
    coll_display = info["collection"] or "[red]not set[/red]"
    coll_source = f"  [dim]({info['collection_source']})[/dim]" if info["collection"] else ""
    stdout.print(f"  Collection:  {coll_display}{coll_source}")
    stdout.print()


@app.command()
def logout(ctx: typer.Context) -> None:
    """Clear saved credentials from ~/.airweave/config.json."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)

    confirm_action("Are you sure you want to log out?", json_flag=json_flag)

    clear_config()
    stderr.print("  Logged out. Config cleared.")
