# pages/engagement_dashboard.py
import pandas as pd
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all

ERROR = ""
df_accounts = pd.DataFrame()

try:
    cfg = get_airtable_config()          # <- returns a flat dict now
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]
    TABLE_ACCOUNTS = cfg["tables"]["ig_accounts"]   # "IG Account Metrics"
    # Pull data
    df_accounts = fetch_all(API_KEY, BASE_ID, TABLE_ACCOUNTS)
    if "Date" in df_accounts.columns:
        df_accounts["Date"] = pd.to_datetime(df_accounts["Date"])
        df_accounts = df_accounts.sort_values("Date")
except Exception as e:
    ERROR = f"⚠️ {e}. Check Airtable config/env."

layout = """
# 📊 Engagement Dashboard
<|{data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Follower Count|title=Reach & Followers|>
"""
