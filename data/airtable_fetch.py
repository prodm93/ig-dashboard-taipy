import requests
import pandas as pd

def fetch_airtable_data(base_id: str, table_name: str, api_key: str):
    """Fetch data from an Airtable table."""
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    records, offset = [], None
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
