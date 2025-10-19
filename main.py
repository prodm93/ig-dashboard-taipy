import os
import pandas as pd
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables

# Import layout strings from page modules
from pages import engagement_dashboard, content_efficiency_dashboard, semantics_dashboard

# Initialize variables
error_message = ""
account_data = pd.DataFrame(columns=["Date", "Reach", "Lifetime Follower Count", "Online Followers"])
posts_data = pd.DataFrame(columns=["Post ID", "Likes Count", "Reach", "Saves", "Timestamp"])

# For post selector
selected_post = ""
post_options = []

try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]
    
    # Fetch both tables
    all_data = fetch_all_tables(API_KEY, BASE_ID, cfg["tables"])
    
    # Account metrics
    account_data = all_data.get("ig_accounts", pd.DataFrame())
    if not account_data.empty and "Date" in account_data.columns:
        account_data["Date"] = pd.to_datetime(account_data["Date"])
        account_data = account_data.sort_values("Date")
    
    # Posts data
    posts_data = all_data.get("ig_posts", pd.DataFrame())
    if not posts_data.empty:
        if "Timestamp" in posts_data.columns:
            posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"])
            posts_data = posts_data.sort_values("Timestamp", ascending=False)
        
        # Create post options for selector
        if "Post ID" in posts_data.columns:
            post_options = posts_data["Post ID"].tolist()
            selected_post = post_options[0] if post_options else ""
        
        # Add engagement rate calculation
        if "Likes Count" in posts_data.columns and "Reach" in posts_data.columns:
            posts_data["Engagement Rate"] = (
                (posts_data["Likes Count"] + posts_data.get("Total Comments Count", 0)) / 
                posts_data["Reach"] * 100
            ).fillna(0).round(2)

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

[🎬 Post Performance](Post_Performance)

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
    "Post_Performance": "<|{post_performance_layout}|>",
    "Content_Efficiency": content_efficiency_dashboard.layout,
    "Semantics_Sentiment": semantics_dashboard.layout,
}

# Post Performance Layout
post_performance_layout = """
# 🎬 Post Performance Analysis

<|layout|columns=1 1|gap=20px|
<|part|class_name=metric-card|
## 📊 Total Posts
### <|{len(posts_data)}|text|class_name=big-number|>
|>

<|part|class_name=metric-card|
## 💖 Total Engagement
### <|{posts_data['Likes Count'].sum() if 'Likes Count' in posts_data.columns else 0:,.0f}|text|class_name=big-number|>
|>
|>

---

## 🔍 Individual Post Analysis

**Select a Post:**
<|{selected_post}|selector|lov={post_options}|dropdown|>

<|part|render={selected_post != ""}|
### Post Details

<|layout|columns=1 1 1|gap=15px|
<|part|class_name=metric-card|
**Likes**  
<|{posts_data[posts_data['Post ID']==selected_post]['Likes Count'].iloc[0] if not posts_data.empty and selected_post in posts_data['Post ID'].values else 0:,.0f}|text|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Reach**  
<|{posts_data[posts_data['Post ID']==selected_post]['Reach'].iloc[0] if not posts_data.empty and selected_post in posts_data['Post ID'].values else 0:,.0f}|text|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Saves**  
<|{posts_data[posts_data['Post ID']==selected_post]['Saves'].iloc[0] if not posts_data.empty and selected_post in posts_data['Post ID'].values else 0:,.0f}|text|class_name=metric-value|>
|>
|>

<|layout|columns=1 1|gap=15px|
<|part|class_name=metric-card|
**Comments**  
<|{posts_data[posts_data['Post ID']==selected_post]['Total Comments Count'].iloc[0] if not posts_data.empty and selected_post in posts_data['Post ID'].values and 'Total Comments Count' in posts_data.columns else 0:,.0f}|text|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Engagement Rate**  
<|{posts_data[posts_data['Post ID']==selected_post]['Engagement Rate'].iloc[0] if not posts_data.empty and selected_post in posts_data['Post ID'].values and 'Engagement Rate' in posts_data.columns else 0:.2f}|text|class_name=metric-value|>%
|>
|>
|>

---

## 📊 Top Performing Posts

**By Engagement Rate:**
<|{posts_data.nlargest(5, 'Engagement Rate') if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>

---

## 📈 Performance Over Time

<|{posts_data}|chart|type=scatter|x=Timestamp|y=Engagement Rate|size=Reach|text=Post ID|title=Engagement Rate vs Time (Size = Reach)|mode=markers|>

<|{posts_data}|chart|type=bar|x=Post ID|y[1]=Likes Count|y[2]=Saves|title=Likes vs Saves by Post|>
"""

# Launch the GUI
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    Gui(pages=pages, css_file="style.css").run(
        title="Malugo Analytics ✨", 
        host="0.0.0.0", 
        port=port,
        dark_mode=True
    )
