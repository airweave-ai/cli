from __future__ import annotations

import typer

from airweave_cli import __version__
from airweave_cli.commands.auth import app as auth_app
from airweave_cli.commands.collections import app as collections_app
from airweave_cli.commands.search import search
from airweave_cli.commands.sources import app as sources_app

app = typer.Typer(
    name="airweave",
    help="Airweave CLI — search across your connected sources.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog=(
        "[dim]Environment:[/dim]  AIRWEAVE_API_KEY · AIRWEAVE_BASE_URL · AIRWEAVE_COLLECTION\n\n"
        "[dim]Output:[/dim]  Human-friendly by default. JSON when piped or with --json."
    ),
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"airweave-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Force JSON output (default when stdout is piped).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress spinners and interactive output; implies --json.",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output or quiet
    ctx.obj["quiet"] = quiet


app.add_typer(auth_app, name="auth")
app.add_typer(collections_app, name="collections")
app.add_typer(sources_app, name="sources")
app.command()(search)


if __name__ == "__main__":
    app()
