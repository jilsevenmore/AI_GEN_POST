"""Add leads table for CRM capture and automation (Steps 4, 6, 10).

Revision ID: 006
Revises: 005
Create Date: 2026-11-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('company', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('interest', sa.String(100), nullable=True),
        sa.Column('source', sa.String(100), nullable=False, server_default='landing_page'),
        sa.Column('status', sa.String(50), nullable=False, server_default='new'),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assigned_owner', sa.String(200), nullable=True),
        sa.Column('next_follow_up', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_leads_email', 'leads', ['email'])
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_company_id', 'leads', ['company_id'])
    op.create_index('ix_leads_source', 'leads', ['source'])


def downgrade() -> None:
    op.drop_index('ix_leads_source', table_name='leads')
    op.drop_index('ix_leads_company_id', table_name='leads')
    op.drop_index('ix_leads_status', table_name='leads')
    op.drop_index('ix_leads_email', table_name='leads')
    op.drop_table('leads')
