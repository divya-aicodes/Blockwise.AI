"""Create the crew-management tables using the configured database URL."""
from sqlalchemy import inspect

from backend.app.db.base import engine, init_db, DATABASE_URL

init_db()
print(f"Tables created successfully in {DATABASE_URL}")
print("Tables:", inspect(engine).get_table_names())
