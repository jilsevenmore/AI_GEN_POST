"""Add password reset code fields to users table

Revision ID: 009_add_password_reset_fields
Revises: 008_resize_search_vector_768
Create Date: 2026-11-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_add_password_reset_fields'
down_revision = '008_resize_search_vector_768'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_reset_code', sa.String(length=10), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column(
            'password_reset_expires',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_code')
