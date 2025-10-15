import os
from taipy.gui import Gui

# Import page modules
from pages import engagement_dashboard, content_efficiency_dashboard, semantics_dashboard

# Define page routes
pages = {
    "/": engagement_dashboard.layout,
    "engagement": engagement_dashboard.layout,
    "efficiency": content_efficiency_dashboard.layout,
    "semantics": semantics_dashboard.layout,
}

# Launch the GUI
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    
    # Create a shared state dictionary with all variables from all pages
    shared_variables = {
        # From engagement_dashboard
        "data": engagement_dashboard.data,
        "error_message": engagement_dashboard.error_message,
    }
    
    Gui(pages=pages).run(
        title="Malugo Dashboard", 
        host="0.0.0.0", 
        port=port,
        **shared_variables
    )
