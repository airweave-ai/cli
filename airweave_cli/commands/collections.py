from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.config import get_client, serialize

app = typer.Typer(name="collections", help="Manage collections.", no_args_is_help=True)

stderr = Console(stderr=True)
stdout = Console()


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


@app.command("list")
def list_collections(
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """List all collections."""
    client = get_client()
    try:
        collections = client.collections.list()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(collections), indent=2, default=str))
        return

    if not collections:
        stderr.print("[yellow]No collections found.[/yellow]")
        return

    table = Table(title="Collections")
    table.add_column("Name", style="bold")
    table.add_column("Readable ID")
    table.add_column("Status")
    table.add_column("Created")

    for c in collections:
        table.add_row(
            c.name,
            c.readable_id,
            str(c.status) if c.status else "-",
            c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "-",
        )

    stdout.print(table)


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Collection name."),
    readable_id: Optional[str] = typer.Option(
        None, "--readable-id", "-r", help="Custom readable ID (auto-generated if omitted)."
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Create a new collection."""
    client = get_client()
    kwargs = {"name": name}
    if readable_id:
        kwargs["readable_id"] = readable_id

    try:
        collection = client.collections.create(**kwargs)
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(collection), indent=2, default=str))
        return

    stdout.print(f"[green]Created:[/green] {collection.name} ({collection.readable_id})")


@app.command()
def get(
    readable_id: str = typer.Argument(..., help="Collection readable_id."),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Get details of a collection."""
    client = get_client()
    try:
        collection = client.collections.get(readable_id)
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(collection), indent=2, default=str))
        return

    stdout.print(f"[bold]{collection.name}[/bold]  ({collection.readable_id})")
    stdout.print(f"  ID:        {collection.id}")
    stdout.print(f"  Status:    {collection.status}")
    stdout.print(f"  Vectors:   {collection.vector_size}d ({collection.embedding_model_name})")
    stdout.print(f"  Created:   {collection.created_at}")
    stdout.print(f"  Modified:  {collection.modified_at}")
