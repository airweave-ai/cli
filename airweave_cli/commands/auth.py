from __future__ import annotations

import json
import os
from enum import Enum

import typer
from rich.console import Console

from airweave_cli.config import (
    clear_config,
    load_config,
    save_config,
)

app = typer.Typer(name="auth", help="Manage authentication.", no_args_is_help=True)

stderr = Console(stderr=True)
stdout = Console()


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


@app.command()
def login() -> None:
    """Interactive login: save your API key to ~/.airweave/config.json."""
    api_key = typer.prompt("API key", hide_input=True)
    base_url = typer.prompt(
        "Base URL",
        default="https://api.airweave.ai",
        show_default=True,
    )
    collection = typer.prompt(
        "Default collection (readable_id)",
        default="",
        show_default=False,
    )

    # Validate the key
    try:
        from airweave import AirweaveSDK

        client = AirweaveSDK(api_key=api_key, base_url=base_url)
        client.collections.list(limit=1)
    except Exception as exc:
        stderr.print(f"[red]Authentication failed:[/red] {exc}")
        raise typer.Exit(code=1)

    cfg = load_config()
    cfg["api_key"] = api_key
    if base_url and base_url != "https://api.airweave.ai":
        cfg["base_url"] = base_url
    if collection:
        cfg["collection"] = collection
    save_config(cfg)

    stderr.print("[green]Logged in.[/green] Config saved to ~/.airweave/config.json")


@app.command()
def status(
    format: OutputFormat = typer.Option(
        OutputFormat.text, "--format", "-f", help="Output format."
    ),
) -> None:
    """Show current authentication state."""
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

    if format == OutputFormat.json:
        typer.echo(json.dumps(info, indent=2))
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
def logout() -> None:
    """Clear saved credentials from ~/.airweave/config.json."""
    clear_config()
    stderr.print("Logged out. Config cleared.")
