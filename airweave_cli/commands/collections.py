from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.config import get_http_client

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
    client = get_http_client()
    try:
        resp = client.get("/collections/")
        resp.raise_for_status()
        collections = resp.json()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(collections, indent=2, default=str))
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
            c.get("name", ""),
            c.get("readable_id", ""),
            c.get("status", "-"),
            (c.get("created_at") or "-")[:16],
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
    client = get_http_client()
    body: dict = {"name": name}
    if readable_id:
        body["readable_id"] = readable_id

    try:
        resp = client.post("/collections/", json=body)
        resp.raise_for_status()
        collection = resp.json()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(collection, indent=2, default=str))
        return

    stdout.print(
        f"[green]Created:[/green] {collection['name']} ({collection['readable_id']})"
    )


@app.command()
def get(
    readable_id: str = typer.Argument(..., help="Collection readable_id."),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Get details of a collection."""
    client = get_http_client()
    try:
        resp = client.get(f"/collections/{readable_id}")
        resp.raise_for_status()
        collection = resp.json()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(collection, indent=2, default=str))
        return

    stdout.print(f"[bold]{collection['name']}[/bold]  ({collection['readable_id']})")
    stdout.print(f"  ID:        {collection['id']}")
    stdout.print(f"  Status:    {collection.get('status', '-')}")
    stdout.print(f"  Vectors:   {collection.get('vector_size', '-')}d ({collection.get('embedding_model_name', '-')})")
    stdout.print(f"  Created:   {collection.get('created_at', '-')}")
    stdout.print(f"  Modified:  {collection.get('modified_at', '-')}")
