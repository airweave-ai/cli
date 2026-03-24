from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Optional

import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from airweave_cli.config import get_http_client, resolve_collection
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.spinner import with_spinner
from airweave_cli.lib.tty import is_interactive

stderr = Console(stderr=True)
stdout = Console()


class SearchMode(str, Enum):
    instant = "instant"
    classic = "classic"
    agentic = "agentic"


class RetrievalStrategy(str, Enum):
    hybrid = "hybrid"
    neural = "neural"
    keyword = "keyword"


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


def _parse_filter(filter_json: Optional[str]) -> Optional[list]:
    """Parse a JSON filter string into a list of filter groups."""
    if not filter_json:
        return None
    try:
        parsed = json.loads(filter_json)
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except json.JSONDecodeError as e:
        from airweave_cli.lib.output import output_error

        output_error(f"Invalid --filter JSON: {e}", code="invalid_filter")
        return None  # unreachable


def _build_request_body(
    mode: SearchMode,
    query: str,
    limit: int,
    offset: int,
    thinking: bool = False,
    retrieval_strategy: Optional[RetrievalStrategy] = None,
    filter_groups: Optional[list] = None,
) -> Dict[str, Any]:
    """Build the request body for the given search mode."""
    if mode == SearchMode.agentic:
        body: Dict[str, Any] = {"query": query, "thinking": thinking}
        if limit != 10:
            body["limit"] = limit
        if filter_groups:
            body["filter"] = filter_groups
        return body

    body: Dict[str, Any] = {"query": query, "limit": limit, "offset": offset}
    if mode == SearchMode.instant and retrieval_strategy:
        body["retrieval_strategy"] = retrieval_strategy.value
    if filter_groups:
        body["filter"] = filter_groups
    return body


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


def _render_stream_event(event: Dict[str, Any]) -> None:
    """Render a single SSE event to stderr during streaming."""
    event_type = event.get("type", "")
    duration = event.get("duration_ms")
    duration_str = f" [dim]({duration}ms)[/dim]" if duration else ""

    if event_type == "started":
        stderr.print(f"  [blue]▶[/blue] Search started{duration_str}")

    elif event_type == "thinking":
        text = event.get("text") or event.get("thinking") or ""
        diag = event.get("diagnostics") or {}
        iteration = diag.get("iteration", "?")
        snippet = text[:120].replace("\n", " ")
        if snippet:
            stderr.print(f"  [yellow]◆[/yellow] Thinking (iter {iteration}){duration_str}: {snippet}...")
        else:
            stderr.print(f"  [yellow]◆[/yellow] Thinking (iter {iteration}){duration_str}")

    elif event_type == "tool_call":
        tool = event.get("tool_name", "unknown")
        diag = event.get("diagnostics") or {}
        iteration = diag.get("iteration", "?")
        stderr.print(f"  [cyan]⚡[/cyan] Tool: {tool} (iter {iteration}){duration_str}")

    elif event_type == "reranking":
        diag = event.get("diagnostics") or {}
        in_count = diag.get("input_count", "?")
        out_count = diag.get("output_count", "?")
        stderr.print(f"  [magenta]⇅[/magenta] Reranking: {in_count} → {out_count} results{duration_str}")

    elif event_type == "error":
        msg = event.get("message", "Unknown error")
        stderr.print(f"  [red]✗[/red] Error: {msg}")

    elif event_type == "done":
        results = event.get("results") or []
        stderr.print(f"  [green]✔[/green] Done — {len(results)} results{duration_str}")


def _stream_agentic_search(
    client: httpx.Client,
    coll: str,
    body: Dict[str, Any],
    json_flag: bool,
    quiet: bool,
) -> None:
    """Execute agentic search via streaming SSE endpoint."""
    interactive = is_interactive() and not quiet

    with client.stream(
        "POST",
        f"/collections/{coll}/search/agentic/stream",
        json=body,
    ) as resp:
        resp.raise_for_status()

        results = []
        buffer = ""

        for chunk in resp.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                event_str, buffer = buffer.split("\n\n", 1)
                for line in event_str.split("\n"):
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type", "")

                        if interactive:
                            _render_stream_event(event)

                        if event_type == "done":
                            results = event.get("results") or []

                        if event_type == "error":
                            msg = event.get("message", "Search failed")
                            if not interactive:
                                output_error(msg, code="search_error", json_flag=json_flag)

    response = {"results": results}

    if should_output_json(json_flag):
        output_result(response, json_flag=json_flag)
        return

    if interactive:
        stdout.print()
    _render_results(response)


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
    thinking: bool = typer.Option(False, "--thinking", "-t", help="Enable extended thinking (agentic only)."),
    retrieval_strategy: Optional[RetrievalStrategy] = typer.Option(
        None, "--strategy", "-s", help="Retrieval strategy (instant only): hybrid, neural, keyword."
    ),
    filter_json: Optional[str] = typer.Option(
        None, "--filter", "-f", help='Filter as JSON, e.g. \'{"conditions": [{"field": "airweave_system_metadata.source_name", "operator": "equals", "value": "slack"}]}\'.'
    ),
) -> None:
    """Search a collection.

    Three search modes are available:

    - instant:  Direct vector search. Fastest, best for simple lookups.
    - classic:  AI-optimized search with LLM-generated search plans. (default)
    - agentic:  Full agent loop that iteratively searches and reasons.

    Examples:

        $ airweave search "how does auth work?"

        $ airweave search "deploy steps" --mode instant --strategy keyword

        $ airweave search "quarterly revenue" --mode agentic --thinking

        $ airweave search "bugs" --filter '{"conditions": [{"field": "airweave_system_metadata.source_name", "operator": "equals", "value": "jira"}]}'
    """
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    coll = resolve_collection(collection)
    client = get_http_client()

    filter_groups = _parse_filter(filter_json)
    body = _build_request_body(
        mode, query, top_k, offset,
        thinking=thinking,
        retrieval_strategy=retrieval_strategy,
        filter_groups=filter_groups,
    )

    # Agentic mode uses the streaming endpoint for real-time progress
    if mode == SearchMode.agentic:
        try:
            _stream_agentic_search(client, coll, body, json_flag, quiet)
        except typer.Exit:
            raise
        except Exception as exc:
            output_error(str(exc), code="search_error", json_flag=json_flag)
        return

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
