import requests
import pandas as pd
import os

def fetch_airtable_data(base_id: str, table_name: str, api_key: str = None):
    """Fetches data from an Airtable table."""
    api_key = api_key or os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise ValueError("Missing Airtable API key")

    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {"Authorization": f"Bearer {api_key}"}

    records = []
    offset = None
    while True:
        params = {"offset": offset} if offset else {}
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return pd.DataFrame([rec["fields"] for rec in records])
