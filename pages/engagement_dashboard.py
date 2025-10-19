# pages/engagement_dashboard.py

layout = """
# 📊 Account Engagement Overview

<|{error_message}|text|class_name=error-message|>

<|layout|columns=1 1 1|gap=20px|
<|part|class_name=metric-card|
## 👥 Current Followers
### <|{account_data['Lifetime Follower Count'].iloc[-1] if not account_data.empty and 'Lifetime Follower Count' in account_data.columns else 0:,.0f}|text|class_name=big-number|>
|>

<|part|class_name=metric-card|
## 📈 Latest Reach
### <|{account_data['Reach'].iloc[-1] if not account_data.empty and 'Reach' in account_data.columns else 0:,.0f}|text|class_name=big-number|>
|>

<|part|class_name=metric-card|
## 👁️ Profile Views
### <|{account_data['Lifetime Profile Views'].iloc[-1] if not account_data.empty and 'Lifetime Profile Views' in account_data.columns else 0:,.0f}|text|class_name=big-number|>
|>
|>

---

## 📊 Growth Trends

<|{account_data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Lifetime Follower Count|title=Reach & Follower Growth|>

<|{account_data}|chart|type=bar|x=Day|y=Reach|title=Reach by Day of Week|>

<|{account_data}|chart|type=line|x=Date|y=Online Followers|title=Online Followers Trend|>
"""
