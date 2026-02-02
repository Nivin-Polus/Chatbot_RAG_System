import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text, inspect

# Add the parent directory to sys.path to import app modules
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.config import settings

def main():
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    
    if not inspector.has_table("plugin_integrations"):
        print("Table 'plugin_integrations' does not exist. Skipping.")
        return

    columns = {col["name"] for col in inspector.get_columns("plugin_integrations")}
    
    if "is_widget_active" not in columns:
        print("Adding 'is_widget_active' column to 'plugin_integrations'...")
        with engine.connect() as conn:
            # For MySQL, use TINYINT(1) for Boolean
            conn.execute(text("ALTER TABLE plugin_integrations ADD COLUMN is_widget_active TINYINT(1) NOT NULL DEFAULT 1"))
            conn.commit()
        print("Successfully added 'is_widget_active' column.")
    else:
        print("'is_widget_active' column already exists.")

if __name__ == "__main__":
    main()
