from pyairtable import Api
import pandas as pd

def fetch_airtable_data(base_id: str, table_name: str, api_key: str):
    """Fetch all rows from an Airtable table using the modern pyairtable API."""
    api = Api(api_key)
    table = api.table(base_id, table_name)

    records = table.all()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r["fields"] for r in records])
    return df
