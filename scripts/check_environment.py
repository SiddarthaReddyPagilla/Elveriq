"""Small beginner-friendly environment check."""
import sys
from dispatchforge_app.settings import load_settings

if __name__ == "__main__":
    settings = load_settings()
    print("Python:", sys.version.split()[0])
    print("Mode:", settings.environment)
    print("Database backend:", "PostgreSQL" if settings.database_url.startswith("postgresql") else "SQLite (development)")
    print("Existing DispatchForge modules are preserved.")
