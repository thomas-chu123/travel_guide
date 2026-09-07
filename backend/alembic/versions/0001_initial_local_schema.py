"""initial local event-map schema

Revision ID: 0001_initial_local_schema
Revises:
Create Date: 2026-09-04
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_local_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("ward", sa.String(length=80), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("google_place_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="valid_venue_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="valid_venue_longitude"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_place_id"),
    )
    op.create_index("ix_venues_ward", "venues", ["ward"])
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("venue_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_language", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fee_kind", sa.String(length=32), nullable=False),
        sa.Column("price_min_jpy", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_max_jpy", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("category IN ('exhibition', 'attraction', 'activity')", name="valid_event_category"),
        sa.CheckConstraint("status IN ('candidate', 'published', 'rejected', 'stale')", name="valid_event_status"),
        sa.CheckConstraint("fee_kind IN ('free', 'paid', 'unknown')", name="valid_fee_kind"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_venue_id", "events", ["venue_id"])
    op.create_table(
        "event_occurrences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="valid_occurrence_range"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_occurrences_event_id", "event_occurrences", ["event_id"])
    op.create_index("ix_event_occurrences_starts_at", "event_occurrences", ["starts_at"])
    op.create_index("ix_event_occurrences_ends_at", "event_occurrences", ["ends_at"])


def downgrade() -> None:
    op.drop_table("event_occurrences")
    op.drop_table("events")
    op.drop_table("venues")
