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
    gui = Gui(pages=pages)
    gui.run(title="Social Performance Dashboard", port=8080, use_reloader=True)
