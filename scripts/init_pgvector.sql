-- HippoRAG pgvector Initialization Script
-- Run this script to initialize all required tables in PostgreSQL with pgvector extension
--
-- Usage:
--   psql -h localhost -U hipporag -d hipporag -f init_pgvector.sql
--
-- Or using environment variables:
--   psql $PGVECTOR_HOST -U $PGVECTOR_USER -d $PGVECTOR_DATABASE -f init_pgvector.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ==================== Embedding Tables ====================

-- Chunk embeddings table
CREATE TABLE IF NOT EXISTS embeddings_chunk (
    hash_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    book_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Entity embeddings table
CREATE TABLE IF NOT EXISTS embeddings_entity (
    hash_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    book_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fact embeddings table
CREATE TABLE IF NOT EXISTS embeddings_fact (
    hash_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    book_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create book_id indexes for embedding tables
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_book_id ON embeddings_chunk(book_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_entity_book_id ON embeddings_entity(book_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_fact_book_id ON embeddings_fact(book_id);

-- ==================== Multi-Tenancy Tables ====================

-- Books table
CREATE TABLE IF NOT EXISTS books (
    book_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256),
    description TEXT,
    doc_count INT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'ready',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Businesses table
CREATE TABLE IF NOT EXISTS businesses (
    business_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256),
    description TEXT,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Book bindings table (many-to-many relationship between businesses and books)
CREATE TABLE IF NOT EXISTS book_bindings (
    id SERIAL PRIMARY KEY,
    business_id VARCHAR(64) NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
    book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(business_id, book_id)
);

-- Create indexes for book_bindings
CREATE INDEX IF NOT EXISTS idx_book_bindings_business ON book_bindings(business_id);
CREATE INDEX IF NOT EXISTS idx_book_bindings_book ON book_bindings(book_id);

-- ==================== Optional: Create vector indexes ====================
-- Note: Vector indexes are typically created after data is inserted
-- Uncomment and run these after inserting data for better search performance

-- CREATE INDEX embeddings_chunk_embedding_idx ON embeddings_chunk USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX embeddings_entity_embedding_idx ON embeddings_entity USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX embeddings_fact_embedding_idx ON embeddings_fact USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ==================== Verification ====================

-- List all created tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('embeddings_chunk', 'embeddings_entity', 'embeddings_fact',
                      'books', 'businesses', 'book_bindings')
ORDER BY table_name;

-- Show extension status
SELECT * FROM pg_extension WHERE extname = 'vector';
