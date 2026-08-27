"""Add report staleness and analysis mode.

Revision ID: 20260801_0003
Revises: 35ac8583490b
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0003"
down_revision: str | None = "35ac8583490b"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_jobs",
        sa.Column(
            "mode",
            sa.Enum("HISTORICAL", "CURRENT", name="analysis_mode", native_enum=False),
            server_default=sa.text("'HISTORICAL'"),
            nullable=False,
        ),
    )
    op.add_column(
        "decision_reports",
        sa.Column("is_stale", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("decision_reports", sa.Column("stale_at", sa.DateTime(timezone=True)))
    op.add_column("decision_reports", sa.Column("stale_reason", sa.Text()))
    op.add_column("decision_reports", sa.Column("changed_version_id", sa.UUID()))
    op.create_foreign_key(
        "fk_decision_reports_changed_version_id_artifact_versions",
        "decision_reports",
        "artifact_versions",
        ["changed_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decision_reports_changed_version_id_artifact_versions",
        "decision_reports",
        type_="foreignkey",
    )
    op.drop_column("decision_reports", "changed_version_id")
    op.drop_column("decision_reports", "stale_reason")
    op.drop_column("decision_reports", "stale_at")
    op.drop_column("decision_reports", "is_stale")
    op.drop_column("analysis_jobs", "mode")
