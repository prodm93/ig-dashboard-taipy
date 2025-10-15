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

# Create a beautiful root page with navigation
root_page = """
<|layout|columns=250px 1fr|
<|part|class_name=sidebar|
# 📊 Malugo Analytics

## Dashboards

[📈 Engagement](Engagement_Dashboard)

[⚙️ Content Efficiency](Content_Efficiency)

[💬 Semantics & Sentiment](Semantics_Sentiment)
|>

<|part|class_name=content|
<|content|>
|part|>
|>
"""

# Define page routes
pages = {
    "/": root_page,
    "Engagement_Dashboard": engagement_dashboard.layout,
    "Content_Efficiency": content_efficiency_dashboard.layout,
    "Semantics_Sentiment": semantics_dashboard.layout,
}

# Launch the GUI
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    Gui(pages=pages, css_file="style.css").run(
        title="Malugo Analytics ✨", 
        host="0.0.0.0", 
        port=port,
        dark_mode=True
    )
