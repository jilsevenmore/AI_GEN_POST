"""Resize image search_vector to 768 dims for BAAI/bge-base-en-v1.5

Revision ID: 008_resize_search_vector_768
Revises: 007_pgvector_search_vector
Create Date: 2026-11-17 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '008_resize_search_vector_768'
down_revision = '007_pgvector_search_vector'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_images_search_vector_hnsw;')
    op.execute('ALTER TABLE images ALTER COLUMN search_vector TYPE vector(768) USING NULL;')
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_images_search_vector_hnsw '
        'ON images USING hnsw (search_vector vector_cosine_ops) '
        'WITH (m = 16, ef_construction = 64);'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_images_search_vector_hnsw;')
    op.execute('ALTER TABLE images ALTER COLUMN search_vector TYPE vector(1536) USING NULL;')
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_images_search_vector_hnsw '
        'ON images USING hnsw (search_vector vector_cosine_ops) '
        'WITH (m = 16, ef_construction = 64);'
    )
