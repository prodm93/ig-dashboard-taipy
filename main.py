
import os
import math
import pandas as pd
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables

# -------------------------------
# State / Globals
# -------------------------------
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
total_posts = 0
total_likes = 0

# Aggregation controls
agg_granularity = "Day"  # Day | Week
date_start = ""          # YYYY-MM-DD
date_end = ""            # YYYY-MM-DD
agg_engagement_over_time = pd.DataFrame(columns=["Date", "Engagement Rate"])

# -------------------------------
# Helpers
# -------------------------------
def nz(x, default=0):
    """Return default for None/NaN; otherwise x."""
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return x
    except Exception:
        return default

def calculate_engagement_rate(row):
    try:
        audience_comments = float(nz(row.get("Audience Comments Count", 0)))
        likes = float(nz(row.get("Likes Count", 0)))
        saves = float(nz(row.get("Saves", 0)))
        reach = float(nz(row.get("Reach", 0)))
        if reach > 0:
            return round(((audience_comments + likes + saves) / reach) * 100, 2)
        return 0.0
    except Exception:
        return 0.0

def get_post_metrics(post_id):
    if posts_data.empty or str(post_id) not in posts_data.get("Post ID", []).astype(str).tolist():
        return 0, 0, 0, 0, 0.0
    row = posts_data[posts_data["Post ID"].astype(str) == str(post_id)].iloc[0]
    return (
        int(nz(row.get("Likes Count", 0))),
        int(nz(row.get("Reach", 0))),
        int(nz(row.get("Saves", 0))),
        int(nz(row.get("Audience Comments Count", 0))),
        float(nz(row.get("Engagement Rate", 0.0))),
    )

def _parse_date(s):
    try:
        return pd.to_datetime(s).date() if s else None
    except Exception:
        return None

def recompute_agg(state=None):
    """Rebuild aggregated engagement rate over time based on controls."""
    global agg_engagement_over_time
    df = posts_data.copy()
    agg_engagement_over_time = pd.DataFrame(columns=["Date", "Engagement Rate"])

    if df.empty or "Timestamp" not in df.columns:
        if state is not None:
            state.agg_engagement_over_time = agg_engagement_over_time
        return

    df["__dt"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["__dt"])

    _start = _parse_date(state.date_start if state is not None else date_start)
    _end = _parse_date(state.date_end if state is not None else date_end)
    if _start:
        df = df[df["__dt"].dt.date >= _start]
    if _end:
        df = df[df["__dt"].dt.date <= _end]

    gran = (state.agg_granularity if state is not None else agg_granularity) or "Day"
    if gran == "Week":
        key = df["__dt"].dt.to_period("W").apply(lambda p: p.start_time.date())
    else:
        key = df["__dt"].dt.date

    group = df.groupby(key).agg(
        {
            "Likes Count": "sum",
            "Audience Comments Count": "sum",
            "Saves": "sum",
            "Reach": "sum",
        }
    ).reset_index().rename(columns={0: "Date"})
    group = group.rename(columns={group.columns[0]: "Date"})

    if len(group) > 0:
        group["Engagement Rate"] = (
            (group.get("Likes Count", 0) + group.get("Audience Comments Count", 0) + group.get("Saves", 0))
            / group.get("Reach", 0).replace(0, pd.NA)
        ) * 100
        group["Engagement Rate"] = group["Engagement Rate"].fillna(0).round(2)
        agg_engagement_over_time = group[["Date", "Engagement Rate"]]

    if state is not None:
        state.agg_engagement_over_time = agg_engagement_over_time

def _on_agg_change(state):
    recompute_agg(state)


# Preformatted display strings to avoid UI comma glitch
def fmt_int(n): 
    try: 
        return f"{int(n):,}"
    except Exception: 
        return "0"

def refresh_formats():
    global current_followers_fmt, latest_reach_fmt, profile_views_fmt
    global post_likes_fmt, post_reach_fmt, post_saves_fmt, post_comments_fmt
    global total_likes_fmt
    current_followers_fmt = fmt_int(current_followers)
    latest_reach_fmt = fmt_int(latest_reach)
    profile_views_fmt = fmt_int(profile_views)
    post_likes_fmt = fmt_int(post_likes)
    post_reach_fmt = fmt_int(post_reach)
    post_saves_fmt = fmt_int(post_saves)
    post_comments_fmt = fmt_int(post_comments)
    total_likes_fmt = fmt_int(total_likes)


# -------------------------------
# Data load
# -------------------------------
try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]

    all_data = fetch_all_tables(API_KEY, BASE_ID, cfg["tables"])

    # Account metrics
    account_data = all_data.get("ig_accounts", pd.DataFrame())
    if not account_data.empty and "Date" in account_data.columns:
        account_data["Date"] = pd.to_datetime(account_data["Date"], errors="coerce")
        account_data = account_data.sort_values("Date")
        account_data["Day"] = account_data["Date"].dt.day_name()

        if len(account_data) > 0:
            latest_row = account_data.iloc[-1]
            current_followers = int(nz(latest_row.get("Lifetime Follower Count", 0)))
            latest_reach = int(nz(latest_row.get("Reach", 0)))
            profile_views = int(nz(latest_row.get("Lifetime Profile Views", 0)))

    # Posts / comments
    posts_data = all_data.get("ig_posts", pd.DataFrame())
    if not posts_data.empty:
        if "Timestamp" in posts_data.columns:
            posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"], errors="coerce")
            posts_data = posts_data.sort_values("Timestamp", ascending=False)

        # Normalize Post ID as string for reliable selection
        if 'Post ID' in posts_data.columns:
            posts_data['Post ID'] = posts_data['Post ID'].astype(str)


        posts_data["Engagement Rate"] = posts_data.apply(calculate_engagement_rate, axis=1)

        total_posts = len(posts_data)
        if "Likes Count" in posts_data.columns:
            total_likes = int(pd.to_numeric(posts_data["Likes Count"], errors="coerce").fillna(0).sum())

        # Date range defaults for aggregation
        try:
            if "Timestamp" in posts_data.columns and len(posts_data) > 0:
                _dt = pd.to_datetime(posts_data["Timestamp"], errors="coerce").dropna()
                if len(_dt) > 0:
                    date_start = str(_dt.min().date())
                    date_end = str(_dt.max().date())
        except Exception as _e:
            print("Date range init error:", _e)

        # Build selector options
        if "Post ID" in posts_data.columns:
            # Display label: Content Type + date (if available)
            if "Display Label" not in posts_data.columns:
                posts_data["Display Label"] = posts_data.apply(
                    lambda row: f"{row.get('Content Type', 'POST')}: "
                                f"{row['Timestamp'].strftime('%b %d, %Y') if pd.notna(row.get('Timestamp')) else 'No Date'}",
                    axis=1
                )
            post_options = list(zip(posts_data["Post ID"].tolist(), posts_data["Display Label"].tolist()))
            selected_post = posts_data["Post ID"].iloc[0] if len(posts_data) > 0 else ""
            if selected_post:
                (post_likes, post_reach, post_saves,
                 post_comments, post_engagement) = get_post_metrics(selected_post)
                refresh_formats()

        # Initial aggregate
        recompute_agg()
        refresh_formats()

except Exception as e:
    error_message = f"⚠️ {e}"
    print(f"✗ Error: {e}")

def update_post_metrics(state):
    (state.post_likes,
     state.post_reach,
     state.post_saves,
     state.post_comments,
     state.post_engagement) = get_post_metrics(state.selected_post)
    print('Post changed ->', state.selected_post, 'metrics:', state.post_likes, state.post_reach, state.post_saves, state.post_comments, state.post_engagement)
    state.post_likes_fmt = fmt_int(state.post_likes)
    state.post_reach_fmt = fmt_int(state.post_reach)
    state.post_saves_fmt = fmt_int(state.post_saves)
    state.post_comments_fmt = fmt_int(state.post_comments)

# -------------------------------
# UI
# -------------------------------
root_page = """<|layout|columns=250px 1fr|
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
|>
|>
"""

engagement_dashboard_layout = """# 📊 Account Engagement Overview

<|layout|columns=1 1 1|gap=20px|class_name=metrics-grid|

<|
## 👥 Current Followers
<|{current_followers_fmt}|text|class_name=metric-number|>
|>

<|
## 📈 Latest Reach
<|{latest_reach_fmt}|text|class_name=metric-number|>
|>

<|
## 👁️ Profile Views
<|{profile_views_fmt}|text|class_name=metric-number|>
|>

|>

---

## 📊 Growth Trends

<|{account_data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Lifetime Follower Count|title=Reach & Follower Growth|class_name=narrow|>

<|{account_data}|chart|type=bar|x=Day|y=Reach|title=Reach by Day of Week|class_name=narrow|>

<|part|class_name=panel|
## 📈 Total Engagement Rate Over Time (All Posts)
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*
<|layout|columns=1 1 1|gap=10px|
**Group by**
<|{agg_granularity}|selector|lov=Day;Week|dropdown|on_change=_on_agg_change|>
**Start date**
<|{date_start}|date|on_change=_on_agg_change|>
**End date**
<|{date_end}|date|on_change=_on_agg_change|>
|>

<|{agg_engagement_over_time}|chart|type=line|x=Date|y=Engagement Rate|title=Total Engagement Rate Over Time|class_name=narrow|>
|>
"""

post_performance_layout = """# 🎬 Post Performance Analysis

<|layout|columns=1 1|gap=20px|class_name=metrics-grid|

<|
## 📊 Total Posts
<|{total_posts}|text|class_name=metric-number|>
|>

<|
## 💖 Total Likes
<|{total_likes_fmt}|text|class_name=metric-number|>
|>

|>

---

## 🔍 Individual Post Analysis

**Select a Post:**

<|{selected_post}|selector|lov={post_options}|dropdown|on_change=update_post_metrics|>

<|layout|columns=1 1 1|gap=15px|class_name=metrics-grid|

<|
**Likes**  
<|{post_likes_fmt}|text|class_name=metric-number|>
|>

<|
**Reach**  
<|{post_reach_fmt}|text|class_name=metric-number|>
|>

<|
**Saves**  
<|{post_saves_fmt}|text|class_name=metric-number|>
|>

|>

<|layout|columns=1 1|gap=15px|class_name=metrics-grid|

<|
**Audience Comments**  
<|{post_comments_fmt}|text|class_name=metric-number|>
|>

<|
**Engagement Rate**  
<|{post_engagement}|text|format=%.2f|class_name=metric-number|>%
|>

|>

---

## 📈 Performance Trends
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|{posts_data}|chart|type=scatter|mode=lines+markers|x=Timestamp|y=Engagement Rate|title=Engagement Rate Over Time|class_name=narrow|>

---

## 🏆 Top 5 Performers
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|{posts_data.nlargest(5, 'Engagement Rate')[['Display Label', 'Likes Count', 'Reach', 'Saves', 'Audience Comments Count', 'Engagement Rate']] if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>
"""

content_efficiency_layout = """# ⚙️ Content Efficiency Dashboard

Coming soon!
"""

semantics_layout = """# 💬 Semantics & Sentiment Dashboard

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
        dark_mode=True,
    )
