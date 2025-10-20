import os
import pandas as pd
import re
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables

# Initialize variables
error_message = ""
account_data = pd.DataFrame(columns=["Date", "Reach", "Lifetime Follower Count"])
posts_data = pd.DataFrame(columns=["Post ID", "Likes Count", "Reach", "Saves", "Timestamp"])

selected_post = ""
post_options = []

post_likes = 0
post_reach = 0
post_saves = 0
post_comments = 0
post_engagement = 0.0

current_followers = 0
latest_reach = 0
profile_views = 0

def extract_caption_title(caption):
    """Extract ONLY the title, completely removing Transmissão prefix"""
    if pd.isna(caption) or not caption:
        return "Untitled"
    
    # Remove the entire "Transmissão #003:" part
    clean = re.sub(r'^.*?Transmissão\s+#?\d+:\s*', '', str(caption), flags=re.IGNORECASE)
    
    # Take first line
    first_line = clean.split('\n')[0].strip()
    
    # Remove emojis
    first_line = re.sub(r'[^\w\s,.:!?-]', '', first_line)
    
    return first_line[:45] + "..." if len(first_line) > 45 else first_line

def calculate_engagement_rate(row):
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
    
    all_data = fetch_all_tables(API_KEY, BASE_ID, cfg["tables"])
    
    account_data = all_data.get("ig_accounts", pd.DataFrame())
    if not account_data.empty and "Date" in account_data.columns:
        account_data["Date"] = pd.to_datetime(account_data["Date"], errors='coerce')
        account_data = account_data.sort_values("Date")
        
        if len(account_data) > 0:
            latest_row = account_data.iloc[-1]
            current_followers = int(latest_row.get('Lifetime Follower Count', 0) or 0)
            latest_reach = int(latest_row.get('Reach', 0) or 0)
            profile_views = int(latest_row.get('Lifetime Profile Views', 0) or 0)
    
    posts_data = all_data.get("ig_posts", pd.DataFrame())
    if not posts_data.empty:
        if "Timestamp" in posts_data.columns:
            posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"], errors='coerce')
            posts_data = posts_data.sort_values("Timestamp", ascending=False)
        
        posts_data["Display Label"] = posts_data.apply(
            lambda row: f"{row.get('Content Type', 'POST')}: {extract_caption_title(row.get('Caption', ''))} ({row['Timestamp'].strftime('%b %d')})" if pd.notna(row.get('Timestamp')) else f"{row.get('Content Type', 'POST')}: {extract_caption_title(row.get('Caption', ''))}",
            axis=1
        )
        
        posts_data["Engagement Rate"] = posts_data.apply(calculate_engagement_rate, axis=1)
        
        if "Post ID" in posts_data.columns:
            post_options = list(zip(
                posts_data["Post ID"].tolist(),
                posts_data["Display Label"].tolist()
            ))
            selected_post = posts_data["Post ID"].iloc[0] if len(posts_data) > 0 else ""
            
            if selected_post:
                post_likes, post_reach, post_saves, post_comments, post_engagement = get_post_metrics(selected_post)

except Exception as e:
    error_message = f"⚠️ {e}"
    print(f"Error: {e}")

def update_post_metrics(state):
    state.post_likes, state.post_reach, state.post_saves, state.post_comments, state.post_engagement = get_post_metrics(state.selected_post)

root_page = """
<|layout|columns=250px 1fr|
<|part|class_name=sidebar|
<|logo.png|image|width=120px|>

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

engagement_dashboard_layout = """
# 📊 Account Engagement Overview

<|layout|columns=1 1 1|gap=20px|class_name=metrics-grid|

<|
<|text|class_name=metric-label|## 👥 Current Followers|>
<|text|class_name=metric-number|{current_followers:,}|>
|>

<|
<|text|class_name=metric-label|## 📈 Latest Reach|>
<|text|class_name=metric-number|{latest_reach:,}|>
|>

<|
<|text|class_name=metric-label|## 👁️ Profile Views|>
<|text|class_name=metric-number|{profile_views:,}|>
|>

|>

---

## 📊 Growth Trends

<|{account_data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Lifetime Follower Count|title=Reach & Follower Growth|>

<|{account_data}|chart|type=bar|x=Day|y=Reach|title=Reach by Day of Week|>
"""

post_performance_layout = """
# 🎬 Post Performance Analysis

<|layout|columns=1 1|gap=20px|class_name=metrics-grid|

<|
<|text|class_name=metric-label|## 📊 Total Posts|>
<|text|class_name=metric-number|{len(posts_data)}|>
|>

<|
<|text|class_name=metric-label|## 💖 Total Likes|>
<|text|class_name=metric-number|{int(posts_data['Likes Count'].sum()) if 'Likes Count' in posts_data.columns else 0:,}|>
|>

|>

---

## 🔍 Individual Post Analysis

**Select a Post:**

<|{selected_post}|selector|lov={post_options}|dropdown|on_change=update_post_metrics|>

<|layout|columns=1 1 1|gap=15px|class_name=metrics-grid|

<|
<|text|class_name=metric-label|**Likes**|>
<|text|class_name=metric-number|{post_likes:,}|>
|>

<|
<|text|class_name=metric-label|**Reach**|>
<|text|class_name=metric-number|{post_reach:,}|>
|>

<|
<|text|class_name=metric-label|**Saves**|>
<|text|class_name=metric-number|{post_saves:,}|>
|>

|>

<|layout|columns=1 1|gap=15px|class_name=metrics-grid|

<|
<|text|class_name=metric-label|**Audience Comments**|>
<|text|class_name=metric-number|{post_comments:,}|>
|>

<|
<|text|class_name=metric-label|**Engagement Rate**|>
<|text|class_name=metric-number|{post_engagement:.2f}%|>
|>

|>

---

## 📈 Performance Trends
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|{posts_data}|chart|type=scatter|mode=lines+markers|x=Timestamp|y=Engagement Rate|title=Engagement Rate Over Time|>

---

## 🏆 Top 5 Performers
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|{posts_data.nlargest(5, 'Engagement Rate')[['Display Label', 'Likes Count', 'Reach', 'Saves', 'Audience Comments Count', 'Engagement Rate']] if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>
"""

content_efficiency_layout = """
# ⚙️ Content Efficiency Dashboard

Coming soon!
"""

semantics_layout = """
# 💬 Semantics & Sentiment Dashboard

Coming soon!
"""

pages = {
    "/": root_page,
    "Engagement_Dashboard": engagement_dashboard_layout,
    "Post_Performance": post_performance_layout,
    "Content_Efficiency": content_efficiency_layout,
    "Semantics_Sentiment": semantics_layout,
}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    Gui(pages=pages, css_file="style.css").run(
        title="Malugo Analytics ✨", 
        host="0.0.0.0", 
        port=port,
        dark_mode=True
    )
