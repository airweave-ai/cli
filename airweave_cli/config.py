from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import typer

CONFIG_DIR = Path.home() / ".airweave"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_BASE_URL = "https://api.airweave.ai"


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    CONFIG_PATH.write_text(json.dumps(data, indent=2) + "\n")


def clear_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def _fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def resolve_api_key() -> str:
    key = os.environ.get("AIRWEAVE_API_KEY")
    if key:
        return key

    cfg = load_config()
    key = cfg.get("api_key")
    if key:
        return key

    _fail("No API key found. Set AIRWEAVE_API_KEY or run: airweave auth login")
    return ""  # unreachable, keeps type checkers happy


def resolve_base_url() -> str:
    url = os.environ.get("AIRWEAVE_BASE_URL")
    if url:
        return url

    cfg = load_config()
    url = cfg.get("base_url")
    if url:
        return url

    return DEFAULT_BASE_URL


def resolve_collection(flag: Optional[str] = None) -> str:
    if flag:
        return flag

    coll = os.environ.get("AIRWEAVE_COLLECTION")
    if coll:
        return coll

    cfg = load_config()
    coll = cfg.get("collection")
    if coll:
        return coll

    _fail(
        "No collection specified. Use --collection, set AIRWEAVE_COLLECTION, "
        "or run: airweave auth login"
    )
    return ""


def get_http_client():
    """Return an httpx client authenticated with the stored access token.

    Sends ``Authorization: Bearer <token>`` and ``X-Organization-ID`` headers
    on every request.  Falls back to ``X-API-Key`` when only an API key is
    available (env var or config).
    """
    import httpx

    cfg = load_config()
    base_url = resolve_base_url()

    token = cfg.get("access_token")
    org_id = cfg.get("organization_id")
    api_key = os.environ.get("AIRWEAVE_API_KEY") or cfg.get("api_key")

    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        if org_id:
            headers["X-Organization-ID"] = org_id
    elif api_key:
        headers["X-API-Key"] = api_key
    else:
        _fail("No credentials found. Run: airweave auth login")

    return httpx.Client(base_url=base_url, headers=headers, timeout=30)


def get_client():
    """Legacy helper — returns an AirweaveSDK client (requires an API key)."""
    from airweave import AirweaveSDK

    return AirweaveSDK(
        api_key=resolve_api_key(),
        base_url=resolve_base_url(),
    )


def serialize(obj: Any) -> Any:
    """Convert an SDK model (or list of models) to a JSON-serializable dict."""
    if isinstance(obj, list):
        return [serialize(item) for item in obj]
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj
