"""Small smoke check for the configured crew database."""
from sqlalchemy import inspect

from backend.app.db.base import engine, init_db

init_db()
tables = inspect(engine).get_table_names()
required = {"crews", "work_orders", "checklists", "notifications", "audit_log"}
missing = required.difference(tables)
assert not missing, f"Missing tables: {sorted(missing)}"
print("Crew database OK:", ", ".join(sorted(required)))
