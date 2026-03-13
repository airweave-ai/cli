from __future__ import annotations

from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from airweave_cli.config import get_http_client, resolve_collection
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.spinner import with_spinner

stderr = Console(stderr=True)
stdout = Console()


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


def _render_results(response: Any) -> None:
    results = response.get("results", [])
    if not results:
        stderr.print("[yellow]No results found.[/yellow]")
        return

    completion = response.get("completion")
    if completion:
        stdout.print(Panel(Markdown(completion), title="Answer", border_style="green"))
        stdout.print()

    for i, result in enumerate(results, 1):
        meta = result.get("system_metadata") or {}
        source = meta.get("source_name") or result.get("source_name", "unknown")
        score = result.get("score")
        name = result.get("name", "")
        content = result.get("textual_representation") or result.get("md_content", "")
        source_fields = result.get("source_fields") or {}
        url = source_fields.get("web_url") or source_fields.get("url") or result.get("url")

        title_parts = [f"[bold]#{i}[/bold]  {source}"]
        if score is not None:
            title_parts.append(f"[dim]score={score:.3f}[/dim]")
        title = Text.from_markup("  ".join(title_parts))

        snippet = content[:500] + ("..." if len(content) > 500 else "") if content else ""
        body = Markdown(snippet) if snippet else Text.from_markup("[dim]no content[/dim]")

        subtitle = url or None
        if name and not snippet:
            body = Text(name)

        stdout.print(Panel(body, title=title, subtitle=subtitle, border_style="blue"))


def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query."),
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results to return."),
) -> None:
    """Search a collection. This is the core command.

    Examples:

        $ airweave search "how does auth work?"

        $ airweave search "deploy steps" --json | jq '.results[0]'
    """
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    coll = resolve_collection(collection)
    client = get_http_client()

    try:
        with with_spinner("Searching...", "Search complete", "Search failed", quiet=quiet):
            resp = client.post(
                f"/collections/{coll}/search",
                json={"query": query, "limit": top_k},
            )
            resp.raise_for_status()
            response = resp.json()
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(str(exc), code="search_error", json_flag=json_flag)

    if should_output_json(json_flag):
        output_result(response, json_flag=json_flag)
        return

    _render_results(response)
