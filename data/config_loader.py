import os, yaml

def get_airtable_config():
    """Loads Airtable base and table configuration."""
    with open("config/airtable_config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    api_key = os.getenv("AIRTABLE_API_KEY")
    for base in cfg["bases"].values():
        for table in base["tables"].values():
            table["api_key"] = api_key
    return cfg
