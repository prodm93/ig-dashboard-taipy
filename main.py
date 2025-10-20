import os
import pandas as pd
import re
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables

# Import layout strings from page modules
from pages import engagement_dashboard, content_efficiency_dashboard, semantics_dashboard

# Initialize variables
error_message = ""
account_data = pd.DataFrame(columns=["Date", "Reach", "Lifetime Follower Count"])
posts_data = pd.DataFrame(columns=["Post ID", "Likes Count", "Reach", "Saves", "Timestamp"])

# For post selector
selected_post = ""
post_options = []

# Post metrics - initialize with zeros
post_likes = 0
post_reach = 0
post_saves = 0
post_comments = 0
post_engagement = 0.0

def extract_caption_title(caption):
    """Extract title from caption after 'Transmissão ###:' pattern"""
    if pd.isna(caption) or not caption:
        return "Untitled"
    
    # Try to match pattern like "Transmissão 002: Title here"
    match = re.search(r'Transmissão\s+#?\d+:\s*(.+?)(?:\n|$)', caption, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        # Remove emojis and limit length
        title = re.sub(r'[^\w\s,.-]', '', title)
        return title[:50] + "..." if len(title) > 50 else title
    
    # Fallback: just take first line or first 50 chars
    first_line = caption.split('\n')[0].strip()
    first_line = re.sub(r'[^\w\s,.-]', '', first_line)
    return first_line[:50] + "..." if len(first_line) > 50 else first_line

def calculate_engagement_rate(row):
    """Calculate engagement rate: (Audience Comments + Likes + Saves) / Reach * 100"""
    try:
        audience_comments = float(row.get('Audience Comments Count', 0) or 0)
        likes = float(row.get('Likes Count', 0) or 0)
        saves = float(row.get('Saves', 0) or 0)
        reach = float(row.get('Reach', 0) or 0)
        
        if reach > 0:
            return round(((audience_comments + likes + saves) / reach) * 100, 2)
        return 0.0
    except:
        return 0.0

def get_post_metrics(post_id):
    """Get metrics for a specific post"""
    if posts_data.empty or post_id not in posts_data['Post ID'].values:
        return 0, 0, 0, 0, 0.0
    
    row = posts_data[posts_data['Post ID'] == post_id].iloc[0]
    return (
        int(row.get('Likes Count', 0) or 0),
        int(row.get('Reach', 0) or 0),
        int(row.get('Saves', 0) or 0),
        int(row.get('Audience Comments Count', 0) or 0),
        float(row.get('Engagement Rate', 0) or 0)
    )

try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]
    
    # Fetch both tables
    all_data = fetch_all_tables(API_KEY, BASE_ID, cfg["tables"])
    
    # Account metrics
    account_data = all_data.get("ig_accounts", pd.DataFrame())
    if not account_data.empty and "Date" in account_data.columns:
        account_data["Date"] = pd.to_datetime(account_data["Date"], errors='coerce')
        account_data = account_data.sort_values("Date")
    
    # Posts data
    posts_data = all_data.get("ig_posts", pd.DataFrame())
    if not posts_data.empty:
        # Process timestamp
        if "Timestamp" in posts_data.columns:
            posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"], errors='coerce')
            posts_data = posts_data.sort_values("Timestamp", ascending=False)
        
        # Create display column: "CONTENT_TYPE: Title - Date"
        posts_data["Display Label"] = posts_data.apply(
            lambda row: f"{row.get('Content Type', 'POST')}: {extract_caption_title(row.get('Caption', ''))} - {row['Timestamp'].strftime('%b %d, %Y') if pd.notna(row.get('Timestamp')) else 'No Date'}",
            axis=1
        )
        
        # Calculate proper engagement rate
        posts_data["Engagement Rate"] = posts_data.apply(calculate_engagement_rate, axis=1)
        
        # Create post options dictionary for selector (ID: Label mapping)
        if "Post ID" in posts_data.columns:
            post_options = list(zip(
                posts_data["Post ID"].tolist(),
                posts_data["Display Label"].tolist()
            ))
            selected_post = posts_data["Post ID"].iloc[0] if len(posts_data) > 0 else ""
            
            # Initialize metrics for first post
            if selected_post:
                post_likes, post_reach, post_saves, post_comments, post_engagement = get_post_metrics(selected_post)

except Exception as e:
    error_message = f"⚠️ {e}. Check Airtable config/env."
    print(f"Error loading data: {e}")

# Function to update post metrics when selection changes
def update_post_metrics(state):
    """Update post metrics when selection changes"""
    state.post_likes, state.post_reach, state.post_saves, state.post_comments, state.post_engagement = get_post_metrics(state.selected_post)

# Create root page with navigation and logo
root_page = """
<|layout|columns=250px 1fr|
<|part|class_name=sidebar|

<|part|class_name=logo-container|
<|image|src=logo.png|width=120px|>
|>

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
**Audience Comments**  
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

<!-- COMMENTED OUT: Likes vs Saves comparison
<|{posts_data}|chart|type=bar|x=Display Label|y[1]=Likes Count|y[2]=Saves|title=Likes vs Saves by Post|>
-->

---

## 🏆 Top 5 Performers

*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|{posts_data.nlargest(5, 'Engagement Rate')[['Display Label', 'Likes Count', 'Reach', 'Saves', 'Audience Comments Count', 'Engagement Rate']] if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>
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
        dark_mode=True
    )
