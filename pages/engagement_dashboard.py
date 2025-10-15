# pages/engagement_dashboard.py
import pandas as pd
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_airtable_data

error_message = ""
data = pd.DataFrame()

try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]
    TABLE_ACCOUNTS = cfg["tables"]["ig_accounts"]
    
    # Pull data
    data = fetch_airtable_data(API_KEY, BASE_ID, TABLE_ACCOUNTS)
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.sort_values("Date")
except Exception as e:
    error_message = f"⚠️ {e}. Check Airtable config/env."
    # Create empty dataframe with expected columns
    data = pd.DataFrame(columns=["Date", "Reach", "Follower Count"])

layout = """
# 📊 Engagement Dashboard
<|{error_message}|text|>
<|{data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Follower Count|title=Reach & Followers|>
"""
