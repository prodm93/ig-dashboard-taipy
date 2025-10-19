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
selected_post_data = {}

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

# Function to get selected post metrics
def get_post_metric(metric_name, default=0):
    if posts_data.empty or not selected_post or selected_post not in posts_data['Post ID'].values:
        return default
    row = posts_data[posts_data['Post ID'] == selected_post].iloc[0]
    return row.get(metric_name, default)

# Create metric variables
post_likes = 0
post_reach = 0
post_saves = 0
post_comments = 0
post_engagement = 0.0

def update_post_metrics(state):
    """Update post metrics when selection changes"""
    if not posts_data.empty and state.selected_post in posts_data['Post ID'].values:
        row = posts_data[posts_data['Post ID'] == state.selected_post].iloc[0]
        state.post_likes = int(row.get('Likes Count', 0))
        state.post_reach = int(row.get('Reach', 0))
        state.post_saves = int(row.get('Saves', 0))
        state.post_comments = int(row.get('Total Comments Count', 0))
        state.post_engagement = float(row.get('Engagement Rate', 0))

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

# Post Performance Layout - FIXED
post_performance_layout = """
# 🎬 Post Performance Analysis

## 📊 Overview

<|layout|columns=1 1|gap=20px|
<|part|class_name=metric-card|
**Total Posts**  
<|{len(posts_data)}|text|class_name=big-number|>
|>

<|part|class_name=metric-card|
**Total Engagement**  
<|{int(posts_data['Likes Count'].sum()) if 'Likes Count' in posts_data.columns else 0}|text|format=,|class_name=big-number|>
|>
|>

---

## 🔍 Individual Post Analysis

**Select a Post:**

<|{selected_post}|selector|lov={post_options}|dropdown|on_change=update_post_metrics|>

<|layout|columns=1 1 1|gap=15px|
<|part|class_name=metric-card|
**Likes**  
<|{post_likes}|text|format=,|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Reach**  
<|{post_reach}|text|format=,|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Saves**  
<|{post_saves}|text|format=,|class_name=metric-value|>
|>
|>

<|layout|columns=1 1|gap=15px|
<|part|class_name=metric-card|
**Comments**  
<|{post_comments}|text|format=,|class_name=metric-value|>
|>

<|part|class_name=metric-card|
**Engagement Rate**  
<|{post_engagement}|text|format=%.2f|class_name=metric-value|>%
|>
|>

---

## 📈 Performance Trends

<|{posts_data}|chart|type=scatter|x=Timestamp|y=Engagement Rate|mode=markers|title=Engagement Rate Over Time|>

<|{posts_data}|chart|type=bar|x=Post ID|y[1]=Likes Count|y[2]=Saves|title=Likes vs Saves by Post|>

---

## 🏆 Top Performers

<|{posts_data.nlargest(10, 'Engagement Rate')[['Post ID', 'Likes Count', 'Reach', 'Saves', 'Engagement Rate']] if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>
"""

# Define page routes
pages = {
    "/": root_page,
    "Engagement_Dashboard": engagement_dashboard.layout,
    "Post_Performance": post_performance_layout,
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
        dark_mode=True,
        on_change=update_post_metrics
    )
