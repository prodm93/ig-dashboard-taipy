from __future__ import annotations
import os, yaml
from pathlib import Path
from typing import Dict, Any

def get_airtable_config() -> Dict[str, Any]:
    # Load YAML relative to repo root (works on Render & locally)
    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = repo_root / "config" / "airtable_config.yaml"

    with cfg_path.open("r") as f:
        cfg = yaml.safe_load(f) or {}

    air = cfg.get("airtable", {})
    tables = air.get("tables", {})

    # Required: API key & base id (env overrides YAML)
    api_key = os.getenv("AIRTABLE_API_KEY", air.get("api_key") or "").strip()
    base_id = os.getenv("AIRTABLE_BASE_ID", air.get("base_id") or "").strip()

    # Optional: table names (env overrides YAML if present)
    tables_out = {
        "ig_posts": os.getenv("AIRTABLE_TABLE_POSTS", tables.get("ig_posts", "")).strip(),
        "ig_accounts": os.getenv("AIRTABLE_TABLE_ACCOUNTS", tables.get("ig_accounts", "")).strip(),
    }

    # Validate the essentials
    missing = []
    if not api_key:  missing.append("AIRTABLE_API_KEY (or airtable.api_key in YAML)")
    if not base_id:  missing.append("AIRTABLE_BASE_ID (or airtable.base_id in YAML)")
    if not tables_out["ig_posts"]:    missing.append("tables.ig_posts (or AIRTABLE_TABLE_POSTS)")
    if not tables_out["ig_accounts"]: missing.append("tables.ig_accounts (or AIRTABLE_TABLE_ACCOUNTS)")
    if missing:
        raise ValueError("Airtable config missing: " + ", ".join(missing))

    return {
        "api_key": api_key,
        "base_id": base_id,
        "tables": tables_out,
    }
