from __future__ import annotations

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from airweave_cli.config import get_client, resolve_collection, serialize

stderr = Console(stderr=True)
stdout = Console()


class OutputFormat(str, Enum):
    json = "json"
    text = "text"


def search(
    query: str = typer.Argument(..., help="Search query."),
    collection: Optional[str] = typer.Option(
        None, "--collection", "-c", help="Collection readable_id."
    ),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results to return."),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format."
    ),
) -> None:
    """Search a collection. This is the core command.

    Pipe JSON output directly:  airweave search "query" | jq '.results[0]'
    """
    coll = resolve_collection(collection)
    client = get_client()

    try:
        from airweave import SearchRequest

        response = client.collections.search(
            coll,
            request=SearchRequest(query=query, limit=top_k),
        )
    except Exception as exc:
        stderr.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if format == OutputFormat.json:
        typer.echo(json.dumps(serialize(response), indent=2, default=str))
        return

    # Rich text output
    results = response.results
    if not results:
        stderr.print("[yellow]No results found.[/yellow]")
        raise typer.Exit(code=0)

    if response.completion:
        stdout.print(Panel(Markdown(response.completion), title="Answer", border_style="green"))
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
