# data/config_loader.py
import os, yaml

def get_airtable_config():
    with open("config/airtable_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    cfg_air = cfg.get("airtable", {})
    cfg_air["api_key"] = os.getenv("AIRTABLE_API_KEY", cfg_air.get("api_key"))
    cfg_air["base_id"] = os.getenv("AIRTABLE_BASE_ID", cfg_air.get("base_id"))
    tables = cfg_air.get("tables", {})
    tables["ig_posts"] = os.getenv("AIRTABLE_TABLE_POSTS", tables.get("ig_posts"))
    tables["ig_accounts"] = os.getenv("AIRTABLE_TABLE_ACCOUNTS", tables.get("ig_accounts"))
    cfg_air["tables"] = tables

    if not cfg_air.get("api_key"): raise ValueError("Missing AIRTABLE_API_KEY")
    if not cfg_air.get("base_id"): raise ValueError("Missing AIRTABLE_BASE_ID")
    return {"airtable": cfg_air}
