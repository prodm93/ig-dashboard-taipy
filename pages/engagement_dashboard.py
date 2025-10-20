# Engagement Dashboard Layout - FIXED SYNTAX
engagement_dashboard_layout = """
# 📊 Account Engagement Overview

<|{error_message}|text|class_name=error-message|>

<|layout|columns=1 1 1|gap=20px|

<|
## 👥 Current Followers
<|{current_followers}|text|format=,|class_name=big-number|>
|>

<|
## 📈 Latest Reach
<|{latest_reach}|text|format=,|class_name=big-number|>
|>

<|
## 👁️ Profile Views
<|{profile_views}|text|format=,|class_name=big-number|>
|>

|>

---

## 📊 Growth Trends

<|{account_data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Lifetime Follower Count|title=Reach & Follower Growth|>

<|{account_data}|chart|type=bar|x=Day|y=Reach|title=Reach by Day of Week|>

<!-- COMMENTED OUT: Online Followers chart (API returning zeros)
<|{account_data}|chart|type=line|x=Date|y=Online Followers|title=Online Followers Trend|>
When API starts working again, uncomment this chart
-->
"""
