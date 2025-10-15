import pandas as pd

data = pd.DataFrame({
    "subtopic": ["Trust", "Romance", "Communication", "Growth", "Conflict"],
    "sentiment": [0.8, 0.6, 0.75, 0.9, 0.4],
    "engagement": [1200, 950, 1320, 1600, 870],
})

layout = """
# 💬 Semantics & Sentiment Dashboard

**Subtopic–to–Engagement Relationship**

<|{data}|chart|type=bubble|x=sentiment|y=engagement|size=engagement|text=subtopic|title=Sentiment vs Engagement|>

This tab will later include:
- 🔍 Topic-level engagement breakdown  
- 🎨 Sentiment trend visualizations  
- 💭 Caption-to-engagement correlation plots
"""
