from taipy.gui import Gui
from components.sidebar import sidebar
from pages import engagement_dashboard, content_efficiency_dashboard, semantics_dashboard

# Define page routes
pages = {
    "/": sidebar,
    "Engagement Dashboard": engagement_dashboard.layout,
    "Content Efficiency": content_efficiency_dashboard.layout,
    "Semantics & Sentiment": semantics_dashboard.layout,
}

# Launch the GUI
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    Gui(pages=pages).run(title="Malugo Dashboard", host="0.0.0.0", port=port)
