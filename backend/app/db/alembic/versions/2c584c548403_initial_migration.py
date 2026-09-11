"""initial_migration

Revision ID: 2c584c548403
Revises: 
Create Date: 2026-09-09 23:37:48.241617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c584c548403'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the complete crew-management schema."""
    from backend.app.db.base import Base
    from backend.app.db import models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop crew-management tables in dependency-safe order."""
    bind = op.get_bind()
    for table in ("audit_log", "notifications", "checklists", "work_orders", "crews"):
        op.drop_table(table)
