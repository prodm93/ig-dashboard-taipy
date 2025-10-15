import pandas as pd

data = pd.DataFrame({
    "week": ["W40", "W41", "W42"],
    "posts_published": [8, 12, 10],
    "draft_acceptance_rate": [75, 82, 90],
    "median_edit_time": [14, 11, 10],
})

layout = """
# ⚙️ Content Efficiency Dashboard

**Posts Published per Week**
<|{data}|chart|type=bar|x=week|y=posts_published|title=Weekly Post Throughput|>

**Draft Acceptance Rate (%)**
<|{data}|chart|type=line|x=week|y=draft_acceptance_rate|title=Acceptance Rate|>

**Median Editor Time (minutes)**
<|{data}|chart|type=bar|x=week|y=median_edit_time|title=Editing Time Efficiency|>
"""
