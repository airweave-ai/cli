from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".airweave"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_BASE_URL = "https://api.airweave.ai"

AUTH0_CONFIGS = {
    "https://api.airweave.ai": {
        "domain": "airweave.us.auth0.com",
        "client_id": "HgVX5NneBER4VgGNQD0NKpyWBaPE2JMs",
        "audience": "https://app.airweave.ai/",
    },
}


def resolve_auth0_config(base_url: str) -> dict:
    """Resolve Auth0 configuration for a given API base URL.

    Checks AIRWEAVE_AUTH0_DOMAIN / _CLIENT_ID / _AUDIENCE env vars first,
    then falls back to the built-in mapping.
    """
    from airweave_cli.lib.output import output_error

    domain = os.environ.get("AIRWEAVE_AUTH0_DOMAIN")
    client_id = os.environ.get("AIRWEAVE_AUTH0_CLIENT_ID")
    audience = os.environ.get("AIRWEAVE_AUTH0_AUDIENCE")
    if domain and client_id and audience:
        return {"domain": domain, "client_id": client_id, "audience": audience}

    cfg = AUTH0_CONFIGS.get(base_url.rstrip("/"))
    if cfg and cfg["client_id"]:
        return cfg

    output_error(
        f"No Auth0 configuration for {base_url}. "
        "Use --api-key to log in with a key, or set AIRWEAVE_AUTH0_DOMAIN, "
        "AIRWEAVE_AUTH0_CLIENT_ID, and AIRWEAVE_AUTH0_AUDIENCE env vars.",
        code="no_auth0_config",
    )
    return {}


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


def resolve_api_key() -> str:
    from airweave_cli.lib.output import output_error

    key = os.environ.get("AIRWEAVE_API_KEY")
    if key:
        return key

    cfg = load_config()
    key = cfg.get("api_key")
    if key:
        return key

    output_error(
        "No API key found. Set AIRWEAVE_API_KEY or run: airweave auth login",
        code="no_api_key",
    )
    return ""  # unreachable


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
    from airweave_cli.lib.output import output_error

    if flag:
        return flag

    coll = os.environ.get("AIRWEAVE_COLLECTION")
    if coll:
        return coll

    cfg = load_config()
    coll = cfg.get("collection")
    if coll:
        return coll

    output_error(
        "No collection specified. Use --collection, set AIRWEAVE_COLLECTION, "
        "or run: airweave auth login",
        code="missing_collection",
    )
    return ""  # unreachable


def get_http_client():
    """Return an httpx client authenticated with the stored access token.

    Sends ``Authorization: Bearer <token>`` and ``X-Organization-ID`` headers
    on every request.  Falls back to ``X-API-Key`` when only an API key is
    available (env var or config).
    """
    import httpx

    from airweave_cli.lib.output import output_error

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
        output_error("No credentials found. Run: airweave auth login", code="no_credentials")

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
