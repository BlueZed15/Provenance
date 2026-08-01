"""Enable pgvector for Mistral embeddings.

Revision ID: 20260801_0001
Revises:
Create Date: 2026-08-01
"""

from alembic import op


revision: str = "20260801_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("create extension if not exists vector with schema extensions")


def downgrade() -> None:
    # The extension may be shared by other application tables. Removing it in a
    # downgrade could destroy vector columns, so rollback deliberately leaves it.
    pass
