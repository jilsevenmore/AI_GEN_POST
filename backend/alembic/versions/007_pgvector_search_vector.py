"""Enable pgvector search_vector column and HNSW index

Revision ID: 007_pgvector_search_vector
Revises: 006
Create Date: 2026-11-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_pgvector_search_vector'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    # Convert existing text column to pgvector; clear non-embedding data
    op.execute('ALTER TABLE images ALTER COLUMN search_vector TYPE vector(1536) USING NULL;')
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_images_search_vector_hnsw '
        'ON images USING hnsw (search_vector vector_cosine_ops) '
        'WITH (m = 16, ef_construction = 64);'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_images_search_vector_hnsw;')
    op.execute('ALTER TABLE images ALTER COLUMN search_vector TYPE text USING NULL;')
