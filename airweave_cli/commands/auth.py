from __future__ import annotations

import base64
import json
import os
import time
import webbrowser
from typing import Any, Dict, List, Optional

import httpx
import typer
from rich.console import Console

from airweave_cli.config import (
    clear_config,
    load_config,
    resolve_auth0_config,
    resolve_base_url,
    save_config,
)
from airweave_cli.lib.output import output_error, output_result, should_output_json
from airweave_cli.lib.prompts import confirm_action, require_password, require_text
from airweave_cli.lib.spinner import with_spinner

app = typer.Typer(
    name="auth",
    help="Manage authentication.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

stderr = Console(stderr=True)
stdout = Console()


def _get_opts(ctx: typer.Context) -> Dict[str, Any]:
    return ctx.ensure_object(dict)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _extract_jwt_claims(token: str) -> Dict[str, Any]:
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def _email_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    for key in claims:
        if key.endswith("/email"):
            return claims[key]
    return claims.get("email")


def _bearer(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Device Code flow
# ---------------------------------------------------------------------------


def _device_code_flow(base_url: str, *, quiet: bool = False) -> str:
    """Run Auth0 Device Code grant. Returns the access token."""
    auth0 = resolve_auth0_config(base_url)

    with httpx.Client(timeout=30) as http:
        resp = http.post(
            f"https://{auth0['domain']}/oauth/device/code",
            data={
                "client_id": auth0["client_id"],
                "scope": "openid email",
                "audience": auth0["audience"],
            },
        )
        resp.raise_for_status()
        device = resp.json()

    user_code = device["user_code"]
    verification_url = device["verification_uri_complete"]
    device_code = device["device_code"]
    interval = device.get("interval", 5)
    expires_in = device.get("expires_in", 900)

    if not quiet:
        stderr.print()
        stderr.print(f"  Open this URL to sign in:\n")
        stderr.print(f"    [bold cyan]{verification_url}[/bold cyan]\n")
        stderr.print(f"  Your code: [bold]{user_code}[/bold]\n")

    try:
        webbrowser.open(verification_url)
    except Exception:
        pass

    if not quiet:
        stderr.print("  Waiting for authentication…", end="")

    deadline = time.monotonic() + expires_in
    access_token: Optional[str] = None

    with httpx.Client(timeout=30) as http:
        while time.monotonic() < deadline:
            time.sleep(interval)
            resp = http.post(
                f"https://{auth0['domain']}/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": auth0["client_id"],
                },
            )
            body = resp.json()

            if resp.status_code == 200:
                access_token = body["access_token"]
                break

            error = body.get("error")
            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                interval += 1
                continue
            elif error == "expired_token":
                stderr.print("\n")
                output_error("Authentication timed out.", code="auth_timeout")
            elif error == "access_denied":
                stderr.print("\n")
                output_error("Authentication was denied.", code="auth_denied")
            else:
                stderr.print("\n")
                output_error(f"Unexpected error: {error}", code="auth_error")

    if not access_token:
        stderr.print("\n")
        output_error("Authentication timed out.", code="auth_timeout")

    if not quiet:
        stderr.print(" done!")

    return access_token  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# User / Organization helpers
# ---------------------------------------------------------------------------


def _ensure_user(base_url: str, token: str, email: str) -> None:
    with httpx.Client(timeout=120) as http:
        http.post(
            f"{base_url.rstrip('/')}/users/create_or_update",
            headers=_bearer(token),
            json={"email": email},
        )


def _list_organizations(base_url: str, token: str, email: str) -> List[Dict[str, Any]]:
    with httpx.Client(timeout=30) as http:
        resp = http.get(
            f"{base_url.rstrip('/')}/organizations/",
            headers=_bearer(token),
        )

    if resp.status_code == 401 and email:
        _ensure_user(base_url, token, email)
        with httpx.Client(timeout=30) as http:
            resp = http.get(
                f"{base_url.rstrip('/')}/organizations/",
                headers=_bearer(token),
            )

    if resp.status_code != 200:
        output_error(
            f"Failed to list organizations ({resp.status_code}): {resp.text}",
            code="org_list_failed",
        )
    return resp.json()


def _create_organization(base_url: str, token: str, name: str) -> Dict[str, Any]:
    with httpx.Client(timeout=30) as http:
        resp = http.post(
            f"{base_url.rstrip('/')}/organizations/",
            headers=_bearer(token),
            json={"name": name},
        )
    if resp.status_code not in (200, 201):
        output_error(
            f"Failed to create organization ({resp.status_code}): {resp.text}",
            code="org_create_failed",
        )
    return resp.json()


def _select_or_create_org(
    base_url: str, token: str, email: str, *, json_flag: bool = False
) -> Dict[str, Any]:
    orgs = _list_organizations(base_url, token, email)

    if orgs:
        if len(orgs) == 1:
            stderr.print(f"\n  Auto-selected [bold]{orgs[0]['name']}[/bold] (only organization).\n")
            return orgs[0]

        stderr.print()
        stderr.print("  [bold]Select an organization:[/bold]\n")
        for i, org in enumerate(orgs, 1):
            role = org.get("role", "")
            stderr.print(f"    {i}. {org['name']}  [dim]({role})[/dim]")
        stderr.print()

        raw = typer.prompt("  Choice", default="1")
        try:
            choice = int(raw)
            if choice < 1 or choice > len(orgs):
                raise ValueError
        except ValueError:
            output_error("Invalid choice.", code="invalid_choice", json_flag=json_flag)

        selected = orgs[choice - 1]
        stderr.print(f"  Organization set to [bold]{selected['name']}[/bold].\n")
        return selected

    stderr.print()
    stderr.print("  No organizations found. Let's create one.\n")
    name = require_text(None, prompt_msg="Organization name:", flag="org-name", json_flag=json_flag)
    org = _create_organization(base_url, token, name)
    stderr.print(f"\n  Created organization [bold]{org['name']}[/bold].\n")
    return org


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def login(
    ctx: typer.Context,
    api_key: bool = typer.Option(
        False, "--api-key", help="Paste an API key manually instead of browser login."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Airweave API base URL."
    ),
    collection: Optional[str] = typer.Option(
        None, "--collection", help="Default collection (readable_id)."
    ),
) -> None:
    """Log in to Airweave.

    Opens a browser for sign-in by default (Auth0 Device Code flow).
    Use --api-key to paste a key manually instead.
    """
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)
    quiet = opts.get("quiet", False)

    effective_url = base_url or resolve_base_url()

    if api_key:
        _login_with_api_key(effective_url, collection, json_flag=json_flag, quiet=quiet)
    else:
        _login_with_browser(effective_url, collection, json_flag=json_flag, quiet=quiet)


def _login_with_browser(
    base_url: str,
    collection: Optional[str],
    *,
    json_flag: bool = False,
    quiet: bool = False,
) -> None:
    token = _device_code_flow(base_url, quiet=quiet)
    claims = _extract_jwt_claims(token)
    email = _email_from_claims(claims) or ""

    if email and not quiet:
        stderr.print(f"  Logged in as [bold]{email}[/bold].")

    org = _select_or_create_org(base_url, token, email, json_flag=json_flag)

    cfg = load_config()
    cfg["access_token"] = token
    cfg["organization_id"] = str(org["id"])
    if base_url != "https://api.airweave.ai":
        cfg["base_url"] = base_url
    if collection:
        cfg["collection"] = collection
    cfg.pop("api_key", None)
    save_config(cfg)

    if not quiet:
        stderr.print("  [green]✔[/green] Config saved to ~/.airweave/config.json")


def _login_with_api_key(
    base_url: str,
    collection: Optional[str],
    *,
    json_flag: bool = False,
    quiet: bool = False,
) -> None:
    key = require_password(
        None, prompt_msg="Enter your API key:", flag="api-key", json_flag=json_flag
    )
    url = require_text(
        None,
        prompt_msg=f"Base URL (leave empty for {base_url}):",
        flag="base-url",
        json_flag=json_flag,
        validate=lambda v: True,
    )
    if not url.strip():
        url = base_url

    coll = collection or require_text(
        None,
        prompt_msg="Default collection readable_id (optional, press enter to skip):",
        flag="collection",
        json_flag=json_flag,
        validate=lambda v: True,
    )

    try:
        with with_spinner(
            "Validating credentials...",
            "Credentials valid",
            "Authentication failed",
            quiet=quiet,
        ):
            from airweave import AirweaveSDK

            client = AirweaveSDK(api_key=key, base_url=url)
            client.collections.list(limit=1)
    except typer.Exit:
        raise
    except Exception as exc:
        output_error(f"Authentication failed: {exc}", code="auth_failed", json_flag=json_flag)

    cfg = load_config()
    cfg["api_key"] = key
    if url and url != "https://api.airweave.ai":
        cfg["base_url"] = url
    if coll and coll.strip():
        cfg["collection"] = coll.strip()
    save_config(cfg)

    if not quiet:
        stderr.print("  [green]✔[/green] Config saved to ~/.airweave/config.json")


@app.command()
def status(ctx: typer.Context) -> None:
    """Show current authentication state."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)

    env_key = os.environ.get("AIRWEAVE_API_KEY")
    cfg = load_config()

    has_token = bool(cfg.get("access_token"))
    email = None
    if has_token:
        claims = _extract_jwt_claims(cfg["access_token"])
        email = _email_from_claims(claims)

    if has_token:
        auth_source = "token"
    elif env_key:
        auth_source = "env (API key)"
    elif cfg.get("api_key"):
        auth_source = "config (API key)"
    else:
        auth_source = "none"

    info = {
        "authenticated": has_token or bool(env_key) or bool(cfg.get("api_key")),
        "auth_source": auth_source,
        "email": email,
        "organization_id": cfg.get("organization_id"),
        "base_url": os.environ.get("AIRWEAVE_BASE_URL")
        or cfg.get("base_url", "https://api.airweave.ai"),
        "base_url_source": "env"
        if os.environ.get("AIRWEAVE_BASE_URL")
        else ("config" if cfg.get("base_url") else "default"),
        "collection": os.environ.get("AIRWEAVE_COLLECTION") or cfg.get("collection"),
        "collection_source": "env"
        if os.environ.get("AIRWEAVE_COLLECTION")
        else ("config" if cfg.get("collection") else "none"),
    }

    if should_output_json(json_flag):
        output_result(info, json_flag=json_flag)
        return

    stdout.print()
    if info["authenticated"]:
        stdout.print(f"  Auth:        [green]authenticated[/green]  [dim]({auth_source})[/dim]")
    else:
        stdout.print("  Auth:        [red]not authenticated[/red]")
    if email:
        stdout.print(f"  Email:       {email}")
    org_display = info["organization_id"] or "[red]not set[/red]"
    stdout.print(f"  Org ID:      {org_display}")
    stdout.print(f"  Base URL:    {info['base_url']}  [dim]({info['base_url_source']})[/dim]")
    coll_display = info["collection"] or "[red]not set[/red]"
    coll_source = f"  [dim]({info['collection_source']})[/dim]" if info["collection"] else ""
    stdout.print(f"  Collection:  {coll_display}{coll_source}")
    stdout.print()


@app.command()
def logout(ctx: typer.Context) -> None:
    """Clear saved credentials from ~/.airweave/config.json."""
    opts = _get_opts(ctx)
    json_flag = opts.get("json", False)

    confirm_action("Are you sure you want to log out?", json_flag=json_flag)

    clear_config()
    stderr.print("  Logged out. Config cleared.")
