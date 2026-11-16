"""Add source file fields to jobs table

Revision ID: 002
Revises: 001
Create Date: 2026-11-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('source_file_name', sa.String(255), nullable=True))
    op.add_column('jobs', sa.Column('source_file_url', sa.String(1000), nullable=True))
    op.add_column('jobs', sa.Column('source_context_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'source_context_text')
    op.drop_column('jobs', 'source_file_url')
    op.drop_column('jobs', 'source_file_name')
