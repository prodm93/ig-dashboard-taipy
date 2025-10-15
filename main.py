import os
import pandas as pd
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_airtable_data

# Import layout strings from page modules
from pages import engagement_dashboard, content_efficiency_dashboard, semantics_dashboard

# Load data here in main.py so Taipy can access it
error_message = ""
data = pd.DataFrame(columns=["Date", "Reach", "Follower Count"])

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
    print(f"Error loading data: {e}")

# Define page routes
pages = {
    "/": engagement_dashboard.layout,
    "engagement": engagement_dashboard.layout,
    "efficiency": content_efficiency_dashboard.layout,
    "semantics": semantics_dashboard.layout,
}

# Launch the GUI
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    Gui(pages=pages).run(
        title="Malugo Dashboard", 
        host="0.0.0.0", 
        port=port
    )
