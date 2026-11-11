"""Database setup. Local demo uses SQLite, hosted production requires PostgreSQL."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base


class Database:
    def __init__(self, url: str):
        options = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, pool_pre_ping=True, **options)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def enable_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)

    def initialize(self):
        # Schema creation is suitable for local MVP. Use versioned migrations before production.
        Base.metadata.create_all(self.engine)

    def dispose(self):
        self.engine.dispose()
