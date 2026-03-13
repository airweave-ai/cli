from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.config import get_http_client, resolve_collection

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
    client = get_http_client()

    body: dict = {
        "short_name": short_name,
        "readable_collection_id": coll,
        "sync_immediately": sync_immediately,
    }
    if name:
        body["name"] = name
    if credentials:
        try:
            creds = json.loads(credentials)
        except json.JSONDecodeError:
            stderr.print("[red]Error:[/red] --credentials must be valid JSON.")
            raise typer.Exit(code=1)
        body["authentication"] = {"type": "direct", "credentials": creds}
    if config:
        try:
            body["config"] = json.loads(config)
        except json.JSONDecodeError:
            stderr.print("[red]Error:[/red] --config must be valid JSON.")
            raise typer.Exit(code=1)

    try:
        resp = client.post("/source-connections/", json=body)
        if resp.status_code >= 400:
            stderr.print(f"[red]Error ({resp.status_code}):[/red] {resp.text}")
            raise typer.Exit(code=1)
        connection = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(connection, indent=2, default=str))
        return

    stdout.print(
        f"[green]Added:[/green] {connection.get('name', '')} ({connection.get('short_name', '')})"
    )
    stdout.print(f"  ID:     {connection.get('id', '')}")
    stdout.print(f"  Status: {connection.get('status', '')}")
    auth_url = connection.get("auth_url") or (connection.get("auth") or {}).get("auth_url")
    if auth_url:
        stdout.print(f"  Auth URL: {auth_url}")
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
    client = get_http_client()

    try:
        resp = client.get(f"/collections/{coll}/source-connections/")
        resp.raise_for_status()
        sources = resp.json()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(sources, indent=2, default=str))
        return

    if not sources:
        stderr.print("[yellow]No source connections found.[/yellow]")
        return

    table = Table(title="Source Connections")
    table.add_column("Name", style="bold")
    table.add_column("Source")
    table.add_column("ID")
    table.add_column("Status")

    for s in sources:
        table.add_row(
            s.get("name", ""),
            s.get("short_name", ""),
            s.get("id", ""),
            s.get("status", "-"),
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
    client = get_http_client()

    body: dict = {}
    if force:
        body["force_full_sync"] = True

    try:
        resp = client.post(f"/source-connections/{source_connection_id}/run", json=body)
        resp.raise_for_status()
        job = resp.json()
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(job, indent=2, default=str))
        return

    job_id = job.get("id", "")
    status = job.get("status", "")
    stdout.print(
        f"[green]Sync started.[/green]  Job ID: {job_id}"
        f"  Status: {status}"
    )
