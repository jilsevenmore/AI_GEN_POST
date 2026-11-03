-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schemas if needed
CREATE SCHEMA IF NOT EXISTS public;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE ai_gen_post TO postgres;
GRANT ALL ON SCHEMA public TO postgres;