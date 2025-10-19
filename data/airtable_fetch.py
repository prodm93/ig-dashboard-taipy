from pyairtable import Api
import pandas as pd

def fetch_airtable_data(api_key: str, base_id: str, table_name: str):
    """Fetch all rows from an Airtable table using the modern pyairtable API."""
    api = Api(api_key)
    table = api.table(base_id, table_name)

    records = table.all()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r["fields"] for r in records])
    return df

def fetch_all_tables(api_key: str, base_id: str, tables: dict):
    """Fetch multiple tables and return as a dictionary of dataframes."""
    result = {}
    for key, table_name in tables.items():
        try:
            df = fetch_airtable_data(api_key, base_id, table_name)
            result[key] = df
        except Exception as e:
            print(f"Error fetching {table_name}: {e}")
            result[key] = pd.DataFrame()
    return result
