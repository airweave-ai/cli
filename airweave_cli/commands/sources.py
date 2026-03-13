from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.config import get_client, resolve_collection, serialize

app = typer.Typer(name="sources", help="Manage source connections.", no_args_is_help=True)

stderr = Console(stderr=True)
stdout = Console()


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


@app.command()
def add(
    short_name: str = typer.Argument(..., help="Source type (e.g. slack, github, notion)."),
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Display name."),
    credentials: Optional[str] = typer.Option(
        None,
        "--credentials",
        help='JSON credentials for direct auth (e.g. \'{"api_key": "..."}\')',
    ),
    config: Optional[str] = typer.Option(
        None, "--config", help="JSON config for the source.",
    ),
    sync_immediately: bool = typer.Option(
        True, "--sync/--no-sync", help="Start syncing immediately after creation.",
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Add a source connection to a collection."""
    coll = resolve_collection(collection)
    client = get_client()

    kwargs: dict = {
        "short_name": short_name,
        "readable_collection_id": coll,
        "sync_immediately": sync_immediately,
    }
    if name:
        kwargs["name"] = name
    if credentials:
        try:
            creds = json.loads(credentials)
        except json.JSONDecodeError:
            stderr.print("[red]Error:[/red] --credentials must be valid JSON.")
            raise typer.Exit(code=1)
        from airweave import DirectAuthentication

        kwargs["authentication"] = DirectAuthentication(credentials=creds)
    if config:
        try:
            kwargs["config"] = json.loads(config)
        except json.JSONDecodeError:
            stderr.print("[red]Error:[/red] --config must be valid JSON.")
            raise typer.Exit(code=1)

    try:
        connection = client.source_connections.create(**kwargs)
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(connection), indent=2, default=str))
        return

    stdout.print(f"[green]Added:[/green] {connection.name} ({connection.short_name})")
    stdout.print(f"  ID:     {connection.id}")
    stdout.print(f"  Status: {connection.status}")
    auth = getattr(connection, "auth", None)
    if auth and getattr(auth, "auth_url", None):
        stdout.print(f"  Auth URL: {auth.auth_url}")
        stdout.print("  Open this URL to complete OAuth authentication.")


@app.command("list")
def list_sources(
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """List source connections for a collection."""
    coll = resolve_collection(collection)
    client = get_client()

    try:
        sources = client.source_connections.list(collection=coll)
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(sources), indent=2, default=str))
        return

    if not sources:
        stderr.print("[yellow]No source connections found.[/yellow]")
        return

    table = Table(title="Source Connections")
    table.add_column("Name", style="bold")
    table.add_column("Source")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Entities")

    for s in sources:
        table.add_row(
            s.name,
            s.short_name,
            s.id,
            str(s.status) if s.status else "-",
            str(s.entity_count) if s.entity_count is not None else "-",
        )

    stdout.print(table)


@app.command()
def sync(
    source_connection_id: str = typer.Argument(..., help="Source connection ID (UUID)."),
    force: bool = typer.Option(
        False, "--force", help="Force a full re-sync instead of incremental."
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Trigger a sync for a source connection."""
    client = get_client()

    try:
        job = client.source_connections.run(
            source_connection_id,
            force_full_sync=force if force else None,
        )
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(job), indent=2, default=str))
        return

    stdout.print(f"[green]Sync started.[/green]  Job ID: {job.id}  Status: {job.status}")
