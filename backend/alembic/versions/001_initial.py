"""Initial migration - create core tables

Revision ID: 001
Revises: 
Create Date: 2026-11-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    # Companies table
    op.create_table(
        'companies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_superuser', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_company_id', 'users', ['company_id'])

    # Brand kits table
    op.create_table(
        'brand_kits',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('tagline', sa.String(500), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(1000), nullable=True),
        sa.Column('primary_color', sa.String(7), nullable=True),
        sa.Column('secondary_color', sa.String(7), nullable=True),
        sa.Column('tone', sa.String(100), nullable=True),
        sa.Column('use_openai_only', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),  # blog, post
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('tone', sa.String(100), nullable=True),
        sa.Column('audience', sa.String(200), nullable=True),
        sa.Column('keywords', sa.ARRAY(sa.String()), default=list, nullable=False),
        sa.Column('image_description', sa.Text(), nullable=True),
        sa.Column('platforms', sa.ARRAY(sa.String()), default=list, nullable=False),
        sa.Column('use_references', sa.Boolean(), default=True, nullable=False),
        sa.Column('reference_image_ids', sa.ARRAY(UUID(as_uuid=True)), default=list, nullable=False),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('progress', sa.Integer(), default=0, nullable=False),
        sa.Column('current_step', sa.String(100), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_jobs_company_id', 'jobs', ['company_id'])
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])

    # Contents table (generated text + images)
    op.create_table(
        'contents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),  # blog, social_post
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('long_text', sa.Text(), nullable=False),
        sa.Column('platform_contents', sa.JSON(), nullable=False, default=list),
        sa.Column('image_variants', sa.JSON(), nullable=False, default=list),
        sa.Column('primary_image_id', UUID(as_uuid=True), nullable=True),
        sa.Column('safety_check_passed', sa.Boolean(), default=True, nullable=False),
        sa.Column('safety_flags', sa.ARRAY(sa.String()), default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_contents_company_id', 'contents', ['company_id'])

    # Images table (library)
    op.create_table(
        'images',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_id', UUID(as_uuid=True), sa.ForeignKey('contents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('tags', sa.ARRAY(sa.String()), default=list, nullable=False),
        sa.Column('aspect_ratio', sa.String(10), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('is_global', sa.Boolean(), default=False, nullable=False),
        sa.Column('search_vector', sa.Text(), nullable=True),  # For pgvector - will be vector type
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_images_company_id', 'images', ['company_id'])
    op.create_index('ix_images_is_global', 'images', ['is_global'])
    op.create_index('ix_images_approved_at', 'images', ['approved_at'])

    # Channel connections (Buffer)
    op.create_table(
        'channel_connections',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform', sa.String(20), nullable=False),  # instagram, facebook, linkedin
        sa.Column('external_account_id', sa.String(255), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_channel_connections_company_id', 'channel_connections', ['company_id'])
    op.create_unique_constraint('uq_channel_company_platform_account', 'channel_connections', ['company_id', 'platform', 'external_account_id'])

    # Publish attempts
    op.create_table(
        'publish_attempts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('content_id', UUID(as_uuid=True), sa.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channel_connections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), default='pending', nullable=False),  # pending, sent, failed, retrying
        sa.Column('external_post_id', sa.String(255), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0, nullable=False),
        sa.Column('idempotency_key', sa.String(100), nullable=False, unique=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_publish_attempts_content_id', 'publish_attempts', ['content_id'])
    op.create_index('ix_publish_attempts_channel_id', 'publish_attempts', ['channel_id'])
    op.create_index('ix_publish_attempts_status', 'publish_attempts', ['status'])

    # Quotas
    op.create_table(
        'quotas',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('daily_free_requests_used', sa.Integer(), default=0, nullable=False),
        sa.Column('daily_free_requests_limit', sa.Integer(), default=12, nullable=False),
        sa.Column('daily_spend_usd', sa.Numeric(10, 4), default=0, nullable=False),
        sa.Column('daily_spend_cap_usd', sa.Numeric(10, 4), default=10.0, nullable=False),
        sa.Column('regenerations_used', sa.Integer(), default=0, nullable=False),
        sa.Column('regenerations_limit', sa.Integer(), default=3, nullable=False),
        sa.Column('last_reset_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('quotas')
    op.drop_table('publish_attempts')
    op.drop_table('channel_connections')
    op.drop_table('images')
    op.drop_table('contents')
    op.drop_table('jobs')
    op.drop_table('brand_kits')
    op.drop_table('users')
    op.drop_table('companies')
    op.execute('DROP EXTENSION IF EXISTS vector;')