from __future__ import annotations

import json
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from airweave_cli.config import get_http_client
from airweave_cli.lib.actions import run_list
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.prompts import require_select
from airweave_cli.lib.spinner import with_spinner
from airweave_cli.lib.tty import is_interactive

app = typer.Typer(
    name="sources",
    help="Manage source connections.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

stderr = Console(stderr=True)
stdout = Console()


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


def _resolve_collection_interactive(
    flag: Optional[str],
    *,
    json_flag: bool = False,
) -> str:
    """Resolve collection: flag > env > config > interactive picker > error."""
    import os

    from airweave_cli.config import load_config

    if flag:
        return flag

    env = os.environ.get("AIRWEAVE_COLLECTION")
    if env:
        return env

    cfg = load_config()
    cfg_coll = cfg.get("collection")
    if cfg_coll:
        return cfg_coll

    if not is_interactive():
        output_error(
            "No collection specified. Use --collection, set AIRWEAVE_COLLECTION, "
            "or run: airweave auth login",
            code="missing_collection",
            json_flag=json_flag,
        )

    try:
        client = get_http_client()
        resp = client.get("/collections/")
        resp.raise_for_status()
        collections = resp.json()
    except Exception:
        output_error(
            "No collection specified and could not fetch collection list. "
            "Use --collection or set AIRWEAVE_COLLECTION.",
            code="missing_collection",
            json_flag=json_flag,
        )

    if not collections:
        output_error(
            "No collections found. Create one first: airweave collections create --name <name>",
            code="no_collections",
            json_flag=json_flag,
        )

    options = [
        (c.get("readable_id", ""), f"{c.get('name', '')} ({c.get('readable_id', '')})")
        for c in collections
    ]

    return require_select(
        None,
        options=options,
        prompt_msg="Which collection?",
        flag="collection",
        json_flag=json_flag,
    )


def _render_sources_table(sources: Any) -> None:
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
def add(
    ctx: typer.Context,
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
) -> None:
    """Add a source connection to a collection."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    coll = _resolve_collection_interactive(collection, json_flag=json_flag)
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
            output_error(
                "--credentials must be valid JSON.", code="invalid_json", json_flag=json_flag
            )
        body["authentication"] = {"type": "direct", "credentials": creds}
    if config:
        try:
            body["config"] = json.loads(config)
        except json.JSONDecodeError:
            output_error("--config must be valid JSON.", code="invalid_json", json_flag=json_flag)

    try:
        with with_spinner("Adding source...", "Source added", "Failed to add source", quiet=quiet):
            resp = client.post("/source-connections/", json=body)
            if resp.status_code >= 400:
                output_error(
                    f"({resp.status_code}) {resp.text}",
                    code="create_error",
                    json_flag=json_flag,
                )
            connection = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="create_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(connection, json_flag=json_flag)
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
    ctx: typer.Context,
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
) -> None:
    """List source connections for a collection."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    coll = _resolve_collection_interactive(collection, json_flag=json_flag)

    run_list(
        ctx,
        endpoint=f"/collections/{coll}/source-connections/",
        spinner_loading="Fetching sources...",
        spinner_success="Fetched sources",
        spinner_fail="Failed to fetch sources",
        render=_render_sources_table,
        empty_message="No source connections found.",
    )


@app.command()
def sync(
    ctx: typer.Context,
    source_connection_id: str = typer.Argument(..., help="Source connection ID (UUID)."),
    force: bool = typer.Option(
        False, "--force", help="Force a full re-sync instead of incremental."
    ),
) -> None:
    """Trigger a sync for a source connection."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    client = get_http_client()
    body: dict = {}
    if force:
        body["force_full_sync"] = True

    try:
        with with_spinner(
            "Starting sync...", "Sync started", "Failed to start sync", quiet=quiet
        ):
            resp = client.post(f"/source-connections/{source_connection_id}/run", json=body)
            resp.raise_for_status()
            job = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="sync_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(job, json_flag=json_flag)
        return

    job_id = job.get("id", "")
    status = job.get("status", "")
    stdout.print(f"[green]Sync started.[/green]  Job ID: {job_id}  Status: {status}")
