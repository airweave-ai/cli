from __future__ import annotations

from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.lib.actions import run_create, run_get, run_list

app = typer.Typer(
    name="collections",
    help="Manage collections.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

stdout = Console()


def _render_collections_table(collections: Any) -> None:
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


def _render_collection_detail(collection: Any) -> None:
    stdout.print(f"[bold]{collection['name']}[/bold]  ({collection['readable_id']})")
    stdout.print(f"  ID:        {collection['id']}")
    stdout.print(f"  Status:    {collection.get('status', '-')}")
    vector_size = collection.get("vector_size", "-")
    model_name = collection.get("embedding_model_name", "-")
    stdout.print(f"  Vectors:   {vector_size}d ({model_name})")
    stdout.print(f"  Created:   {collection.get('created_at', '-')}")
    stdout.print(f"  Modified:  {collection.get('modified_at', '-')}")


def _render_created(collection: Any) -> None:
    stdout.print(
        f"[green]Created:[/green] {collection['name']} ({collection['readable_id']})"
    )


@app.command("list")
def list_collections(ctx: typer.Context) -> None:
    """List all collections."""
    run_list(
        ctx,
        endpoint="/collections/",
        spinner_loading="Fetching collections...",
        spinner_success="Fetched collections",
        spinner_fail="Failed to fetch collections",
        render=_render_collections_table,
        empty_message="No collections found.",
    )


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Collection name."),
    readable_id: Optional[str] = typer.Option(
        None, "--readable-id", "-r", help="Custom readable ID (auto-generated if omitted)."
    ),
) -> None:
    """Create a new collection."""
    body: dict = {"name": name}
    if readable_id:
        body["readable_id"] = readable_id

    run_create(
        ctx,
        endpoint="/collections/",
        body=body,
        spinner_loading="Creating collection...",
        spinner_success="Collection created",
        spinner_fail="Failed to create collection",
        render=_render_created,
    )


@app.command()
def get(
    ctx: typer.Context,
    readable_id: str = typer.Argument(..., help="Collection readable_id."),
) -> None:
    """Get details of a collection."""
    run_get(
        ctx,
        endpoint=f"/collections/{readable_id}",
        spinner_loading="Fetching collection...",
        spinner_success="Fetched collection",
        spinner_fail="Failed to fetch collection",
        render=_render_collection_detail,
    )
