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
