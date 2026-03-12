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
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"airweave-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    pass


app.add_typer(auth_app, name="auth")
app.add_typer(collections_app, name="collections")
app.add_typer(sources_app, name="sources")
app.command()(search)


if __name__ == "__main__":
    app()
