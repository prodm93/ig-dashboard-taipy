# data/config_loader.py
from __future__ import annotations
import os, yaml
from pathlib import Path
from typing import Dict, Any

YAML_PATH = Path(__file__).resolve().parents[1] / "config" / "airtable_config.yaml"

def get_airtable_config() -> Dict[str, Any]:
    with YAML_PATH.open("r") as f:
        cfg = yaml.safe_load(f) or {}

    # Your YAML shape: bases -> <alias> -> base_id, tables -> {ig_posts_comments: {name: ...}, ...}
    bases = cfg.get("bases", {})
    alias = os.getenv("AIRTABLE_BASE_ALIAS", "malugo_backend")  # choose which base to use
    base_cfg = bases.get(alias, {})

    # Required creds (env wins)
    api_key = (os.getenv("AIRTABLE_API_KEY") or "").strip()
    base_id = (os.getenv("AIRTABLE_BASE_ID") or base_cfg.get("base_id") or "").strip()

    # Table names (env wins). Your keys: ig_posts_comments, ig_account_metrics -> each has {name: "..."}
    t_cfg = base_cfg.get("tables", {})
    tbl_posts = os.getenv("AIRTABLE_TABLE_POSTS", (t_cfg.get("ig_posts_comments") or {}).get("name", "")).strip()
    tbl_accounts = os.getenv("AIRTABLE_TABLE_ACCOUNTS", (t_cfg.get("ig_account_metrics") or {}).get("name", "")).strip()

    missing = []
    if not api_key:       missing.append("AIRTABLE_API_KEY")
    if not base_id:       missing.append("AIRTABLE_BASE_ID or bases.<alias>.base_id")
    if not tbl_posts:     missing.append("AIRTABLE_TABLE_POSTS or tables.ig_posts_comments.name")
    if not tbl_accounts:  missing.append("AIRTABLE_TABLE_ACCOUNTS or tables.ig_account_metrics.name")
    if missing:
        raise ValueError("Airtable config missing: " + ", ".join(missing))

    return {
        "api_key": api_key,
        "base_id": base_id,
        "tables": {
            "ig_posts": tbl_posts,
            "ig_accounts": tbl_accounts,
        },
        "alias": alias,
    }
