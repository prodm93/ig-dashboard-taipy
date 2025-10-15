from data.airtable_fetch import fetch_airtable_data
from data.config_loader import get_airtable_config
import pandas as pd

cfg = get_airtable_config()
base = cfg["bases"]["malugo_backend"]

# Fetch IG Account Metrics data
try:
    data = fetch_airtable_data(
        base_id=base["base_id"],
        table_name=base["tables"]["ig_account_metrics"]["name"],
        api_key=base["tables"]["ig_account_metrics"]["api_key"]
    )
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.sort_values("Date")
except Exception as e:
    print(f"⚠️ Airtable load failed: {e}")
    data = pd.DataFrame({
        "Date": ["2025-10-12", "2025-10-13"],
        "Reach": [1500, 1700],
        "Follower Count": [510, 525],
    })

layout = """
# 📊 Engagement Dashboard
<|{data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Follower Count|title=Reach & Followers|>
"""
