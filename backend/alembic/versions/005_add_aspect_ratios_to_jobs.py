"""Add aspect_ratios field to jobs table

Revision ID: 005
Revises: 004
Create Date: 2026-11-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('aspect_ratios', sa.ARRAY(sa.String()), default=list, nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'aspect_ratios')
