"""Add Instagram post type fields to jobs table

Revision ID: 004
Revises: 002
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('instagram_post_type', sa.String(20), nullable=True))
    op.add_column('jobs', sa.Column('instagram_cover_image_url', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'instagram_cover_image_url')
    op.drop_column('jobs', 'instagram_post_type')
