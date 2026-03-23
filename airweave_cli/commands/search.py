from __future__ import annotations

from enum import Enum
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


class SearchMode(str, Enum):
    instant = "instant"
    classic = "classic"
    agentic = "agentic"


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


def _build_request_body(
    mode: SearchMode,
    query: str,
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    """Build the request body for the given search mode."""
    if mode == SearchMode.agentic:
        body: Dict[str, Any] = {"query": query}
        if limit != 10:
            body["limit"] = limit
        return body

    return {"query": query, "limit": limit, "offset": offset}


def _render_results(response: Any) -> None:
    results = response.get("results", [])
    if not results:
        stderr.print("[yellow]No results found.[/yellow]")
        return

    for i, result in enumerate(results, 1):
        meta = result.get("airweave_system_metadata") or {}
        source = meta.get("source_name", "unknown")
        score = result.get("relevance_score")
        name = result.get("name", "")
        content = result.get("textual_representation", "")
        web_url = result.get("web_url")
        url = web_url or result.get("url")

        # Breadcrumb path
        breadcrumbs = result.get("breadcrumbs") or []
        if breadcrumbs:
            path = " > ".join(bc.get("name", "") for bc in breadcrumbs)
        else:
            path = ""

        title_parts = [f"[bold]#{i}[/bold]  {source}"]
        if score is not None:
            title_parts.append(f"[dim]score={score:.3f}[/dim]")
        title = Text.from_markup("  ".join(title_parts))

        # Build body: name header + breadcrumb path + content snippet
        body_parts = []
        if name:
            body_parts.append(f"**{name}**")
        if path:
            body_parts.append(f"_{path}_")
        if content:
            snippet = content[:500] + ("..." if len(content) > 500 else "")
            body_parts.append(snippet)

        if body_parts:
            body = Markdown("\n\n".join(body_parts))
        else:
            body = Text.from_markup("[dim]no content[/dim]")

        subtitle = url or None

        stdout.print(Panel(body, title=title, subtitle=subtitle, border_style="blue"))


def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query."),
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
    mode: SearchMode = typer.Option(
        SearchMode.classic, "--mode", "-m", help="Search mode: instant, classic, or agentic."
    ),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results to return."),
    offset: int = typer.Option(0, "--offset", help="Number of results to skip (instant/classic)."),
) -> None:
    """Search a collection.

    Three search modes are available:

    - instant:  Direct vector search. Fastest, best for simple lookups.
    - classic:  AI-optimized search with LLM-generated search plans. (default)
    - agentic:  Full agent loop that iteratively searches and reasons.

    Examples:

        $ airweave search "how does auth work?"

        $ airweave search "deploy steps" --mode instant --top-k 5

        $ airweave search "quarterly revenue" --mode agentic --json | jq '.results[0]'
    """
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    coll = resolve_collection(collection)
    client = get_http_client()

    body = _build_request_body(mode, query, top_k, offset)

    try:
        with with_spinner("Searching...", "Search complete", "Search failed", quiet=quiet):
            resp = client.post(
                f"/collections/{coll}/search/{mode.value}",
                json=body,
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
