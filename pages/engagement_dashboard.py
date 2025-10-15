# pages/engagement_dashboard.py
import pandas as pd
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_airtable_data

ERROR = ""
data = pd.DataFrame()  # ✅ Changed from df_accounts to data

try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]
    TABLE_ACCOUNTS = cfg["tables"]["ig_accounts"]
    
    # Pull data
    data = fetch_airtable_data(API_KEY, BASE_ID, TABLE_ACCOUNTS)  # ✅ Changed
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.sort_values("Date")
except Exception as e:
    ERROR = f"⚠️ {e}. Check Airtable config/env."

layout = """
# 📊 Engagement Dashboard
<|{data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Follower Count|title=Reach & Followers|>
"""
